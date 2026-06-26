"""HTTP API for multi-step bar backtests (trade book + metrics). Frontend can integrate later."""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backtest.bars import (
    align_bars_by_min_length,
    fetch_ccxt_ohlcv_bars,
    fetch_ccxt_ohlcv_range,
    fetch_futu_ohlcv_bars,
    interval_sec_to_ccxt_timeframe,
    iso_utc_to_ms,
    load_ohlcv_json,
)
from backtest.config import resolve_backtest_config, set_env_from_config
from backtest.exchange_trade_format import normalize_trade_row_for_api
from backtest.loop import MultiStepResult, run_multi_step_backtest
from backtest.trade_book import read_jsonl_dict_records
from config.runs_paths import runs_dir as _resolved_runs_dir
from strategies.presets import (
    DEFAULT_QUANT_STRATEGY_ID,
    get_preset,
    list_presets,
    merge_preset_quick_request,
)

RUNS_DIR = _resolved_runs_dir()
BACKTESTS_DIR = RUNS_DIR / "backtests"

# Async preset jobs: UI polls GET /backtests/jobs/{run_id} for step progress.
BACKTEST_JOBS: dict[str, dict[str, Any]] = {}

router = APIRouter(tags=["backtests"])
logger = logging.getLogger(__name__)


def _max_api_steps() -> int:
    return max(20, int(os.environ.get("BACKTEST_API_MAX_STEPS", "5000")))


def _job_path(run_id: str) -> Path:
    return BACKTESTS_DIR / str(run_id) / "job.json"


def _write_job(run_id: str, payload: dict[str, Any]) -> None:
    """Persist job progress so multi-worker servers can poll reliably."""
    try:
        p = _job_path(run_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        # Best-effort: in-memory polling may still work in single-worker setups.
        pass


def _jsonl_preview(path: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    return read_jsonl_dict_records(path, limit=limit)


def _read_jsonl_all(path: Path) -> list[dict[str, Any]]:
    return read_jsonl_dict_records(path)


def _downsample_rows(rows: list[dict[str, Any]], max_points: int) -> list[dict[str, Any]]:
    """Evenly sample rows (inclusive ends) so charts stay responsive for long runs."""
    n = len(rows)
    if n <= max_points or max_points < 2:
        return rows
    indices = sorted({int(round(i * (n - 1) / (max_points - 1))) for i in range(max_points)})
    return [rows[i] for i in indices]


def _evaluation_block(
    *,
    result: MultiStepResult,
    initial_cash: float,
) -> dict[str, Any]:
    final = float(result.final_equity) if result.final_equity is not None else float(initial_cash)
    ret_pct = ((final - initial_cash) / initial_cash * 100.0) if initial_cash else 0.0
    block: dict[str, Any] = {
        "initial_cash": initial_cash,
        "final_equity": final,
        "total_return_pct": round(ret_pct, 4),
        "trade_count": result.trade_count,
        "trades_preview": [
            normalize_trade_row_for_api(r) for r in _jsonl_preview(result.trades_path, limit=15)
        ],
        "note": (
            "Fills are simulated at each bar's close when Risk Guard approves and the portfolio "
            "desk proposes a trade; see paths.trades for the full JSONL ledger."
        ),
    }
    if result.benchmark is not None:
        block["benchmark"] = dict(result.benchmark)
    return block


def _backtest_paths_response(result: MultiStepResult) -> dict[str, Any]:
    return {
        "summary": str(result.summary_path),
        "trades": str(result.trades_path),
        "equity": str(result.equity_path),
        "iterations": str(result.iterations_path) if result.iterations_path else None,
        "events": str(result.events_path),
    }


class QuickBacktestRequest(BaseModel):
    ticker: str = Field("BTC/USDT", min_length=3)
    n_bars: int = Field(200, ge=20, le=100_000)
    interval_sec: int = Field(
        300,
        ge=60,
        le=86_400,
        description="Bar size in seconds (e.g. 300 = 5m).",
    )
    initial_cash: float = Field(10_000.0, gt=0)
    fee_bps: float = Field(10.0, ge=0, le=500)
    max_steps: int | None = Field(
        None,
        ge=1,
        description="Optional cap on bars processed (subject to server cap).",
    )
    exchange_id: str = Field(
        "binance",
        description='Data source: CCXT id (e.g. "binance") or "futu" for Futu OpenD (HK/US symbols like HK.00700).',
    )
    since_iso: str | None = Field(
        None,
        description="ccxt_range: ISO date/datetime (UTC) for range start, e.g. 2023-01-01.",
    )
    until_iso: str | None = Field(
        None,
        description="ccxt_range: ISO date/datetime (UTC) for range end, e.g. 2024-01-01.",
    )


class DemoBacktestRequest(BaseModel):
    """README-style demo defaults: multi-symbol, aligned bars, single portfolio run."""

    symbols: str = Field(
        "BTC/USDT,ETH/USDT,SOL/USDT",
        min_length=3,
        description="Comma-separated symbols, min 2. CCXT pairs for binance (e.g. BTC/USDT); "
        "Futu codes for exchange_id=futu (e.g. HK.00700,HK.09988).",
    )
    steps: int = Field(100, ge=20, le=20_000, description="Candles to fetch and replay.")
    interval_sec: int = Field(
        86_400,
        ge=60,
        le=86_400,
        description="Bar size in seconds (default: 1d).",
    )
    exchange_id: str = Field(
        "binance",
        description='CCXT exchange id or "futu" for OpenD multi-symbol runs.',
    )
    initial_cash: float = Field(10_000.0, gt=0)
    fee_bps: float = Field(10.0, ge=0, le=500)


def _execute_quick_backtest(
    req: QuickBacktestRequest,
    *,
    strategy: dict[str, Any] | None = None,
    run_id: str | None = None,
    on_bar_complete: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    cfg = resolve_backtest_config()
    set_env_from_config(cfg)
    cap = _max_api_steps()
    tf = interval_sec_to_ccxt_timeframe(int(req.interval_sec))
    ex_id = (req.exchange_id or "binance").strip().lower()
    if req.since_iso or req.until_iso:
        if not req.since_iso or not req.until_iso:
            raise HTTPException(
                status_code=400, detail="since_iso and until_iso must both be set (or both omitted)"
            )
        if ex_id == "futu":
            raise HTTPException(
                status_code=400,
                detail=(
                    "exchange_id=futu does not support since_iso/until_iso yet; "
                    "omit the date range for latest-N candles, or use a CCXT exchange for fixed windows."
                ),
            )
        bars = fetch_ccxt_ohlcv_range(
            req.ticker,
            timeframe=tf,
            since_ms=iso_utc_to_ms(req.since_iso),
            until_ms=iso_utc_to_ms(req.until_iso),
            exchange_id=ex_id,
            max_rows=int(req.n_bars),
        )
    elif ex_id == "futu":
        bars = fetch_futu_ohlcv_bars(
            req.ticker,
            int(req.n_bars),
            interval_sec=int(req.interval_sec),
        )
    else:
        bars = fetch_ccxt_ohlcv_bars(
            req.ticker,
            int(req.n_bars),
            timeframe=tf,
            exchange_id=ex_id,
        )
    want = req.max_steps if req.max_steps is not None else req.n_bars
    effective = min(want, req.n_bars, cap)
    if effective < 1:
        raise HTTPException(status_code=400, detail="No steps to run after applying caps.")

    if run_id is not None and run_id in BACKTEST_JOBS:
        BACKTEST_JOBS[run_id].update(
            {
                "status": "running",
                "total_steps": effective,
                "step": 0,
            }
        )
        _write_job(run_id, dict(BACKTEST_JOBS[run_id]))

    logger.info(
        "backtest quick ticker=%s bars=%s effective_steps=%s",
        req.ticker,
        req.n_bars,
        effective,
    )
    result = run_multi_step_backtest(
        ticker=req.ticker,
        bars=bars,
        initial_cash=req.initial_cash,
        fee_bps=req.fee_bps,
        interval_sec=req.interval_sec,
        runs_dir=RUNS_DIR,
        max_steps=effective,
        run_id=run_id,
        progress_callback=on_bar_complete,
        deploy_config=cfg,
        deploy_profile_weights=cfg.get("profile_weights") or None,
        deploy_profile_id=cfg.get("profile_id") or None,
        deploy_arbitrator_mode=cfg.get("arbitrator_mode") or None,
        take_profit_pct=cfg.get("take_profit_pct", 0.0),
        stop_loss_pct=cfg.get("stop_loss_pct", 0.0),
        max_hold_bars=cfg.get("max_hold_bars", 0),
    )
    logger.info(
        "backtest done run_id=%s trade_count=%s final_equity=%s",
        result.run_id,
        result.trade_count,
        result.metrics.get("final_equity"),
    )
    out: dict[str, Any] = {
        "run_id": result.run_id,
        "steps": result.steps,
        "trade_count": result.trade_count,
        "metrics": result.metrics,
        "evaluation": _evaluation_block(result=result, initial_cash=req.initial_cash),
        "paths": _backtest_paths_response(result),
        "capped": effective < min(want, req.n_bars),
        "server_max_steps": cap,
    }
    if result.quality_report:
        out["quality_report"] = result.quality_report
    if result.resolved_config:
        out["resolved_config"] = result.resolved_config
    if strategy:
        out["strategy"] = strategy
    return out


def _execute_demo_backtest(
    req: DemoBacktestRequest,
    *,
    run_id: str | None = None,
    on_bar_complete: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    cfg = resolve_backtest_config()
    set_env_from_config(cfg)
    cap = _max_api_steps()
    want = int(req.steps)
    effective = max(1, min(want, cap))
    ex_id = (req.exchange_id or "binance").strip().lower()
    tf = interval_sec_to_ccxt_timeframe(int(req.interval_sec))
    syms = [s.strip() for s in (req.symbols or "").split(",") if s.strip()]
    if len(syms) < 2:
        raise HTTPException(
            status_code=400, detail="demo backtest requires at least 2 symbols (comma-separated)"
        )

    if run_id is not None and run_id in BACKTEST_JOBS:
        BACKTEST_JOBS[run_id].update({"status": "running", "total_steps": effective, "step": 0})
        _write_job(run_id, dict(BACKTEST_JOBS[run_id]))

    bars_by_symbol: dict[str, list[list[float]]] = {}
    for sym in syms:
        if ex_id == "futu":
            bars = fetch_futu_ohlcv_bars(
                sym,
                effective,
                interval_sec=int(req.interval_sec),
            )
        else:
            bars = fetch_ccxt_ohlcv_bars(
                exchange_id=ex_id, symbol=sym, timeframe=tf, limit=effective
            )
        if not bars:
            raise HTTPException(
                status_code=400, detail=f"No OHLCV returned for {sym} ({ex_id}, {tf})"
            )
        bars_by_symbol[sym] = [list(map(float, row)) for row in bars]

    aligned = align_bars_by_min_length(bars_by_symbol)

    # Use the first symbol as "primary" for logging/bench labels inside the engine.
    primary = syms[0]
    result = run_multi_step_backtest(
        ticker=primary,
        bars_by_symbol=aligned,
        initial_cash=req.initial_cash,
        fee_bps=req.fee_bps,
        interval_sec=req.interval_sec,
        runs_dir=RUNS_DIR,
        max_steps=effective,
        run_id=run_id,
        progress_callback=on_bar_complete,
        deploy_config=cfg,
        deploy_profile_weights=cfg.get("profile_weights") or None,
        deploy_profile_id=cfg.get("profile_id") or None,
        deploy_arbitrator_mode=cfg.get("arbitrator_mode") or None,
        take_profit_pct=cfg.get("take_profit_pct", 0.0),
        stop_loss_pct=cfg.get("stop_loss_pct", 0.0),
        max_hold_bars=cfg.get("max_hold_bars", 0),
    )

    out: dict[str, Any] = {
        "run_id": result.run_id,
        "steps": result.steps,
        "trade_count": result.trade_count,
        "metrics": result.metrics,
        "evaluation": _evaluation_block(result=result, initial_cash=req.initial_cash),
        "paths": _backtest_paths_response(result),
        "capped": effective < want,
        "server_max_steps": cap,
        "symbols": syms,
        "timeframe": tf,
        "exchange_id": ex_id,
    }
    if result.quality_report:
        out["quality_report"] = result.quality_report
    if result.resolved_config:
        out["resolved_config"] = result.resolved_config
    return out


@router.post("/backtests/quick")
def post_quick_backtest(req: QuickBacktestRequest) -> dict[str, Any]:
    """
    Run a **synthetic** OHLCV replay: one LangGraph pass per bar, book simulated fills,
    write ``.runs/backtests/<run_id>/`` (trades, equity, ``iterations.jsonl``, summary) and flow events under ``.runs/``.
    """
    return _execute_quick_backtest(req)


@router.post("/backtests/quick/async")
def post_quick_backtest_async(req: QuickBacktestRequest) -> dict[str, Any]:
    """Run quick backtest in a background thread and expose per-bar progress.

    Poll :func:`get_backtest_job` for progress updates.
    """
    rid = f"bt-{uuid.uuid4().hex[:12]}"
    BACKTEST_JOBS[rid] = {
        "status": "queued",
        "step": 0,
        "total_steps": 0,
        "trade_count": 0,
        "equity": None,
        "capital": None,
        "positions": 0,
        "ts": None,
    }
    _write_job(rid, dict(BACKTEST_JOBS[rid]))

    def work() -> None:
        def on_bar(i: int, total: int, snap: dict[str, Any]) -> None:
            if rid not in BACKTEST_JOBS:
                return
            BACKTEST_JOBS[rid].update(
                {
                    "status": "running",
                    "step": i + 1,
                    "total_steps": total,
                    "trade_count": snap.get("trade_count", 0),
                    "equity": snap.get("equity"),
                    "capital": snap.get("capital"),
                    "positions": snap.get("positions", 0),
                    "ts": snap.get("ts"),
                }
            )
            _write_job(rid, dict(BACKTEST_JOBS[rid]))

        try:
            out = _execute_quick_backtest(req, run_id=rid, on_bar_complete=on_bar)
            BACKTEST_JOBS[rid] = {"status": "completed", "result": out}
            _write_job(rid, dict(BACKTEST_JOBS[rid]))
        except HTTPException as e:
            detail = e.detail
            BACKTEST_JOBS[rid] = {
                "status": "failed",
                "error": detail if isinstance(detail, str) else str(detail),
            }
            _write_job(rid, dict(BACKTEST_JOBS[rid]))
        except Exception as e:
            logger.exception("async quick backtest failed")
            BACKTEST_JOBS[rid] = {"status": "failed", "error": str(e)}
            _write_job(rid, dict(BACKTEST_JOBS[rid]))

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": rid, "poll": f"/backtests/jobs/{rid}"}


@router.post("/backtests/demo/async")
def post_demo_backtest_async(req: DemoBacktestRequest) -> dict[str, Any]:
    """Run README-style multi-symbol demo backtest (async) with job polling."""
    rid = f"bt-{uuid.uuid4().hex[:12]}"
    BACKTEST_JOBS[rid] = {
        "status": "queued",
        "step": 0,
        "total_steps": 0,
        "trade_count": 0,
        "equity": None,
        "capital": None,
        "positions": 0,
        "ts": None,
    }
    _write_job(rid, dict(BACKTEST_JOBS[rid]))

    def work() -> None:
        def on_bar(i: int, total: int, snap: dict[str, Any]) -> None:
            if rid not in BACKTEST_JOBS:
                return
            BACKTEST_JOBS[rid].update(
                {
                    "status": "running",
                    "step": i + 1,
                    "total_steps": total,
                    "trade_count": snap.get("trade_count", 0),
                    "equity": snap.get("equity"),
                    "capital": snap.get("capital"),
                    "positions": snap.get("positions", 0),
                    "ts": snap.get("ts"),
                }
            )
            _write_job(rid, dict(BACKTEST_JOBS[rid]))

        try:
            out = _execute_demo_backtest(req, run_id=rid, on_bar_complete=on_bar)
            BACKTEST_JOBS[rid] = {"status": "completed", "result": out}
            _write_job(rid, dict(BACKTEST_JOBS[rid]))
        except HTTPException as e:
            detail = e.detail
            BACKTEST_JOBS[rid] = {
                "status": "failed",
                "error": detail if isinstance(detail, str) else str(detail),
            }
            _write_job(rid, dict(BACKTEST_JOBS[rid]))
        except Exception as e:
            logger.exception("async demo backtest failed")
            BACKTEST_JOBS[rid] = {"status": "failed", "error": str(e)}
            _write_job(rid, dict(BACKTEST_JOBS[rid]))

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": rid, "poll": f"/backtests/jobs/{rid}"}


class PresetBacktestRequest(BaseModel):
    preset_id: str = Field(DEFAULT_QUANT_STRATEGY_ID, min_length=1)
    ticker: str = Field("BTC/USDT", min_length=3)
    exchange_id: str | None = Field(
        None,
        description='Optional: "binance" (default) or "futu" for Futu OpenD (use HK.00700 style tickers).',
    )
    n_bars: int | None = Field(None, ge=20, le=100_000)
    interval_sec: int | None = Field(None, ge=60, le=86_400)
    max_steps: int | None = Field(None, ge=1)
    seed: int | None = Field(None, ge=0)
    fee_bps: float | None = Field(None, ge=0, le=500)
    initial_cash: float | None = Field(None, gt=0)


@router.get("/strategies")
def get_strategy_presets() -> dict[str, Any]:
    """List named strategy presets and default parameters for the backtest UI."""
    return {"strategies": list_presets()}


@router.post("/backtests/preset")
def post_preset_backtest(req: PresetBacktestRequest) -> dict[str, Any]:
    """Run a quick backtest using a **named preset** (defaults for bars, interval, caps)."""
    try:
        merged = merge_preset_quick_request(
            req.preset_id,
            ticker=req.ticker,
            exchange_id=req.exchange_id,
            n_bars=req.n_bars,
            interval_sec=req.interval_sec,
            max_steps=req.max_steps,
            seed=req.seed,
            fee_bps=req.fee_bps,
            initial_cash=req.initial_cash,
        )
        preset = get_preset(req.preset_id)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    q = QuickBacktestRequest(**merged)
    return _execute_quick_backtest(
        q,
        strategy={
            "preset_id": preset.id,
            "title": preset.title,
            "description": preset.description,
        },
    )


@router.post("/backtests/preset/async")
def post_preset_backtest_async(req: PresetBacktestRequest) -> dict[str, Any]:
    """Run preset backtest in a background thread.

    Poll :func:`get_backtest_job` for per-bar progress.
    """
    try:
        merged = merge_preset_quick_request(
            req.preset_id,
            ticker=req.ticker,
            exchange_id=req.exchange_id,
            n_bars=req.n_bars,
            interval_sec=req.interval_sec,
            max_steps=req.max_steps,
            seed=req.seed,
            fee_bps=req.fee_bps,
            initial_cash=req.initial_cash,
        )
        preset = get_preset(req.preset_id)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    q = QuickBacktestRequest(**merged)
    rid = f"bt-{uuid.uuid4().hex[:12]}"
    BACKTEST_JOBS[rid] = {
        "status": "queued",
        "step": 0,
        "total_steps": 0,
        "trade_count": 0,
        "equity": None,
        "vetoed": None,
    }
    _write_job(rid, dict(BACKTEST_JOBS[rid]))

    def work() -> None:
        def on_bar(i: int, total: int, snap: dict[str, Any]) -> None:
            if rid not in BACKTEST_JOBS:
                return
            BACKTEST_JOBS[rid].update(
                {
                    "status": "running",
                    "step": i + 1,
                    "total_steps": total,
                    "trade_count": snap.get("trade_count", 0),
                    "equity": snap.get("equity"),
                    "vetoed": snap.get("vetoed"),
                }
            )
            _write_job(rid, dict(BACKTEST_JOBS[rid]))

        try:
            out = _execute_quick_backtest(
                q,
                strategy={
                    "preset_id": preset.id,
                    "title": preset.title,
                    "description": preset.description,
                },
                run_id=rid,
                on_bar_complete=on_bar,
            )
            BACKTEST_JOBS[rid] = {"status": "completed", "result": out}
            _write_job(rid, dict(BACKTEST_JOBS[rid]))
        except HTTPException as e:
            detail = e.detail
            BACKTEST_JOBS[rid] = {
                "status": "failed",
                "error": detail if isinstance(detail, str) else str(detail),
            }
            _write_job(rid, dict(BACKTEST_JOBS[rid]))
        except Exception as e:
            logger.exception("async preset backtest failed")
            BACKTEST_JOBS[rid] = {"status": "failed", "error": str(e)}
            _write_job(rid, dict(BACKTEST_JOBS[rid]))

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": rid, "poll": f"/backtests/jobs/{rid}"}


@router.get("/backtests/jobs/{run_id}")
def get_backtest_job(run_id: str) -> dict[str, Any]:
    rid = str(run_id)
    p = _job_path(rid)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    job = BACKTEST_JOBS.get(rid)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job or run_id")
    return job


@router.get("/backtests/jobs/{run_id}/stream")
async def stream_backtest_job(run_id: str, request: Request) -> StreamingResponse:
    """Server-sent events stream of backtest job progress.

    This is a drop-in upgrade over polling for large fanout. Clients should close the stream
    once they receive a terminal state (completed/failed).
    """

    rid = str(run_id)

    async def gen():
        last_payload: str | None = None
        last_keepalive = 0.0
        while True:
            if await request.is_disconnected():
                return

            try:
                job = get_backtest_job(rid)
            except HTTPException as e:
                # One structured error event, then end.
                payload = json.dumps(
                    {"status": "failed", "error": str(e.detail)}, ensure_ascii=False
                )
                yield f"event: error\ndata: {payload}\n\n"
                return

            payload = json.dumps(job, ensure_ascii=False)
            if payload != last_payload:
                last_payload = payload
                yield f"data: {payload}\n\n"

            status = (job or {}).get("status")
            if status in ("completed", "failed"):
                return

            # Keep-alive comment ~ every 15s to prevent idle timeouts.
            now = anyio.current_time()
            if now - last_keepalive > 15.0:
                last_keepalive = now
                yield ": keepalive\n\n"

            await anyio.sleep(0.5)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class FileBacktestRequest(BaseModel):
    path: str = Field(..., description="Path under repo to JSON OHLCV file (server-local).")
    initial_cash: float = Field(10_000.0, gt=0)
    fee_bps: float = Field(10.0, ge=0, le=500)
    interval_sec: int = Field(300, ge=60, le=86_400)
    max_steps: int | None = Field(None, ge=1)


@router.post("/backtests/from-file")
def post_backtest_from_file(req: FileBacktestRequest) -> dict[str, Any]:
    """Load bars from a server-local JSON file (operator path; not multipart upload)."""
    p = Path(req.path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {req.path}")
    try:
        ticker, bars = load_ohlcv_json(p)
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    cap = _max_api_steps()
    want = req.max_steps if req.max_steps is not None else len(bars)
    effective = min(want, len(bars), cap)
    cfg = resolve_backtest_config()
    set_env_from_config(cfg)
    result = run_multi_step_backtest(
        ticker=ticker,
        bars=bars,
        initial_cash=req.initial_cash,
        fee_bps=req.fee_bps,
        interval_sec=req.interval_sec,
        runs_dir=RUNS_DIR,
        max_steps=effective,
        deploy_config=cfg,
        deploy_profile_weights=cfg.get("profile_weights") or None,
        deploy_profile_id=cfg.get("profile_id") or None,
        deploy_arbitrator_mode=cfg.get("arbitrator_mode") or None,
        take_profit_pct=cfg.get("take_profit_pct", 0.0),
        stop_loss_pct=cfg.get("stop_loss_pct", 0.0),
        max_hold_bars=cfg.get("max_hold_bars", 0),
    )
    out: dict[str, Any] = {
        "run_id": result.run_id,
        "steps": result.steps,
        "trade_count": result.trade_count,
        "metrics": result.metrics,
        "evaluation": _evaluation_block(result=result, initial_cash=req.initial_cash),
        "paths": _backtest_paths_response(result),
        "capped": effective < min(want, len(bars)),
        "server_max_steps": cap,
    }
    if result.quality_report:
        out["quality_report"] = result.quality_report
    if result.resolved_config:
        out["resolved_config"] = result.resolved_config
    return out


@router.get("/backtests/{run_id}/summary")
def get_backtest_summary(run_id: str) -> dict[str, Any]:
    summary_path = BACKTESTS_DIR / run_id / "summary.json"
    if not summary_path.is_file():
        raise HTTPException(status_code=404, detail="Unknown backtest run_id")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    # Backfill start/end time for older runs (added later in engine).
    if isinstance(summary, dict) and ("start_ts" not in summary or "end_ts" not in summary):
        equity_path = BACKTESTS_DIR / run_id / "equity.jsonl"
        if equity_path.is_file():
            try:
                lines = equity_path.read_text(encoding="utf-8").splitlines()
                if lines:
                    first = json.loads(lines[0])
                    last = json.loads(lines[-1])
                    start_ts = first.get("ts")
                    end_ts = last.get("ts")
                    if isinstance(start_ts, (int, float)) and isinstance(end_ts, (int, float)):
                        start_ts_i = int(start_ts)
                        end_ts_i = int(end_ts)
                        summary["start_ts"] = start_ts_i
                        summary["end_ts"] = end_ts_i
                        try:
                            from datetime import datetime, timezone

                            summary["start_iso"] = datetime.fromtimestamp(
                                start_ts_i / 1000, tz=timezone.utc
                            ).isoformat()
                            summary["end_iso"] = datetime.fromtimestamp(
                                end_ts_i / 1000, tz=timezone.utc
                            ).isoformat()
                        except Exception:
                            summary.setdefault("start_iso", None)
                            summary.setdefault("end_iso", None)
            except Exception:
                pass
    return summary


@router.get("/backtests/{run_id}/export/manifest")
def get_backtest_export_manifest(run_id: str) -> dict[str, Any]:
    """Return the ``export_manifest.json`` for a completed backtest.

    Contains schema version, file listing, and metrics summary.
    Returns 404 if the export bundle was not generated.
    """
    manifest_path = BACKTESTS_DIR / run_id / "export_manifest.json"
    if not manifest_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "export_manifest.json not found — run may be too old "
                "or did not complete export bundle generation"
            ),
        )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@router.get("/backtests/{run_id}/equity")
def get_backtest_equity(
    run_id: str,
    max_points: int = Query(2000, ge=10, le=50_000),
) -> dict[str, Any]:
    """Return equity curve points for charting (downsampled for large runs)."""
    equity_path = BACKTESTS_DIR / run_id / "equity.jsonl"
    if not equity_path.is_file():
        raise HTTPException(
            status_code=404, detail="Unknown backtest run_id or missing equity.jsonl"
        )
    rows = _read_jsonl_all(equity_path)
    raw_count = len(rows)
    sampled = _downsample_rows(rows, max_points) if raw_count > max_points else rows
    return {
        "run_id": run_id,
        "count": raw_count,
        "max_points": max_points,
        "downsampled": raw_count > len(sampled),
        "points": sampled,
    }


@router.get("/backtests/{run_id}/trades")
def get_backtest_trades(
    run_id: str,
    limit: int = Query(2000, ge=1, le=50_000),
) -> dict[str, Any]:
    """Return booked trades from ``trades.jsonl`` (newest last; capped by ``limit``)."""
    trades_path = BACKTESTS_DIR / run_id / "trades.jsonl"
    if not trades_path.is_file():
        raise HTTPException(
            status_code=404, detail="Unknown backtest run_id or missing trades.jsonl"
        )
    rows = _read_jsonl_all(trades_path)
    total = len(rows)
    if total > limit:
        rows = rows[-limit:]
    normalized = [normalize_trade_row_for_api(r) for r in rows]
    return {
        "run_id": run_id,
        "total": total,
        "returned": len(normalized),
        "truncated": total > len(normalized),
        "trades": normalized,
    }


@router.get("/backtests/{run_id}/iterations")
def get_backtest_iterations(
    run_id: str,
    limit: int = Query(300, ge=1, le=5000),
) -> dict[str, Any]:
    """Return per-bar iteration receipts from ``iterations.jsonl`` (capped)."""

    iterations_path = BACKTESTS_DIR / run_id / "iterations.jsonl"
    if not iterations_path.is_file():
        raise HTTPException(
            status_code=404, detail="Unknown backtest run_id or missing iterations.jsonl"
        )
    rows = _jsonl_preview(iterations_path, limit=limit)
    return {
        "run_id": run_id,
        "total_returned": len(rows),
        "iterations": rows,
    }


@router.get("/backtests/{run_id}/bars")
def get_backtest_bars(
    run_id: str,
    max_points: int = Query(2000, ge=10, le=50_000),
) -> dict[str, Any]:
    """Return OHLCV bars used for the run (primary ticker), downsampled for charting."""
    bars_path = BACKTESTS_DIR / run_id / "bars.json"
    if not bars_path.is_file():
        raise HTTPException(status_code=404, detail="Unknown backtest run_id or missing bars.json")
    raw = json.loads(bars_path.read_text(encoding="utf-8"))
    bars = raw.get("bars")
    if not isinstance(bars, list):
        raise HTTPException(status_code=500, detail="bars.json is invalid (missing bars)")
    raw_count = len(bars)
    sampled = _downsample_rows(bars, max_points) if raw_count > max_points else bars
    return {
        "run_id": run_id,
        "ticker": raw.get("ticker"),
        "interval_sec": raw.get("interval_sec"),
        "count": raw_count,
        "max_points": max_points,
        "downsampled": raw_count > len(sampled),
        "bars": sampled,
    }


@router.get("/backtests")
def list_backtests() -> dict[str, Any]:
    """List run ids that have a persisted ``summary.json`` (skips crashed / partial dirs)."""
    if not BACKTESTS_DIR.is_dir():
        return {"runs": []}
    runs: list[str] = []
    for p in sorted(BACKTESTS_DIR.iterdir()):
        if not p.is_dir():
            continue
        if (p / "summary.json").is_file():
            runs.append(p.name)
    return {"runs": runs}
