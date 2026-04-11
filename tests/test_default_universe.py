from __future__ import annotations

from config.default_universe import DEFAULT_UNIVERSE_SYMBOLS, resolve_backtest_symbol_list


def test_builtin_list_includes_aio():
    assert "AIO/USDT" in DEFAULT_UNIVERSE_SYMBOLS


def test_resolve_primary_first_and_caps():
    u = resolve_backtest_symbol_list("ETH/USDT", max_symbols=3)
    assert u[0] == "ETH/USDT"
    assert len(u) == 3


def test_resolve_env_csv_overrides_tail():
    # Frozen single-source config: env overrides are removed. Ensure the helper still caps and
    # keeps primary first.
    u = resolve_backtest_symbol_list("BTC/USDT", max_symbols=5)
    assert u[0] == "BTC/USDT"
    assert len(u) <= 5
