"""Buy-and-hold baseline vs the same OHLCV window (strategy accountability).

``benchmark_asset_return_pct`` is pure spot move (first→last close), no costs.
``benchmark_buy_hold_equity_return_pct`` is one buy at the first close and one sell
at the last close using the same fee/slippage model as :class:`backtest.engine.BacktestEngine`
(full fills; no partial-fill noise).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def compute_buy_hold_benchmark(
    *,
    initial_cash_usd: float,
    bars: Sequence[Sequence[Any]],
    fee_bps: float,
    slippage_bps: float,
) -> dict[str, float]:
    """Return benchmark stats; empty-ish dict if ``bars`` too short or bad prices."""
    out: dict[str, float] = {}
    if not bars or len(bars) < 2:
        return out
    try:
        p0 = float(bars[0][4])
        p1 = float(bars[-1][4])
    except (IndexError, TypeError, ValueError):
        return out
    if p0 <= 0 or p1 <= 0 or initial_cash_usd <= 0:
        return out

    asset_ret = (p1 / p0 - 1.0) * 100.0
    out["benchmark_asset_return_pct"] = round(asset_ret, 6)

    slip = float(slippage_bps) / 10000.0
    fee_r = float(fee_bps) / 10000.0
    buy_fill = p0 * (1.0 + slip)
    sell_fill = p1 * (1.0 - slip)
    denom = buy_fill * (1.0 + fee_r)
    if denom <= 0:
        return out
    qty = float(initial_cash_usd) / denom
    final_cash = sell_fill * qty * (1.0 - fee_r)
    bh_ret = (final_cash - float(initial_cash_usd)) / float(initial_cash_usd) * 100.0
    out["benchmark_buy_hold_equity_return_pct"] = round(bh_ret, 6)
    out["benchmark_first_close"] = round(p0, 8)
    out["benchmark_last_close"] = round(p1, 8)
    return out


def compute_equal_weight_buy_hold_benchmark(
    *,
    initial_cash_usd: float,
    bars_by_symbol: Mapping[str, Sequence[Sequence[Any]]],
    fee_bps: float,
    slippage_bps: float,
) -> dict[str, Any]:
    """Split cash equally, buy each symbol at first close, sell at last (same fee/slippage as engine)."""
    out: dict[str, Any] = {}
    if not bars_by_symbol or initial_cash_usd <= 0:
        return out
    syms = sorted(bars_by_symbol.keys())
    per = float(initial_cash_usd) / len(syms)
    slip = float(slippage_bps) / 10000.0
    fee_r = float(fee_bps) / 10000.0
    final_total = 0.0
    used = 0
    for sym in syms:
        bars = bars_by_symbol[sym]
        if not bars or len(bars) < 2:
            continue
        try:
            p0 = float(bars[0][4])
            p1 = float(bars[-1][4])
        except (IndexError, TypeError, ValueError):
            continue
        if p0 <= 0 or p1 <= 0:
            continue
        buy_fill = p0 * (1.0 + slip)
        sell_fill = p1 * (1.0 - slip)
        denom = buy_fill * (1.0 + fee_r)
        if denom <= 0:
            continue
        qty = per / denom
        final_total += sell_fill * qty * (1.0 - fee_r)
        used += 1
    if used == 0:
        return out
    ew_ret = (final_total - float(initial_cash_usd)) / float(initial_cash_usd) * 100.0
    out["benchmark_equal_weight_equity_return_pct"] = round(ew_ret, 6)
    out["benchmark_equal_weight_leg_count"] = used
    out["benchmark_equal_weight_symbols"] = list(syms)
    return out


__all__ = ["compute_buy_hold_benchmark", "compute_equal_weight_buy_hold_benchmark"]
