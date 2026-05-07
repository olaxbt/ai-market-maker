"""Tests for HyperliquidAdapter (Task 3).

All tests use FakeHyperliquidClient — no real SDK, no real API keys.
_SdkHyperliquidClient is tested only for the RuntimeError path.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from adapters.hyperliquid_adapter import (
    FakeHyperliquidClient,
    HyperliquidAdapter,
    _SdkHyperliquidClient,
    normalize_hl_symbol,
)
from config.exchange_env import ExchangeConfig


def _make_config(**overrides: Any) -> ExchangeConfig:
    defaults: dict[str, Any] = dict(
        exchange_name="hyperliquid",
        testnet=True,
        dry_run=False,
        hyperliquid_api_key="test-wallet-addr",
        hyperliquid_secret="test-secret-DO-NOT-EXPOSE",
        hyperliquid_api_base=None,
    )
    defaults.update(overrides)
    return ExchangeConfig(**defaults)


def test_protocol_conformance_all_five_methods_exist():
    adapter = HyperliquidAdapter(config=_make_config(), client=FakeHyperliquidClient())
    for method in (
        "place_order",
        "cancel_order",
        "get_order_status",
        "get_portfolio_health",
        "fetch_market_depth",
    ):
        assert callable(getattr(adapter, method, None)), f"Missing method: {method}"


def test_dry_run_place_order_does_not_call_client():
    fake = FakeHyperliquidClient()
    adapter = HyperliquidAdapter(config=_make_config(dry_run=True), client=fake)
    result = adapter.place_order(
        symbol="BTC/USDT",
        side="buy",
        qty=0.1,
        order_type="limit",
        price=50000.0,
        client_order_id="coid-dry-1",
    )
    assert result["status"] == "accepted"
    assert result["exchange_order_id"] is None
    assert result["symbol"] == "BTC/USDT"
    assert result["side"] == "buy"
    assert result["qty"] == 0.1
    assert result["price"] == 50000.0
    assert result["filled_qty"] == 0.0
    assert result["raw"] == {"dry_run": True}
    assert len(fake.submitted_orders) == 0


def test_place_order_accepted_via_fake_client():
    fake = FakeHyperliquidClient(default_response="accepted")
    adapter = HyperliquidAdapter(config=_make_config(), client=fake)
    result = adapter.place_order(
        symbol="ETH/USDT",
        side="buy",
        qty=1.0,
        order_type="limit",
        price=3000.0,
        client_order_id="coid-1",
    )
    assert result["status"] == "accepted"
    assert result["exchange_order_id"] is not None
    assert result["exchange_order_id"].startswith("fake-oid-")
    assert result["symbol"] == "ETH/USDT"
    assert result["side"] == "buy"
    assert result["qty"] == 1.0
    assert result["price"] == 3000.0
    assert len(fake.submitted_orders) == 1
    assert fake.submitted_orders[0]["coin"] == "ETH"
    assert fake.submitted_orders[0]["is_buy"] is True
    assert "error" not in result


def test_place_order_rejected_via_fake_client():
    fake = FakeHyperliquidClient(default_response="rejected")
    adapter = HyperliquidAdapter(config=_make_config(), client=fake)
    result = adapter.place_order(
        symbol="BTC/USDT",
        side="sell",
        qty=0.05,
        order_type="limit",
        price=60000.0,
        client_order_id="coid-2",
    )
    assert result["status"] == "rejected"
    assert result["exchange_order_id"] is None
    assert "error" in result
    assert "insufficient margin" in result["error"]
    assert result["raw"]["status"] == "rejected"


def test_place_order_timeout_maps_to_unknown():
    fake = FakeHyperliquidClient(default_response="timeout")
    adapter = HyperliquidAdapter(config=_make_config(), client=fake)
    result = adapter.place_order(
        symbol="BTC/USDT",
        side="buy",
        qty=0.1,
        order_type="market",
        price=None,
        client_order_id=None,
    )
    assert result["status"] == "unknown"
    assert result["raw"]["status"] == "timeout"


def test_cancel_order_returns_cancelled():
    fake = FakeHyperliquidClient()
    adapter = HyperliquidAdapter(config=_make_config(), client=fake)
    result = adapter.cancel_order(symbol="BTC/USDT", exchange_order_id="oid-99")
    assert result["status"] == "cancelled"
    assert result["exchange_order_id"] == "oid-99"
    assert result["symbol"] == "BTC/USDT"
    assert result["side"] == ""
    assert result["qty"] == 0.0
    assert len(fake.cancelled_orders) == 1
    assert fake.cancelled_orders[0]["coin"] == "BTC"
    assert fake.cancelled_orders[0]["oid"] == "oid-99"


@pytest.mark.parametrize(
    "fake_response,expected_status",
    [
        ("accepted", "accepted"),
        ("filled", "filled"),
        ("cancelled", "cancelled"),
        ("rejected", "rejected"),
        ("partial", "partially_filled"),
    ],
)
def test_get_order_status_maps_all_statuses(fake_response: str, expected_status: str):
    fake = FakeHyperliquidClient(default_response=fake_response)
    adapter = HyperliquidAdapter(config=_make_config(), client=fake)
    result = adapter.get_order_status(symbol="BTC/USDT", exchange_order_id="oid-1")
    assert result["status"] == expected_status
    assert result["exchange_order_id"] == "oid-1"
    assert result["symbol"] == "BTC/USDT"


def test_fetch_open_orders_returns_list():
    fake = FakeHyperliquidClient()
    adapter = HyperliquidAdapter(config=_make_config(), client=fake)
    adapter.place_order(
        symbol="BTC/USDT",
        side="buy",
        qty=0.1,
        order_type="limit",
        price=50000.0,
        client_order_id="c1",
    )
    adapter.place_order(
        symbol="ETH/USDT",
        side="sell",
        qty=1.0,
        order_type="limit",
        price=3000.0,
        client_order_id="c2",
    )
    orders = adapter.fetch_open_orders()
    assert isinstance(orders, list)
    assert len(orders) == 2


def test_fetch_positions_returns_list():
    fake = FakeHyperliquidClient()
    adapter = HyperliquidAdapter(config=_make_config(), client=fake)
    positions = adapter.fetch_positions()
    assert isinstance(positions, list)


def test_healthcheck_returns_ok():
    fake = FakeHyperliquidClient()
    adapter = HyperliquidAdapter(config=_make_config(), client=fake)
    result = adapter.healthcheck()
    assert result["status"] == "ok"


def test_missing_sdk_raises_runtime_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "hyperliquid", None)
    monkeypatch.setitem(sys.modules, "hyperliquid.exchange", None)
    monkeypatch.setitem(sys.modules, "hyperliquid.info", None)
    config = _make_config()
    with pytest.raises(RuntimeError, match="hyperliquid-python-sdk"):
        _SdkHyperliquidClient(config)


def test_repr_does_not_expose_secret():
    adapter = HyperliquidAdapter(
        config=_make_config(hyperliquid_secret="VERY-SECRET-KEY-XYZ"),
        client=FakeHyperliquidClient(),
    )
    r = repr(adapter)
    assert "VERY-SECRET-KEY-XYZ" not in r


@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("BTC/USDT", "BTC"),
        ("BTC-USD", "BTC"),
        ("BTCUSDT", "BTC"),
        ("BTC", "BTC"),
        ("ETH/USDT", "ETH"),
    ],
)
def test_normalize_hl_symbol_all_cases(symbol: str, expected: str):
    assert normalize_hl_symbol(symbol) == expected
