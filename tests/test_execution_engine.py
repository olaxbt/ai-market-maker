"""Tests for execution engine wiring (Task 4).

All tests use fake adapters — no real exchange calls, no real API keys.
set_nexus_adapter(None) resets the singleton; every test that touches
get_nexus_adapter() must do this in a finally block.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from adapters.exchange_protocol import ExchangeOrderResult
from adapters.nexus_adapter import (
    NexusAdapter,
    NexusAdapterConfig,
    OmsNexusAdapter,
    get_nexus_adapter,
    set_nexus_adapter,
)
from config.execution_engine import (
    EXECUTION_ENGINE_ENV,
    ExecutionEngine,
    load_execution_engine,
)
from oms.oms import Oms

# ---------------------------------------------------------------------------
# Shared fake adapter (satisfies ExchangeAdapter Protocol, no I/O)
# ---------------------------------------------------------------------------


class _FakeExchangeAdapter:
    def __init__(self) -> None:
        self.place_order_count = 0

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        order_type: str,
        price: float | None,
        client_order_id: str | None,
    ) -> ExchangeOrderResult:
        self.place_order_count += 1
        return ExchangeOrderResult(
            status="accepted",
            exchange_order_id=f"fake-{self.place_order_count}",
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            filled_qty=0.0,
            ts=1_000_000,
            raw={},
        )

    def cancel_order(self, *, symbol: str, exchange_order_id: str) -> ExchangeOrderResult:
        return ExchangeOrderResult(
            status="cancelled",
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="",
            qty=0.0,
            price=None,
            filled_qty=0.0,
            ts=1_000_000,
            raw={},
        )

    def get_order_status(self, *, symbol: str, exchange_order_id: str) -> ExchangeOrderResult:
        return ExchangeOrderResult(
            status="accepted",
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="",
            qty=0.0,
            price=None,
            filled_qty=0.0,
            ts=1_000_000,
            raw={},
        )

    def get_portfolio_health(self, *, account_id: str | None = None) -> dict[str, Any]:
        return {"account_id": account_id or "default", "balances": {}, "positions": []}

    def fetch_market_depth(self, *, symbol: str, limit: int) -> dict[str, Any]:
        return {"symbol": symbol, "bids": [], "asks": []}


# ---------------------------------------------------------------------------
# Tests: load_execution_engine
# ---------------------------------------------------------------------------


def test_load_execution_engine_defaults_to_legacy(monkeypatch):
    monkeypatch.delenv(EXECUTION_ENGINE_ENV, raising=False)
    assert load_execution_engine() == ExecutionEngine.LEGACY


def test_load_execution_engine_oms(monkeypatch):
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "oms")
    assert load_execution_engine() == ExecutionEngine.OMS


def test_load_execution_engine_case_insensitive(monkeypatch):
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "OMS")
    assert load_execution_engine() == ExecutionEngine.OMS


def test_load_execution_engine_unknown_falls_back_to_legacy(monkeypatch):
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "turbo")
    assert load_execution_engine() == ExecutionEngine.LEGACY


# ---------------------------------------------------------------------------
# Tests: NexusAdapter now satisfies ExchangeAdapter Protocol (5 methods)
# ---------------------------------------------------------------------------


def test_nexus_adapter_satisfies_exchange_adapter_protocol():
    adapter = NexusAdapter(NexusAdapterConfig(mode="paper"))
    for method in (
        "place_order",
        "cancel_order",
        "get_order_status",
        "get_portfolio_health",
        "fetch_market_depth",
    ):
        assert callable(getattr(adapter, method, None)), f"Missing protocol method: {method}"


def test_nexus_adapter_cancel_order_returns_typed_result():
    adapter = NexusAdapter(NexusAdapterConfig(mode="paper"))
    result = adapter.cancel_order(symbol="BTC/USDT", exchange_order_id="eid-1")
    assert result["status"] == "cancelled"
    assert result["exchange_order_id"] == "eid-1"
    assert result["symbol"] == "BTC/USDT"


def test_nexus_adapter_get_order_status_returns_typed_result():
    adapter = NexusAdapter(NexusAdapterConfig(mode="paper"))
    result = adapter.get_order_status(symbol="ETH/USDT", exchange_order_id="eid-2")
    assert result["status"] == "accepted"
    assert result["exchange_order_id"] == "eid-2"


# ---------------------------------------------------------------------------
# Tests: OmsNexusAdapter routes through OMS
# ---------------------------------------------------------------------------


def test_oms_nexus_adapter_routes_place_smart_order_through_oms():
    fake = _FakeExchangeAdapter()
    oms = Oms(adapter=fake)
    oms_adapter = OmsNexusAdapter(oms=oms, exchange_adapter=fake)

    result = oms_adapter.place_smart_order(
        symbol="BTC/USDT",
        side="buy",
        qty=0.1,
        order_type="limit",
        price=50_000.0,
    )
    assert result["status"] == "accepted"
    assert result["symbol"] == "BTC/USDT"
    assert result["side"] == "buy"
    assert result["qty"] == 0.1
    assert fake.place_order_count == 1  # OMS called the adapter exactly once


def test_oms_nexus_adapter_does_not_call_exchange_in_dry_run():
    fake = _FakeExchangeAdapter()
    oms = Oms(adapter=fake, dry_run=True)
    oms_adapter = OmsNexusAdapter(oms=oms, exchange_adapter=fake)

    oms_adapter.place_smart_order(
        symbol="BTC/USDT",
        side="buy",
        qty=0.1,
        order_type="market",
        price=None,
    )
    assert fake.place_order_count == 0  # dry_run: adapter never called


def test_oms_nexus_adapter_delegates_portfolio_health():
    fake = _FakeExchangeAdapter()
    oms_adapter = OmsNexusAdapter(oms=Oms(adapter=fake), exchange_adapter=fake)

    health = oms_adapter.get_portfolio_health(account_id="test-account")
    assert health["account_id"] == "test-account"


def test_oms_nexus_adapter_delegates_market_depth():
    fake = _FakeExchangeAdapter()
    oms_adapter = OmsNexusAdapter(oms=Oms(adapter=fake), exchange_adapter=fake)

    depth = oms_adapter.fetch_market_depth(symbol="ETH/USDT", limit=5)
    assert depth["symbol"] == "ETH/USDT"


def test_oms_nexus_adapter_result_shape_compatible_with_execution_result():
    """Per-order result must satisfy what main.py reads from smart_orders entries.

    main.py: execution_result["smart_order"] = smart_orders[0]
    e2e test: assert smart_order["status"] == "accepted"
    paper_account falls back to paper_snapshot when "paper" key is absent — no issue.
    """
    fake = _FakeExchangeAdapter()
    oms_adapter = OmsNexusAdapter(oms=Oms(adapter=fake), exchange_adapter=fake)

    result = oms_adapter.place_smart_order(
        symbol="ETH/USDT",
        side="sell",
        qty=0.5,
        order_type="market",
        price=3_000.0,
    )
    # Keys that main.py and the e2e test read from individual smart_orders entries
    assert result["status"] == "accepted"
    assert result["symbol"] == "ETH/USDT"
    assert result["side"] == "sell"
    assert result["qty"] == 0.5


# ---------------------------------------------------------------------------
# Tests: get_nexus_adapter() factory
# ---------------------------------------------------------------------------


def test_get_nexus_adapter_default_returns_nexus_adapter(monkeypatch):
    """Default (no env vars) must return NexusAdapter — legacy path unchanged."""
    monkeypatch.delenv(EXECUTION_ENGINE_ENV, raising=False)
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    set_nexus_adapter(None)
    try:
        adapter = get_nexus_adapter()
        assert isinstance(adapter, NexusAdapter)
    finally:
        set_nexus_adapter(None)


def test_get_nexus_adapter_explicit_legacy_returns_nexus_adapter(monkeypatch):
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "legacy")
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    set_nexus_adapter(None)
    try:
        adapter = get_nexus_adapter()
        assert isinstance(adapter, NexusAdapter)
    finally:
        set_nexus_adapter(None)


def test_get_nexus_adapter_oms_paper_returns_oms_adapter(monkeypatch):
    """OMS engine with paper exchange must return OmsNexusAdapter."""
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "oms")
    monkeypatch.delenv("EXCHANGE", raising=False)
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    set_nexus_adapter(None)
    try:
        adapter = get_nexus_adapter()
        assert isinstance(adapter, OmsNexusAdapter)
    finally:
        set_nexus_adapter(None)


def test_get_nexus_adapter_oms_hyperliquid_without_dry_run_raises(monkeypatch):
    """OMS + Hyperliquid without dry_run must fail closed with a clear RuntimeError."""
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "oms")
    monkeypatch.setenv("EXCHANGE", "hyperliquid")
    monkeypatch.setenv("AI_MARKET_MAKER_ALLOW_LIVE", "1")
    monkeypatch.delenv("HYPERLIQUID_DRY_RUN", raising=False)
    set_nexus_adapter(None)
    try:
        with pytest.raises(RuntimeError, match="not implemented"):
            get_nexus_adapter()
    finally:
        set_nexus_adapter(None)


def test_get_nexus_adapter_oms_hyperliquid_dry_run_returns_oms_adapter(monkeypatch):
    """OMS + Hyperliquid + dry_run=True must return OmsNexusAdapter without SDK."""
    monkeypatch.setenv(EXECUTION_ENGINE_ENV, "oms")
    monkeypatch.setenv("EXCHANGE", "hyperliquid")
    monkeypatch.setenv("AI_MARKET_MAKER_ALLOW_LIVE", "1")
    monkeypatch.setenv("HYPERLIQUID_DRY_RUN", "1")
    # SDK absent — must still work because FakeHyperliquidClient is injected
    monkeypatch.setitem(sys.modules, "hyperliquid", None)
    set_nexus_adapter(None)
    try:
        adapter = get_nexus_adapter()
        assert isinstance(adapter, OmsNexusAdapter)
        # OMS maps dry_run adapter response → ACCEPTED order state (no real order sent)
        result = adapter.place_smart_order(
            symbol="BTC/USDT", side="buy", qty=0.01, order_type="limit", price=50_000.0
        )
        assert result["status"] == "accepted"
    finally:
        set_nexus_adapter(None)


def test_missing_sdk_does_not_break_legacy_path(monkeypatch):
    """Missing Hyperliquid SDK must never affect the default paper/legacy path."""
    monkeypatch.setitem(sys.modules, "hyperliquid", None)
    monkeypatch.delenv(EXECUTION_ENGINE_ENV, raising=False)
    monkeypatch.delenv("AI_MARKET_MAKER_ALLOW_LIVE", raising=False)
    set_nexus_adapter(None)
    try:
        adapter = get_nexus_adapter()
        assert isinstance(adapter, NexusAdapter)
    finally:
        set_nexus_adapter(None)
