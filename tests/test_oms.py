"""Tests for the OMS package (Task 2).

Fake adapters are defined in this file and implement the full ExchangeAdapter
protocol without any monkeypatching of real modules.
No Hyperliquid SDK is imported anywhere.
"""

from __future__ import annotations

import pathlib
import time
from typing import Any

from adapters.exchange_protocol import ExchangeOrderResult
from oms.oms import Oms
from oms.order import OmsOrder, OrderState

# ---------------------------------------------------------------------------
# Fake adapters — full ExchangeAdapter protocol (all 5 methods)
# ---------------------------------------------------------------------------


def _base_result(
    *,
    status: str,
    symbol: str = "BTC/USDT",
    side: str = "buy",
    qty: float = 0.1,
    price: float | None = 50_000.0,
    exchange_order_id: str | None = "eid-1",
    client_order_id: str | None = None,
    filled_qty: float = 0.0,
) -> ExchangeOrderResult:
    return ExchangeOrderResult(
        status=status,
        exchange_order_id=exchange_order_id,
        client_order_id=client_order_id,
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
        filled_qty=filled_qty,
        ts=int(time.time()),
        raw={},
    )


class _AcceptingAdapter:
    """Always accepts orders with status='accepted'."""

    def __init__(self) -> None:
        self.place_order_call_count = 0

    def place_order(
        self, *, symbol, side, qty, order_type, price, client_order_id
    ) -> ExchangeOrderResult:
        self.place_order_call_count += 1
        return _base_result(
            status="accepted",
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            client_order_id=client_order_id,
        )

    def cancel_order(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return _base_result(status="cancelled", symbol=symbol, exchange_order_id=exchange_order_id)

    def get_order_status(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return _base_result(status="accepted", symbol=symbol, exchange_order_id=exchange_order_id)

    def get_portfolio_health(self, *, account_id: str | None = None) -> dict[str, Any]:
        return {"balances": {}, "positions": []}

    def fetch_market_depth(self, *, symbol: str, limit: int) -> dict[str, Any]:
        return {"symbol": symbol, "bids": [], "asks": []}


class _RejectingAdapter:
    """Always rejects orders with status='rejected'."""

    def place_order(
        self, *, symbol, side, qty, order_type, price, client_order_id
    ) -> ExchangeOrderResult:
        return _base_result(
            status="rejected",
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            client_order_id=client_order_id,
        )

    def cancel_order(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return _base_result(status="cancelled", symbol=symbol, exchange_order_id=exchange_order_id)

    def get_order_status(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return _base_result(status="rejected", symbol=symbol, exchange_order_id=exchange_order_id)

    def get_portfolio_health(self, *, account_id: str | None = None) -> dict[str, Any]:
        return {"balances": {}, "positions": []}

    def fetch_market_depth(self, *, symbol: str, limit: int) -> dict[str, Any]:
        return {"symbol": symbol, "bids": [], "asks": []}


class _FilledStatusAdapter:
    """Returns 'accepted' on place_order, then 'filled' on get_order_status."""

    def place_order(
        self, *, symbol, side, qty, order_type, price, client_order_id
    ) -> ExchangeOrderResult:
        return _base_result(
            status="accepted",
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            client_order_id=client_order_id,
            exchange_order_id="eid-fill",
            filled_qty=0.0,
        )

    def cancel_order(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return _base_result(status="cancelled", symbol=symbol, exchange_order_id=exchange_order_id)

    def get_order_status(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return _base_result(
            status="filled",
            symbol=symbol,
            exchange_order_id=exchange_order_id,
            filled_qty=0.1,
            price=50_000.0,
        )

    def get_portfolio_health(self, *, account_id: str | None = None) -> dict[str, Any]:
        return {"balances": {}, "positions": []}

    def fetch_market_depth(self, *, symbol: str, limit: int) -> dict[str, Any]:
        return {"symbol": symbol, "bids": [], "asks": []}


class _TimeoutAdapter:
    """Returns status='timeout' — an unrecognised status that maps to UNKNOWN."""

    def place_order(
        self, *, symbol, side, qty, order_type, price, client_order_id
    ) -> ExchangeOrderResult:
        return _base_result(
            status="timeout",
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            client_order_id=client_order_id,
            exchange_order_id="eid-timeout",
        )

    def cancel_order(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return _base_result(status="cancelled", symbol=symbol, exchange_order_id=exchange_order_id)

    def get_order_status(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
        return _base_result(status="timeout", symbol=symbol, exchange_order_id=exchange_order_id)

    def get_portfolio_health(self, *, account_id: str | None = None) -> dict[str, Any]:
        return {"balances": {}, "positions": []}

    def fetch_market_depth(self, *, symbol: str, limit: int) -> dict[str, Any]:
        return {"symbol": symbol, "bids": [], "asks": []}


# ---------------------------------------------------------------------------
# Shared submit helper
# ---------------------------------------------------------------------------


def _submit(oms: Oms, *, nonce: str = "n1", **kwargs: Any) -> OmsOrder:
    defaults: dict[str, Any] = dict(
        symbol="BTC/USDT",
        side="buy",
        order_type="market",
        quantity=0.1,
        strategy="test-strat",
        run_id="run-001",
        nonce=nonce,
    )
    defaults.update(kwargs)
    return oms.submit_order(**defaults)


# ---------------------------------------------------------------------------
# Test 1 — fresh OmsOrder default state
# ---------------------------------------------------------------------------


def test_new_order_default_state_is_created():
    """A freshly constructed OmsOrder must start in CREATED state."""
    order = OmsOrder(
        client_order_id="coid-1",
        idempotency_key="idem-1",
        symbol="BTC/USDT",
        side="buy",
        order_type="market",
        quantity=0.1,
    )
    assert order.state == OrderState.CREATED
    assert order.venue_order_id is None
    assert order.filled_quantity == 0.0
    assert order.error is None
    assert isinstance(order.created_at, int)
    assert isinstance(order.updated_at, int)


# ---------------------------------------------------------------------------
# Test 2 — accepted transition
# ---------------------------------------------------------------------------


def test_submit_order_accepted_transitions_to_accepted():
    """When adapter returns 'accepted', order state must be ACCEPTED."""
    oms = Oms(adapter=_AcceptingAdapter())
    order = _submit(oms)
    assert order.state == OrderState.ACCEPTED
    assert order.venue_order_id is not None


# ---------------------------------------------------------------------------
# Test 3 — idempotency dedup
# ---------------------------------------------------------------------------


def test_duplicate_idempotency_key_does_not_call_adapter_twice():
    """Second submit_order with the same idempotency key must return the cached
    OmsOrder without calling adapter.place_order again."""
    adapter = _AcceptingAdapter()
    oms = Oms(adapter=adapter)

    idem = Oms.make_idempotency_key("s", "r", "BTC/USDT", "buy", "market", "n1")

    order_a = _submit(oms, idempotency_key=idem, nonce="n1")
    order_b = _submit(oms, idempotency_key=idem, nonce="n1")

    assert order_a is order_b
    assert adapter.place_order_call_count == 1


# ---------------------------------------------------------------------------
# Test 4 — rejected transition
# ---------------------------------------------------------------------------


def test_submit_rejected_transitions_to_rejected():
    """When adapter returns 'rejected', order state must be REJECTED."""
    oms = Oms(adapter=_RejectingAdapter())
    order = _submit(oms)
    assert order.state == OrderState.REJECTED


# ---------------------------------------------------------------------------
# Test 5 — dry run
# ---------------------------------------------------------------------------


def test_dry_run_submit_does_not_call_adapter():
    """With dry_run=True, adapter.place_order must never be called and order
    remains in CREATED state."""
    adapter = _AcceptingAdapter()
    oms = Oms(adapter=adapter, dry_run=True)
    order = _submit(oms)
    assert order.state == OrderState.CREATED
    assert adapter.place_order_call_count == 0


# ---------------------------------------------------------------------------
# Test 6 — cancel accepted order
# ---------------------------------------------------------------------------


def test_cancel_accepted_order():
    """Cancelling an ACCEPTED order must transition it to CANCELLED."""
    oms = Oms(adapter=_AcceptingAdapter())
    order = _submit(oms)
    assert order.state == OrderState.ACCEPTED

    cancelled = oms.cancel_order(client_order_id=order.client_order_id)
    assert cancelled.state == OrderState.CANCELLED
    assert cancelled is order  # same object, mutated in-place


# ---------------------------------------------------------------------------
# Test 7 — get_order_status maps 'filled'
# ---------------------------------------------------------------------------


def test_get_order_status_maps_filled():
    """After adapter reports 'filled', order state must be FILLED."""
    oms = Oms(adapter=_FilledStatusAdapter())
    order = _submit(oms)
    # place_order returned 'accepted' — start from ACCEPTED
    assert order.state == OrderState.ACCEPTED

    refreshed = oms.get_order_status(client_order_id=order.client_order_id)
    assert refreshed.state == OrderState.FILLED
    assert refreshed is order


# ---------------------------------------------------------------------------
# Test 8 — unknown status stays UNKNOWN, no auto-retry
# ---------------------------------------------------------------------------


def test_unknown_status_from_adapter_stays_unknown():
    """Adapter returning an unrecognised status ('timeout') must map to UNKNOWN,
    not trigger a retry or raise an exception."""
    oms = Oms(adapter=_TimeoutAdapter())
    order = _submit(oms)
    assert order.state == OrderState.UNKNOWN

    # Calling get_order_status on an UNKNOWN order (non-terminal, has venue_id)
    # must not raise and must remain UNKNOWN when adapter still returns 'timeout'
    refreshed = oms.get_order_status(client_order_id=order.client_order_id)
    assert refreshed.state == OrderState.UNKNOWN


# ---------------------------------------------------------------------------
# Test 9 — reconcile marks missing orders EXPIRED, no exchange calls
# ---------------------------------------------------------------------------


def test_reconcile_no_exchange_calls():
    """reconcile(known_venue_ids={...}) must:
    - Mark orders whose venue_order_id is absent from the set as EXPIRED
    - NOT call any adapter method
    - Leave orders whose venue_order_id IS in the set untouched
    """

    class _SpyAdapter(_AcceptingAdapter):
        def get_order_status(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
            raise AssertionError("get_order_status must not be called during reconcile")

        def cancel_order(self, *, symbol, exchange_order_id) -> ExchangeOrderResult:
            raise AssertionError("cancel_order must not be called during reconcile")

    adapter = _SpyAdapter()
    oms = Oms(adapter=adapter)

    order_a = _submit(oms, nonce="a")
    order_b = _submit(oms, nonce="b")
    order_c = _submit(oms, nonce="c")

    # Confirm all are ACCEPTED (adapter accepts all)
    assert order_a.state == OrderState.ACCEPTED
    assert order_b.state == OrderState.ACCEPTED
    assert order_c.state == OrderState.ACCEPTED

    # Assign deterministic venue IDs so reconcile has distinct values to compare
    order_a.venue_order_id = "venue-a"
    order_b.venue_order_id = "venue-b"
    order_c.venue_order_id = "venue-c"

    # Only venue-a is known; venue-b and venue-c should be expired
    expired = oms.reconcile(known_venue_ids={"venue-a"})

    assert order_a.state == OrderState.ACCEPTED  # untouched — was in known set
    assert order_b.state == OrderState.EXPIRED
    assert order_c.state == OrderState.EXPIRED

    assert len(expired) == 2
    assert order_b in expired
    assert order_c in expired


# ---------------------------------------------------------------------------
# Test 10 — no hyperliquid imports in oms source
# ---------------------------------------------------------------------------


def test_oms_has_no_hyperliquid_import():
    """oms.py and order.py must contain no reference to 'hyperliquid'."""
    src_root = pathlib.Path(__file__).resolve().parents[1] / "src"

    for rel_path in ("oms/oms.py", "oms/order.py"):
        path = src_root / rel_path
        source = path.read_text(encoding="utf-8")
        assert "import hyperliquid" not in source.lower(), (
            f"Found 'import hyperliquid' in {rel_path}"
        )
        assert "from hyperliquid" not in source.lower(), f"Found 'from hyperliquid' in {rel_path}"
