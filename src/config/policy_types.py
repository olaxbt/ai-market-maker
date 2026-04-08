"""Policy types (pure dataclasses, no env/IO).

Kept separate so tests and downstream modules can import the policy shape without
pulling in env parsing or file IO.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FundPolicy:
    """Per-deployment trading policy (hedge-fund-style knobs)."""

    portfolio_budget_usd: float
    stop_loss_pct: float
    take_profit_pct: float
    max_leverage: float
    min_confidence_directional: float

    # Order sizing caps (per-symbol add / scale-in).
    order_max_add_btc: float
    #: When set, each incremental buy is also capped by this **USD** notional (per-symbol).
    order_max_add_notional_usd: float | None

    #: Upper bound on each symbol's ``position_size`` in :mod:`agents.risk_management` (allocation weights).
    risk_position_cap_usd: float

    #: ``execution_intent`` reporting: ``cash * this * max_leverage`` (engine uses :attr:`max_leverage` separately).
    intent_notional_fraction: float

    # Rule overlay thresholds (Tier-1 tape / quant bridge).
    rule_sentiment_buy_min: float
    rule_sentiment_sell_below: float

    #: When ``False``, bearish thesis on a **flat** book does not emit ``SELL`` (long-only / no short).
    allows_short: bool

    #: Minimum bars between fills (per-symbol). Used in both backtest and live to prevent churn.
    trade_cooldown_bars: int

    # Exposure shaping (regime-aware).
    bull_min_target_fraction: float
    bear_max_target_fraction: float

    # Portfolio-level circuit breaker.
    risk_max_drawdown_stop: float | None
    risk_kill_switch_cooldown_bars: int


__all__ = ["FundPolicy"]
