from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from config.app_settings import load_app_settings

from .engine import BacktestConfig, BacktestEngine


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
) -> MultiStepResult:
    """Run a deterministic multi-step backtest and persist artifacts under `.runs/`."""
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
    )
    engine = BacktestEngine(cfg)
    if bars_by_symbol is not None:
        bbs = {str(sym): [list(x) for x in series] for sym, series in bars_by_symbol.items()}
        res = engine.run(
            ticker=str(ticker),
            bars_by_symbol=bbs,
            run_id=run_id,
            runs_dir=runs_dir,
        )
    elif bars is not None:
        res = engine.run(
            ticker=str(ticker), bars=[list(x) for x in bars], run_id=run_id, runs_dir=runs_dir
        )
    else:
        raise ValueError("run_multi_step_backtest requires bars or bars_by_symbol")

    paths = res.get("paths") or {}
    fe = res.get("final_equity")
    final_equity = float(fe) if isinstance(fe, (int, float)) else None
    ip = paths.get("iterations")
    iterations_path = Path(str(ip)) if ip else None
    raw_bench = res.get("benchmark")
    bench_out: dict[str, Any] | None = dict(raw_bench) if isinstance(raw_bench, dict) else None
    return MultiStepResult(
        run_id=str(res.get("run_id") or ""),
        steps=int(res.get("steps") or 0),
        interval_sec=int(res.get("interval_sec") or interval_sec),
        trade_count=int(res.get("trade_count") or 0),
        metrics=dict(res.get("metrics") or {}),
        final_equity=final_equity,
        benchmark=bench_out,
        summary_path=Path(str(paths.get("summary"))),
        trades_path=Path(str(paths.get("trades"))),
        equity_path=Path(str(paths.get("equity"))),
        events_path=Path(str(paths.get("events"))),
        iterations_path=iterations_path,
    )
