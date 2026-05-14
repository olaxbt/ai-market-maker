"""Named backtest presets: default parameters and copy for the strategy API and UI.

Three styles:
  - Momentum (trend-following)
  - Mean reversion (counter-trend)
  - All-weather (balanced / adaptive)

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_QUANT_STRATEGY_ID = "momentum"


@dataclass(frozen=True)
class StrategyPreset:
    id: str
    title: str
    description: str
    category: str = "balanced"
    coin: str = ""
    # Chain-of-thought snippet shown in card UI
    reasoning_preview: str = ""
    # Defaults for POST /backtests/quick
    n_bars: int = 500
    interval_sec: int = 300
    max_steps: int = 200
    seed: int = 1
    fee_bps: float = 10.0
    initial_cash: float = 10_000.0


PRESETS: dict[str, StrategyPreset] = {
    "momentum": StrategyPreset(
        id="momentum",
        title="Momentum (trend-following)",
        category="trend",
        coin="arrow-up",
        reasoning_preview=(
            "1. Compute fast/slow EMA cross (12/26) — detect trend direction. "
            "2. RSI(14) > 60 confirms momentum, not overbought. "
            "3. Volume > 20-bar SMA validates conviction. "
            "4. ADX > 25 filters out chop zones. "
            "5. Enter with 0.6 notional fraction when all 4 conditions align. "
            "6. Exit when EMA cross reverses or trailing ATR stop hit."
        ),
        description=(
            "Trend-following strategy that enters on EMA crossovers confirmed by "
            "RSI momentum, volume surge, and ADX trend strength. Exits on "
            "crossover reversal or trailing ATR stop. Optimised for trending "
            "markets with low chop."
        ),
        n_bars=500,
        interval_sec=300,
        max_steps=200,
        seed=1,
    ),
    "mean_reversion": StrategyPreset(
        id="mean_reversion",
        title="Mean reversion (counter-trend)",
        category="mean_reversion",
        coin="arrow-down",
        reasoning_preview=(
            "1. Bollinger Bands (20,2) — price below lower band signals oversold. "
            "2. RSI(14) < 30 confirms oversold regime. "
            "3. Volume < 10-bar SMA indicates climax exhaustion. "
            "4. Entry when price closes back inside the band. "
            "5. Risk: trade is counter-trend. Use 0.25 notional fraction. "
            "6. Exit at upper BB or profit target = 1.5× ATR."
        ),
        description=(
            "Counter-trend strategy that buys oversold bounces off Bollinger "
            "Band lower touch, confirmed by RSI exhaustion and volume fade. "
            "Tight risk control: half momentum sizing, profit target based on "
            "average true range."
        ),
        n_bars=400,
        interval_sec=300,
        max_steps=150,
        seed=2,
    ),
    "all_weather": StrategyPreset(
        id="all_weather",
        title="All-weather (balanced / adaptive)",
        category="balanced",
        coin="layers",
        reasoning_preview=(
            "1. Multi-frame signal: EMA slope (trend) + RSI percentile (mean-reversion bias). "
            "2. Weighted blend: momentum_weight = ADX / 100, reversion_weight = 1 - momentum_weight. "
            "3. Position size from Kelly-approximation based on win-rate lookback. "
            "4. Exit logic: profitable trend fades → scale out; stop widens during volatility. "
            "5. Minimum 3 bars between trades to avoid whipsaw. "
            "6. Adaptive — switches between trend and reversion depending on market regime."
        ),
        description=(
            "Adaptive strategy that blends momentum and mean-reversion signals "
            "proportional to market regime (ADX). Uses Kelly-inspired position "
            "sizing, dynamic stops, and a cooldown filter. Designed for any "
            "market environment, hence all-weather."
        ),
        n_bars=600,
        interval_sec=300,
        max_steps=250,
        seed=3,
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
            "category": p.category,
            "reasoning_preview": p.reasoning_preview,
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
    exchange_id: str | None = None,
    n_bars: int | None = None,
    interval_sec: int | None = None,
    max_steps: int | None = None,
    seed: int | None = None,
    fee_bps: float | None = None,
    initial_cash: float | None = None,
) -> dict[str, Any]:
    """Build kwargs compatible with :func:`backtest_routes.post_quick_backtest` body."""
    p = get_preset(preset_id)
    out: dict[str, Any] = {
        "ticker": ticker or "BTC/USDT",
        "n_bars": n_bars if n_bars is not None else p.n_bars,
        "interval_sec": interval_sec if interval_sec is not None else p.interval_sec,
        "max_steps": max_steps if max_steps is not None else p.max_steps,
        "seed": seed if seed is not None else p.seed,
        "fee_bps": fee_bps if fee_bps is not None else p.fee_bps,
        "initial_cash": initial_cash if initial_cash is not None else p.initial_cash,
    }
    if exchange_id is not None:
        ex = str(exchange_id).strip()
        if ex:
            out["exchange_id"] = ex
    return out


def quant_trace_meta() -> dict[str, Any]:
    """Embedded in Quant agent JSON for UI / operator transparency."""
    p = PRESETS[DEFAULT_QUANT_STRATEGY_ID]
    return {
        "preset_id": p.id,
        "title": p.title,
        "signals": [
            "EMA cross (12/26) — trend direction",
            "RSI(14) — momentum / overbought-oversold",
            "ADX(14) — trend strength / chop filter",
            "Bollinger Bands (20,2) — mean-reversion levels",
        ],
        "portfolio": "Adaptive blend of momentum and mean-reversion desks; position sized with Kelly approximation.",
    }
