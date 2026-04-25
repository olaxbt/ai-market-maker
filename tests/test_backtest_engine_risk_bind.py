"""PerpEngine: liquidation, funding, and rebalancing tests."""

from __future__ import annotations

import pytest

from backtest.engines.perp import PerpEngine, FUNDING_HOURS


def test_basic_long_profits():
    """Simple upward trend → long makes profit."""
    bars = [[900_000 * i, 100.0, 101.0, 99.0, 100.0 + i * 0.5, 10.0] for i in range(30)]

    def signal(sym, window, pos, cap):
        return 1.0

    engine = PerpEngine({"initial_cash": 10_000, "leverage": 1.0})
    result = engine.run({"BTC/USDT": bars}, signal)
    assert result["metrics"]["total_trades"] > 0
    assert result["metrics"]["total_return_pct"] > 0


def test_liquidation_triggers():
    """10x long on a crash → gets liquidated."""
    bars = [
        [900_000 * i, 100.0 - i * 6.0, 101.0 - i * 6.0, 99.0 - i * 6.0, 100.0 - i * 6.0, 10.0]
        for i in range(20)
    ]

    def signal(sym, window, pos, cap):
        if len(window) < 2:
            return 0.0
        return 1.0  # long

    engine = PerpEngine({"initial_cash": 10_000, "leverage": 10.0})
    engine.run({"BTC/USDT": bars}, signal)

    liq_trades = [t for t in engine.trades if t.exit_reason == "liquidation"]
    assert len(liq_trades) >= 1, "Expected at least 1 liquidation"


def test_short_profits_on_downtrend():
    """Short position profits on a downtrend."""
    bars = [[900_000 * i, 100.0, 101.0, 99.0, 100.0 - i * 0.5, 10.0] for i in range(30)]

    def signal(sym, window, pos, cap):
        return -1.0  # always short

    engine = PerpEngine({"initial_cash": 10_000, "leverage": 1.0})
    result = engine.run({"BTC/USDT": bars}, signal)
    assert result["metrics"]["total_trades"] > 0
    assert result["metrics"]["total_return_pct"] > 0, "Short should profit on downtrend"


def test_funding_fee_applies():
    """Funding fees are deducted."""
    bars = [[900_000 * i, 100.0, 101.0, 99.0, 100.0, 10.0] for i in range(100)]

    def signal(sym, window, pos, cap):
        if len(window) < 2:
            return 0.0
        return 0.8

    cfg = {"initial_cash": 10_000, "leverage": 3.0, "funding_rate": 0.001}
    engine = PerpEngine(cfg)
    engine.run({"BTC/USDT": bars}, signal)

    capital_used = cfg["initial_cash"] - engine.capital
    assert capital_used > 0, "Funding fees should reduce capital"


def test_direction_change_flips_position():
    """Changing signal direction closes old → opens new."""
    bars = [[900_000 * i, 100.0, 101.0, 99.0, 100.0, 10.0] for i in range(20)]

    calls = []

    def signal(sym, window, pos, cap):
        calls.append(len(window))
        if len(window) < 3:
            return 0.0
        return 1.0 if len(window) < 10 else -1.0

    engine = PerpEngine({"initial_cash": 10_000, "leverage": 3.0})
    engine.run({"BTC/USDT": bars}, signal)

    trade_count = len(engine.trades)
    assert trade_count >= 2, f"Expected >= 2 trades for flip, got {trade_count}"


def test_no_signal_no_trades():
    """Signal stays 0 → no positions opened."""
    bars = [[900_000 * i, 100.0, 101.0, 99.0, 100.0, 10.0] for i in range(20)]

    def signal(sym, window, pos, cap):
        return 0.0

    engine = PerpEngine({"initial_cash": 10_000})
    engine.run({"BTC/USDT": bars}, signal)

    assert len(engine.trades) == 0
    assert engine.capital == pytest.approx(10_000.0, abs=1e-6)


def test_multi_symbol_backtest():
    """Multi-symbol alignment works."""
    bars_btc = [[900_000 * i, 100.0, 101.0, 99.0, 100.0 + i * 0.3, 10.0] for i in range(20)]
    bars_eth = [[900_000 * i, 10.0, 10.1, 9.9, 10.0 + i * 0.05, 100.0] for i in range(20)]

    def signal(sym, window, pos, cap):
        return 0.5

    engine = PerpEngine({"initial_cash": 10_000, "leverage": 1.0})
    result = engine.run({"BTC/USDT": bars_btc, "ETH/USDT": bars_eth}, signal)

    assert result["metrics"]["total_trades"] > 0
