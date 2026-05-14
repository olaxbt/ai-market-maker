"""Exchange-shaped trade rows and consumer helpers."""

from __future__ import annotations

from backtest.exchange_trade_format import (
    normalize_trade_row_for_api,
    trade_row_fee_usd,
    trade_row_side,
    trade_row_symbol_for_analytics,
)


def test_normalize_trade_row_for_api_adds_side_step_fee_alias() -> None:
    row = {
        "symbol": "BTCUSDT",
        "isBuyer": True,
        "time": 1_700_000_000_000,
        "commission": "0.12",
        "_sim": {"step": 42, "ccxt_symbol": "BTC/USDT", "venue": "sim"},
    }
    out = normalize_trade_row_for_api(row)
    assert out["side"] == "buy"
    assert out["step"] == 42
    assert out["ts_ms"] == 1_700_000_000_000
    assert out["ts"] == 1_700_000_000_000 / 1000.0
    assert out["fee_usd"] == 0.12
    assert out["symbol"] == "BTCUSDT"


def test_trade_row_fee_legacy_fee_usd() -> None:
    assert trade_row_fee_usd({"fee_usd": 1.5}) == 1.5
    assert trade_row_fee_usd({"commission": "2"}) == 2.0


def test_normalize_perp_ledger_row_direction_and_exit_ts() -> None:
    row = {
        "symbol": "SOL/USDT",
        "direction": -1,
        "exit_ts_ms": 1_770_681_600_000,
        "exit_bar_index": 7,
        "entry_price": 90.0,
        "exit_price": 91.0,
        "size": 1.0,
        "commission": 1.0,
    }
    out = normalize_trade_row_for_api(row)
    assert out["side"] == "sell"
    assert out["step"] == 7
    assert out["ts_ms"] == 1_770_681_600_000
    assert abs(out["ts"] - 1_770_681_600_000 / 1000.0) < 1e-6


def test_trade_row_side_and_symbol() -> None:
    assert trade_row_side({"side": "sell"}) == "sell"
    assert trade_row_side({"isBuyer": False}) == "sell"
    assert trade_row_side({"direction": 1}) == "buy"
    assert trade_row_side({"direction": -1}) == "sell"
    assert (
        trade_row_symbol_for_analytics({"symbol": "X", "_sim": {"ccxt_symbol": "ETH/USDT"}})
        == "ETH/USDT"
    )
