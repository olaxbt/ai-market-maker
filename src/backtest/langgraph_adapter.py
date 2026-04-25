"""LangGraph → PerpEngine adapter (perp-only).

Replaces the old multi-asset / single-asset logic.
The PerpEngine handles all execution; AIMM provides the per-bar signal.

No env vars. Lean wrapper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .engines.perp import PerpEngine


def run_perp_backtest(
    ticker: str,
    bars_by_symbol: dict[str, list[list[float]]],
    signal_fn: Callable,
    *,
    config: dict[str, Any] | None = None,
    run_id: str | None = None,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    cfg = dict(config or {})
    cfg.setdefault("leverage", 3.0)
    cfg.setdefault("taker_rate", 0.001)
    cfg.setdefault("maker_rate", 0.001)
    cfg.setdefault("slippage", 0.001)
    cfg.setdefault("funding_rate", 0.0001)

    engine = PerpEngine(cfg)
    return engine.run(
        bars_by_symbol=bars_by_symbol,
        signal_fn=signal_fn,
        run_id=run_id,
        runs_dir=runs_dir,
    )
