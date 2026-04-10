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

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backtest.bars import load_ohlcv_json, synthetic_ohlcv_bars
from backtest.exchange_trade_format import normalize_trade_row_for_api
from backtest.loop import MultiStepResult, run_multi_step_backtest
from backtest.trade_book import read_jsonl_dict_records
from strategies.presets import (
    DEFAULT_QUANT_STRATEGY_ID,
    get_preset,
    list_presets,
    merge_preset_quick_request,
)

RUNS_DIR = Path(".runs")
BACKTESTS_DIR = RUNS_DIR / "backtests"

# Async preset jobs: UI polls GET /backtests/jobs/{run_id} for step progress.
BACKTEST_JOBS: dict[str, dict[str, Any]] = {}

router = APIRouter(tags=["backtests"])
logger = logging.getLogger(__name__)


def _max_api_steps() -> int:
    return max(20, int(os.environ.get("BACKTEST_API_MAX_STEPS", "5000")))


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
    seed: int = Field(1, ge=0)
    initial_cash: float = Field(10_000.0, gt=0)
    fee_bps: float = Field(10.0, ge=0, le=500)
    max_steps: int | None = Field(
        None,
        ge=1,
        description="Optional cap on bars processed (subject to server cap).",
    )


def _execute_quick_backtest(
    req: QuickBacktestRequest,
    *,
    strategy: dict[str, Any] | None = None,
    run_id: str | None = None,
    on_bar_complete: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    cap = _max_api_steps()
    bars = synthetic_ohlcv_bars(
        req.n_bars,
        seed=req.seed,
        interval_sec=req.interval_sec,
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

    logger.info(
        "backtest quick ticker=%s bars=%s effective_steps=%s seed=%s",
        req.ticker,
        req.n_bars,
        effective,
        req.seed,
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
    if strategy:
        out["strategy"] = strategy
    return out


@router.post("/backtests/quick")
def post_quick_backtest(req: QuickBacktestRequest) -> dict[str, Any]:
    """
    Run a **synthetic** OHLCV replay: one LangGraph pass per bar, book simulated fills,
    write ``.runs/backtests/<run_id>/`` (trades, equity, ``iterations.jsonl``, summary) and flow events under ``.runs/``.
    """
    return _execute_quick_backtest(req)


class PresetBacktestRequest(BaseModel):
    preset_id: str = Field(DEFAULT_QUANT_STRATEGY_ID, min_length=1)
    ticker: str = Field("BTC/USDT", min_length=3)
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

    def work() -> None:
        def on_bar(i: int, total: int, snap: dict[str, Any]) -> None:
            if rid not in BACKTEST_JOBS:
                return
            BACKTEST_JOBS[rid].update(
                {
                    "status": "running",
                    "step": i + 1,
                    "total_steps": total,
                    "trade_count": snap["trade_count"],
                    "equity": snap["equity"],
                    "vetoed": snap["vetoed"],
                }
            )

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
        except HTTPException as e:
            detail = e.detail
            BACKTEST_JOBS[rid] = {
                "status": "failed",
                "error": detail if isinstance(detail, str) else str(detail),
            }
        except Exception as e:
            logger.exception("async preset backtest failed")
            BACKTEST_JOBS[rid] = {"status": "failed", "error": str(e)}

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": rid, "poll": f"/backtests/jobs/{rid}"}


@router.get("/backtests/jobs/{run_id}")
def get_backtest_job(run_id: str) -> dict[str, Any]:
    job = BACKTEST_JOBS.get(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job or run_id")
    return job


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
    result = run_multi_step_backtest(
        ticker=ticker,
        bars=bars,
        initial_cash=req.initial_cash,
        fee_bps=req.fee_bps,
        interval_sec=req.interval_sec,
        runs_dir=RUNS_DIR,
        max_steps=effective,
    )
    return {
        "run_id": result.run_id,
        "steps": result.steps,
        "trade_count": result.trade_count,
        "metrics": result.metrics,
        "evaluation": _evaluation_block(result=result, initial_cash=req.initial_cash),
        "paths": _backtest_paths_response(result),
        "capped": effective < min(want, len(bars)),
        "server_max_steps": cap,
    }


@router.get("/backtests/{run_id}/summary")
def get_backtest_summary(run_id: str) -> dict[str, Any]:
    summary_path = BACKTESTS_DIR / run_id / "summary.json"
    if not summary_path.is_file():
        raise HTTPException(status_code=404, detail="Unknown backtest run_id")
    return json.loads(summary_path.read_text(encoding="utf-8"))


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
