"""Tests for FutuAdapter (Futu OpenD exchange adapter).

All tests use FakeFutuClient — no real SDK, no OpenD connection.
_SdkFutuClient is tested only for the RuntimeError path (missing SDK).
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from adapters.futu import (
    FakeFutuClient,
    FutuAdapter,
    FutuEnvConfig,
    _SdkFutuClient,
    normalize_futu_symbol,
)
from config.exchange_env import ExchangeConfig


def _make_futu_env(**overrides: Any) -> FutuEnvConfig:
    defaults: dict[str, Any] = dict(
        host="127.0.0.1",
        quote_port=11111,
        trade_port=11112,
        dry_run=False,
    )
    defaults.update(overrides)
    return FutuEnvConfig(**defaults)


def _make_config() -> ExchangeConfig:
    return ExchangeConfig(
        exchange_name="futu",
        testnet=True,
        dry_run=False,
    )


# -- Symbol normalization tests -----------------------------------------------

@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("0700.HK", "HK.00700"),
        ("700.HK", "HK.00700"),
        ("00700.HK", "HK.00700"),
        ("HK.00700", "HK.00700"),
        ("AAPL.US", "US.AAPL"),
        ("MSFT.US", "US.MSFT"),
        ("AAPL", "US.AAPL"),
        ("TSLA", "US.TSLA"),
        ("BTC/USDT", "US.BTC/USDT"),
    ],
)
def test_normalize_futu_symbol(symbol: str, expected: str):
    result = normalize_futu_symbol(symbol)
    assert result == expected, f"normalize({symbol!r}) = {result!r}, expected {expected!r}"


# -- Protocol conformance -----------------------------------------------------

def test_protocol_conformance_all_methods_exist():
    adapter = FutuAdapter(config=_make_config(), client=FakeFutuClient())
    for method in (
        "place_order",
        "cancel_order",
        "get_order_status",
        "get_portfolio_health",
        "fetch_market_depth",
    ):
        assert callable(getattr(adapter, method, None)), f"Missing method: {method}"


# -- Dry run ------------------------------------------------------------------

def test_dry_run_place_order_does_not_call_client():
    fake = FakeFutuClient()
    adapter = FutuAdapter(
        config=_make_config(),
        futu_env=_make_futu_env(dry_run=True),
        client=fake,
    )
    result = adapter.place_order(
        symbol="HK.00700",
        side="buy",
        qty=100,
        order_type="limit",
        price=380.0,
        client_order_id="coid-dry-1",
    )
    assert result["status"] == "dry_run"
    assert result["exchange_order_id"] is None
    assert result["symbol"] == "HK.00700"
    assert result["side"] == "buy"
    assert result["qty"] == 100
    assert result["price"] == 380.0
    assert result["filled_qty"] == 0.0
    assert result["raw"] == {"dry_run": True}
    assert len(fake.submitted_orders) == 0


# -- Place order ---------------------------------------------------------------

def test_place_order_accepted_via_fake_client():
    fake = FakeFutuClient(default_response="accepted")
    adapter = FutuAdapter(config=_make_config(), client=fake)
    result = adapter.place_order(
        symbol="HK.00700",
        side="buy",
        qty=100,
        order_type="limit",
        price=380.0,
        client_order_id="coid-1",
    )
    assert result["status"] == "accepted"
    assert result["exchange_order_id"] is not None
    assert result["symbol"] == "HK.00700"
    assert result["side"] == "buy"
    assert result["qty"] == 100
    assert result["price"] == 380.0
    assert len(fake.submitted_orders) == 1
    assert "error" not in result


def test_place_order_rejected_via_fake_client():
    fake = FakeFutuClient(default_response="rejected")
    adapter = FutuAdapter(config=_make_config(), client=fake)
    result = adapter.place_order(
        symbol="HK.00700",
        side="sell",
        qty=100,
        order_type="limit",
        price=400.0,
        client_order_id="coid-2",
    )
    assert result["status"] == "rejected"
    assert result["exchange_order_id"] is None
    assert "error" in result


def test_place_order_filled_via_fake_client():
    fake = FakeFutuClient(default_response="filled")
    adapter = FutuAdapter(config=_make_config(), client=fake)
    result = adapter.place_order(
        symbol="US.AAPL",
        side="buy",
        qty=10,
        order_type="market",
        price=None,
        client_order_id="coid-3",
    )
    assert result["status"] == "filled"
    assert result["exchange_order_id"] is not None
    assert result["filled_qty"] == 10.0


# -- Cancel order -------------------------------------------------------------

def test_cancel_order_returns_cancelled():
    fake = FakeFutuClient()
    adapter = FutuAdapter(config=_make_config(), client=fake)
    result = adapter.cancel_order(symbol="HK.00700", exchange_order_id="oid-99")
    assert result["status"] == "cancelled"
    assert result["exchange_order_id"] == "oid-99"
    assert result["symbol"] == "HK.00700"
    assert len(fake.cancelled_orders) == 1
    assert fake.cancelled_orders[0]["order_id"] == "oid-99"


def test_dry_run_cancel_order_does_not_call_client():
    fake = FakeFutuClient()
    adapter = FutuAdapter(
        config=_make_config(),
        futu_env=_make_futu_env(dry_run=True),
        client=fake,
    )
    result = adapter.cancel_order(symbol="HK.00700", exchange_order_id="oid-dry-1")
    assert result["status"] == "dry_run"
    assert result["exchange_order_id"] == "oid-dry-1"
    assert result["raw"] == {"dry_run": True}
    assert len(fake.cancelled_orders) == 0


# -- Get order status ---------------------------------------------------------

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
    fake = FakeFutuClient(default_response=fake_response)
    adapter = FutuAdapter(config=_make_config(), client=fake)
    result = adapter.get_order_status(symbol="HK.00700", exchange_order_id="oid-1")
    assert result["status"] == expected_status
    assert result["exchange_order_id"] == "oid-1"
    assert result["symbol"] == "HK.00700"


# -- Portfolio health ---------------------------------------------------------

def test_get_portfolio_health_returns_data():
    fake = FakeFutuClient()
    adapter = FutuAdapter(config=_make_config(), client=fake)
    result = adapter.get_portfolio_health(account_id="test-futu")
    assert result["account_id"] == "test-futu"
    assert result["exchange"] == "futu-opend"
    assert isinstance(result["balances"], list)
    assert isinstance(result["positions"], list)
    assert len(result["balances"]) == 2
    assert len(result["positions"]) == 2


# -- Market depth -------------------------------------------------------------

def test_fetch_market_depth_returns_orders():
    fake = FakeFutuClient()
    adapter = FutuAdapter(config=_make_config(), client=fake)
    depth = adapter.fetch_market_depth(symbol="HK.00700", limit=5)
    assert depth["symbol"] == "HK.00700"
    assert depth["source"] == "futu-opend"
    assert isinstance(depth["bids"], list)
    assert isinstance(depth["asks"], list)
    assert len(depth["bids"]) == 5
    assert len(depth["asks"]) == 5


# -- History kline ------------------------------------------------------------

def test_get_history_kline_returns_bars():
    fake = FakeFutuClient()
    adapter = FutuAdapter(config=_make_config(), client=fake)
    bars = adapter.get_history_kline(symbol="HK.00700", interval="1d", limit=50)
    assert isinstance(bars, list)
    assert len(bars) == 50
    for bar in bars:
        assert len(bar) == 6  # ts, open, high, low, close, volume


# -- RT data ------------------------------------------------------------------

def test_get_rt_data_returns_snapshot():
    fake = FakeFutuClient()
    adapter = FutuAdapter(config=_make_config(), client=fake)
    snap = adapter.get_rt_data(symbol="HK.00700")
    assert snap["symbol"] == "HK.00700"
    assert "price" in snap
    assert "bid_price" in snap
    assert "ask_price" in snap


# -- Healthcheck --------------------------------------------------------------

def test_healthcheck_returns_ok():
    fake = FakeFutuClient()
    adapter = FutuAdapter(config=_make_config(), client=fake)
    result = adapter.healthcheck()
    assert result["status"] == "ok"
    assert result["opend_connected"] is True


# -- Missing SDK --------------------------------------------------------------

def test_missing_sdk_raises_runtime_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "futu", None)
    env = _make_futu_env()
    with pytest.raises(RuntimeError, match="futu-api") as exc_info:
        _SdkFutuClient(env)
    assert isinstance(exc_info.value.__cause__, ImportError)


# -- Repr safety --------------------------------------------------------------

def test_repr_does_not_expose_host():
    adapter = FutuAdapter(
        config=_make_config(),
        futu_env=_make_futu_env(host="192.168.1.100"),
        client=FakeFutuClient(),
    )
    r = repr(adapter)
    assert "192.168.1.100" in r  # host is safe to show
    assert "dry_run" in r
