"""Named backtest presets: default parameters and copy for the strategy API and UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_QUANT_STRATEGY_ID = "macd_risk_v1"


@dataclass(frozen=True)
class StrategyPreset:
    id: str
    title: str
    description: str
    # Defaults for POST /backtests/quick
    n_bars: int = 500
    interval_sec: int = 300
    max_steps: int = 200
    seed: int = 1
    fee_bps: float = 10.0
    initial_cash: float = 10_000.0


PRESETS: dict[str, StrategyPreset] = {
    DEFAULT_QUANT_STRATEGY_ID: StrategyPreset(
        id=DEFAULT_QUANT_STRATEGY_ID,
        title="Orchestrated multi-agent workflow (default)",
        description=(
            "Each bar invokes the full LangGraph: tier-1 perception desks (market structure, "
            "sentiment, statistical signals, and a reproducible quant feature layer) feed tier-2 "
            "bull/bear debate and a signal arbitrator, then portfolio proposal, risk guard, and "
            "execution. The default arbitrator is rule-based for determinism; set "
            "AI_MARKET_MAKER_USE_LLM for an LLM synthesis path. Backtests use synthetic OHLCV so "
            "runs stay comparable and the same trace contract applies as live Nexus streams."
        ),
        n_bars=500,
        interval_sec=300,
        max_steps=200,
        seed=1,
    ),
}


def get_preset(preset_id: str) -> StrategyPreset:
    key = (preset_id or "").strip() or DEFAULT_QUANT_STRATEGY_ID
    if key not in PRESETS:
        raise KeyError(f"Unknown strategy preset {key!r}. Known: {list(PRESETS)}")
    return PRESETS[key]


def list_presets() -> list[dict[str, Any]]:
    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "defaults": {
                "n_bars": p.n_bars,
                "interval_sec": p.interval_sec,
                "max_steps": p.max_steps,
                "seed": p.seed,
                "fee_bps": p.fee_bps,
                "initial_cash": p.initial_cash,
            },
        }
        for p in PRESETS.values()
    ]


def merge_preset_quick_request(
    preset_id: str,
    *,
    ticker: str | None = None,
    n_bars: int | None = None,
    interval_sec: int | None = None,
    max_steps: int | None = None,
    seed: int | None = None,
    fee_bps: float | None = None,
    initial_cash: float | None = None,
) -> dict[str, Any]:
    """Build kwargs compatible with :func:`backtest_routes.post_quick_backtest` body."""
    p = get_preset(preset_id)
    return {
        "ticker": ticker or "BTC/USDT",
        "n_bars": n_bars if n_bars is not None else p.n_bars,
        "interval_sec": interval_sec if interval_sec is not None else p.interval_sec,
        "max_steps": max_steps if max_steps is not None else p.max_steps,
        "seed": seed if seed is not None else p.seed,
        "fee_bps": fee_bps if fee_bps is not None else p.fee_bps,
        "initial_cash": initial_cash if initial_cash is not None else p.initial_cash,
    }


def quant_trace_meta() -> dict[str, Any]:
    """Embedded in Quant agent JSON for UI / operator transparency."""
    p = PRESETS[DEFAULT_QUANT_STRATEGY_ID]
    return {
        "preset_id": p.id,
        "title": p.title,
        "signals": [
            "MACD vs signal line — regime and crossover (TA-Lib)",
            "Volume vs short rolling mean (activity)",
        ],
        "portfolio": "One tier-1 desk; outputs merge with other desks before debate and execution.",
    }
