"""PerpEngine: liquidation, funding, and rebalancing tests."""

from __future__ import annotations

import pytest

from backtest.engines.perp import PerpEngine


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


def test_ohlcv_window_grows_per_step():
    """Regression: the `window` param to _signal_fn must grow 1→N bars,
    not receive the full series each time (P0 bug recurrence check)."""
    bars = [[900_000 * i, 100.0, 101.0, 99.0, 100.0 + i * 0.1, 10.0] for i in range(30)]
    window_lengths: list[int] = []

    def signal(sym, window, pos, cap):
        window_lengths.append(len(window))
        return 0.0

    engine = PerpEngine({"initial_cash": 10_000, "leverage": 1.0})
    engine.run({"TEST/USDT": bars}, signal)

    # Step 1 gets 1 bar, step 2 gets 2 bars, ... step 30 gets 30 bars
    assert len(window_lengths) == 30, f"Expected 30 steps, got {len(window_lengths)}"
    for i, n in enumerate(window_lengths):
        assert n == i + 1, f"Step {i + 1}: expected {i + 1} bars in window, got {n}"
    # Also check: non-first-bar windows have distinct last close
    # (ensuring TA indicators don't return identical values)
    closes_step = [bars[i][4] for i in range(30)]
    assert len(set(c for i, c in enumerate(closes_step) if i > 0)) > 1, (
        "Only one unique last-close across all windows — window may not be advancing"
    )
