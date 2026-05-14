from __future__ import annotations

import time

from adapters.exchange_protocol import ExchangeAdapter, ExchangeOrderResult


class _MinimalAdapter:
    """Minimal concrete implementation satisfying ExchangeAdapter protocol."""

    def place_order(
        self, *, symbol, side, qty, order_type, price, client_order_id
    ) -> ExchangeOrderResult:
        return ExchangeOrderResult(
            status="accepted",
            exchange_order_id="x",
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            filled_qty=0.0,
            ts=int(time.time()),
            raw={},
        )

    def cancel_order(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return ExchangeOrderResult(
            status="cancelled",
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="",
            qty=0.0,
            price=None,
            filled_qty=0.0,
            ts=int(time.time()),
            raw={},
        )

    def get_order_status(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return ExchangeOrderResult(
            status="filled",
            exchange_order_id=exchange_order_id,
            client_order_id=None,
            symbol=symbol,
            side="buy",
            qty=1.0,
            price=100.0,
            filled_qty=1.0,
            ts=int(time.time()),
            raw={},
        )

    def get_portfolio_health(self, *, account_id):
        return {"balances": {}, "positions": []}

    def fetch_market_depth(self, *, symbol, limit):
        return {"symbol": symbol, "bids": [], "asks": []}


def test_minimal_adapter_satisfies_protocol():
    adapter: ExchangeAdapter = _MinimalAdapter()  # type: ignore[assignment]
    result = adapter.place_order(
        symbol="BTC/USDT",
        side="buy",
        qty=0.01,
        order_type="market",
        price=50000.0,
        client_order_id="test-1",
    )
    assert result["status"] == "accepted"
    assert result["symbol"] == "BTC/USDT"
    assert result["filled_qty"] == 0.0


def test_exchange_order_result_all_fields():
    r = ExchangeOrderResult(
        status="accepted",
        exchange_order_id="e1",
        client_order_id="c1",
        symbol="ETH/USDT",
        side="sell",
        qty=0.5,
        price=3000.0,
        filled_qty=0.5,
        ts=1700000000,
        raw={},
    )
    assert r["filled_qty"] == 0.5
    assert r["ts"] == 1700000000
    assert r["raw"] == {}


def test_exchange_order_result_optional_error():
    r = ExchangeOrderResult(
        status="rejected",
        exchange_order_id=None,
        client_order_id="c2",
        symbol="BTC/USDT",
        side="buy",
        qty=0.01,
        price=50000.0,
        filled_qty=0.0,
        ts=1700000000,
        raw={},
        error="insufficient margin",
    )
    assert r["error"] == "insufficient margin"
    assert r["status"] == "rejected"


def test_cancel_result():
    adapter = _MinimalAdapter()
    result = adapter.cancel_order(symbol="BTC/USDT", exchange_order_id="eid-99")
    assert result["status"] == "cancelled"
    assert result["exchange_order_id"] == "eid-99"


def test_market_depth_result():
    adapter = _MinimalAdapter()
    depth = adapter.fetch_market_depth(symbol="BTC/USDT", limit=5)
    assert depth["symbol"] == "BTC/USDT"
    assert "bids" in depth and "asks" in depth
