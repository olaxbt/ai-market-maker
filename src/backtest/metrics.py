from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


def _to_floats(xs: Iterable[float]) -> list[float]:
    return [float(x) for x in xs]


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Return max drawdown as a fraction (e.g. 0.25 = -25%)."""
    eq = _to_floats(equity_curve)
    if len(eq) < 2:
        return 0.0
    peak = eq[0]
    mdd = 0.0
    for x in eq:
        peak = max(peak, x)
        if peak > 0:
            dd = (peak - x) / peak
            mdd = max(mdd, dd)
    return float(mdd)


def returns_from_equity(equity_curve: Sequence[float]) -> list[float]:
    """Compute simple returns between consecutive equity points."""
    eq = _to_floats(equity_curve)
    rets: list[float] = []
    for a, b in zip(eq, eq[1:], strict=False):
        if a == 0:
            rets.append(0.0)
        else:
            rets.append((b - a) / a)
    return rets


def sharpe_ratio(returns: Sequence[float], *, periods_per_year: int = 365) -> float:
    """Annualized Sharpe ratio assuming zero risk-free rate."""
    r = _to_floats(returns)
    if len(r) < 2:
        return 0.0
    mean = sum(r) / len(r)
    var = sum((x - mean) ** 2 for x in r) / (len(r) - 1)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return float((mean / std) * math.sqrt(periods_per_year))


def win_rate(pnls: Sequence[float]) -> float:
    """Win rate as a fraction of pnl observations > 0."""
    xs = _to_floats(pnls)
    if not xs:
        return 0.0
    wins = sum(1 for x in xs if x > 0)
    return float(wins / len(xs))


@dataclass(frozen=True)
class BacktestMetrics:
    sharpe: float
    max_drawdown: float
    win_rate: float


def compute_basic_metrics(
    *,
    equity_curve: Sequence[float],
    trade_pnls: Sequence[float] | None = None,
    periods_per_year: int = 365,
) -> BacktestMetrics:
    rets = returns_from_equity(equity_curve)
    return BacktestMetrics(
        sharpe=sharpe_ratio(rets, periods_per_year=periods_per_year),
        max_drawdown=max_drawdown(equity_curve),
        win_rate=win_rate(trade_pnls or []),
    )
