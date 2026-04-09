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


def periods_per_year_from_interval_sec(interval_sec: int) -> int:
    """Bars per year from bar spacing (for annualizing Sharpe / Sortino)."""
    sec = max(60, int(interval_sec))
    sec_per_year = 365.25 * 24 * 3600
    return max(1, int(round(sec_per_year / sec)))


def downside_deviation(returns: Sequence[float], *, mar: float = 0.0) -> float:
    """RMS of returns below the minimum acceptable return (MAR), full sample in denominator."""
    r = _to_floats(returns)
    if not r:
        return 0.0
    sq = [min(0.0, float(x) - mar) ** 2 for x in r]
    return float(math.sqrt(sum(sq) / len(r)))


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


def sortino_ratio(
    returns: Sequence[float],
    *,
    periods_per_year: int = 365,
    mar: float = 0.0,
) -> float:
    """Annualized Sortino (downside deviation vs MAR). Zero when no downside volatility."""
    r = _to_floats(returns)
    if len(r) < 2:
        return 0.0
    mean = sum(r) / len(r)
    dd = downside_deviation(r, mar=mar)
    if dd <= 1e-18:
        return 0.0
    return float(((mean - mar) / dd) * math.sqrt(periods_per_year))


def profit_factor(pnls: Sequence[float]) -> float | None:
    """Gross wins / gross losses on closed trade PnLs. ``None`` if no trades; capped when no losses."""
    xs = _to_floats(pnls)
    if not xs:
        return None
    wins = sum(x for x in xs if x > 0)
    losses = -sum(x for x in xs if x < 0)
    if losses < 1e-12:
        return None if abs(wins) < 1e-12 else 999.0
    return float(wins / losses)


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
    sortino: float
    max_drawdown: float
    win_rate: float
    profit_factor: float | None
    periods_per_year: int


def compute_basic_metrics(
    *,
    equity_curve: Sequence[float],
    trade_pnls: Sequence[float] | None = None,
    periods_per_year: int | None = None,
    interval_sec: int | None = None,
) -> BacktestMetrics:
    rets = returns_from_equity(equity_curve)
    ppy = (
        int(periods_per_year)
        if periods_per_year is not None
        else (periods_per_year_from_interval_sec(interval_sec) if interval_sec is not None else 365)
    )
    pnls = trade_pnls or []
    return BacktestMetrics(
        sharpe=sharpe_ratio(rets, periods_per_year=ppy),
        sortino=sortino_ratio(rets, periods_per_year=ppy),
        max_drawdown=max_drawdown(equity_curve),
        win_rate=win_rate(pnls),
        profit_factor=profit_factor(pnls),
        periods_per_year=ppy,
    )
