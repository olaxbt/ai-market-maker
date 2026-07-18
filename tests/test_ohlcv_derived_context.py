"""Tests for OHLCV-derived Nexus context in backtests."""

from __future__ import annotations

from backtest.ohlcv_derived_context import build_ohlcv_derived_nexus_context


def _fake_bars(n: int, *, start: float = 100.0, drift: float = 0.01) -> list[list[float]]:
    rows: list[list[float]] = []
    price = start
    for i in range(n):
        ts = 1_700_000_000_000 + i * 86_400_000
        price *= 1.0 + drift
        rows.append([ts, price, price, price, price, 1000.0])
    return rows


def test_builds_market_overview_from_ohlcv():
    sym = "BTC/USDT"
    md = {sym: {"ohlcv": _fake_bars(40, drift=0.005)}}
    ctx = build_ohlcv_derived_nexus_context(ticker=sym, universe=[sym], market_data=md)
    mo = ctx["endpoints"]["market_overview"]
    assert mo["ok"] is True
    data = mo["data"]
    assert data["success"] is True
    assert 10.0 <= float(data["systemic_liquidity_score"]) <= 95.0
    assert ctx["source"] == "ohlcv_derived"


def test_per_symbol_technical_block():
    sym = "ETH/USDT"
    md = {sym: {"ohlcv": _fake_bars(25, start=2000.0, drift=-0.002)}}
    ctx = build_ohlcv_derived_nexus_context(ticker=sym, universe=[sym], market_data=md)
    ta = ctx["per_symbol"]["by_symbol"][sym]["technical_analysis"]
    assert ta["ok"] is True
    assert ta["data"]["source"] == "ohlcv_derived"
    assert ta["data"]["trend"] in ("bullish", "bearish", "neutral")
