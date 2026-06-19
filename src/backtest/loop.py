from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from config.app_settings import load_app_settings

from .engine import BacktestConfig, BacktestEngine

logger = logging.getLogger(__name__)


def _maybe_tail_slice(
    bars: Sequence[Sequence[Any]],
    *,
    max_steps: int | None,
) -> list[list[Any]]:
    """Keep only the trailing ``max_steps`` bars when capping simulated steps.

    OHLCV fetches usually return ``n_bars`` history but callers may ask to replay fewer
    (``max_steps`` from API merges). Without this, execution + progress totals use the
    full fetched length and overwrite job ``total_steps`` mid-run.
    """
    rows = [list(x) for x in bars]
    if max_steps is None:
        return rows
    limit = int(max_steps)
    if limit < 1 or len(rows) <= limit:
        return rows
    return rows[-limit:]


@dataclass(frozen=True)
class MultiStepResult:
    run_id: str
    steps: int
    interval_sec: int
    trade_count: int
    metrics: dict[str, Any]
    final_equity: float | None
    #: Buy-and-hold baseline vs same bars (see ``backtest.benchmark``).
    benchmark: Mapping[str, Any] | None

    summary_path: Path
    trades_path: Path
    equity_path: Path
    events_path: Path
    iterations_path: Path | None = None
    quality_report: dict[str, Any] | None = None
    resolved_config: dict[str, Any] | None = None


def run_multi_step_backtest(
    *,
    ticker: str,
    bars: Sequence[Sequence[Any]] | None = None,
    bars_by_symbol: Mapping[str, Sequence[Sequence[Any]]] | None = None,
    initial_cash: float = 10_000.0,
    initial_btc: float = 0.0,
    fee_bps: float = 10.0,
    interval_sec: int = 300,
    run_id: str | None = None,
    runs_dir: Path | None = None,
    max_steps: int | None = None,
    progress_callback: Callable[[int, int, dict[str, Any]], None] | None = None,
    export_bundle: bool = True,
    instrument: str | None = None,
    leverage: float | None = None,
    deploy_profile_weights: dict[str, float] | None = None,
    deploy_profile_id: str | None = None,
    deploy_arbitrator_mode: str | None = None,
    take_profit_pct: float = 0.0,
    stop_loss_pct: float = 0.0,
    max_hold_bars: int = 0,
    deploy_config: dict[str, Any] | None = None,
) -> MultiStepResult:
    """Run a deterministic multi-step backtest and persist artifacts under ``.runs/``."""
    app = load_app_settings()
    inst = (instrument or app.paper.instrument or "spot").strip().lower()
    lev = float(app.paper.leverage) if leverage is None else float(leverage)
    cfg = BacktestConfig(
        initial_cash_usd=float(initial_cash),
        initial_btc=float(initial_btc),
        fee_bps=float(fee_bps),
        max_steps=max_steps,
        export_bundle=bool(export_bundle),
        interval_sec=int(interval_sec),
        progress_callback=progress_callback,
        instrument=str(inst),
        leverage=max(1.0, lev),
        take_profit_pct=float(take_profit_pct),
        stop_loss_pct=float(stop_loss_pct),
        max_hold_bars=int(max_hold_bars),
    )
    if deploy_profile_weights:
        cfg.deploy_profile_weights = deploy_profile_weights  # type: ignore[attr-defined]
    if deploy_profile_id:
        cfg.deploy_profile_id = deploy_profile_id  # type: ignore[attr-defined]
    if deploy_arbitrator_mode:
        cfg.deploy_arbitrator_mode = deploy_arbitrator_mode  # type: ignore[attr-defined]
    engine = BacktestEngine(cfg)
    if bars_by_symbol is not None:
        raw = {str(sym): [list(x) for x in series] for sym, series in bars_by_symbol.items()}
        bbs = {sym: _maybe_tail_slice(rows, max_steps=max_steps) for sym, rows in raw.items()}
        res = engine.run(
            ticker=str(ticker),
            bars_by_symbol=bbs,
            run_id=run_id,
            runs_dir=runs_dir,
        )
    elif bars is not None:
        sliced = _maybe_tail_slice(bars, max_steps=max_steps)
        res = engine.run(ticker=str(ticker), bars=sliced, run_id=run_id, runs_dir=runs_dir)
    else:
        raise ValueError("run_multi_step_backtest requires bars or bars_by_symbol")

    paths = res.get("paths") or {}
    fe = res.get("final_equity")
    final_equity = float(fe) if isinstance(fe, (int, float)) else None
    ip = paths.get("iterations")
    iterations_path = Path(str(ip)) if ip else None
    raw_bench = res.get("benchmark")
    bench_out: dict[str, Any] | None = dict(raw_bench) if isinstance(raw_bench, dict) else None

    qual_report: dict[str, Any] | None = None
    summary_path = Path(str(paths.get("summary"))) if paths.get("summary") else None
    try:
        trades_path = Path(str(paths.get("trades"))) if paths.get("trades") else None
        trades: list[dict[str, Any]] = []
        if trades_path and trades_path.is_file():
            with trades_path.open(encoding="utf-8") as f:
                trades = [json.loads(line) for line in f if line.strip()]

        closes: list[float] = []
        if bars is not None:
            closes = [float(b[4]) for b in bars if len(b) > 4 and float(b[4]) > 0]
        elif bars_by_symbol is not None and ticker:
            primary = bars_by_symbol.get(ticker, [])
            closes = [float(b[4]) for b in primary if len(b) > 4 and float(b[4]) > 0]

        if closes and trades:
            from backtest.validation import generate_quality_report

            qual_report = generate_quality_report(
                close_prices=closes,
                total_bars=len(closes),
                trade_count=len(trades),
                profit_factor=float(res.get("metrics", {}).get("profit_factor") or 0),
                trades=trades,
            ).to_dict()

        if summary_path and summary_path.is_file():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if qual_report:
                summary["quality_report"] = qual_report
            if deploy_config:
                summary["resolved_config"] = dict(deploy_config)
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("quality-report post-process failed: %s", exc)
        qual_report = None

    return MultiStepResult(
        run_id=str(res.get("run_id") or ""),
        steps=int(res.get("steps") or 0),
        interval_sec=int(res.get("interval_sec") or interval_sec),
        trade_count=int(res.get("trade_count") or 0),
        metrics=dict(res.get("metrics") or {}),
        final_equity=final_equity,
        benchmark=bench_out,
        summary_path=summary_path,
        trades_path=Path(str(paths.get("trades"))),
        equity_path=Path(str(paths.get("equity"))),
        events_path=Path(str(paths.get("events"))),
        iterations_path=iterations_path,
        quality_report=qual_report,
        resolved_config=deploy_config or None,
    )
