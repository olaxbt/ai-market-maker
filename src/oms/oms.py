"""Order Management System — exchange-agnostic order lifecycle controller.

Imports only from:
  - oms.order          (OmsOrder, OrderState)
  - adapters.exchange_protocol  (ExchangeAdapter, ExchangeOrderResult)
  - stdlib

No exchange-specific SDK imports. No real credentials required.
"""

from __future__ import annotations

import hashlib
from typing import Any

from adapters.exchange_protocol import ExchangeAdapter
from oms.order import OmsOrder, OrderState

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[str, OrderState] = {
    "accepted": OrderState.ACCEPTED,
    "open": OrderState.ACCEPTED,
    "filled": OrderState.FILLED,
    "cancelled": OrderState.CANCELLED,
    "rejected": OrderState.REJECTED,
    "error": OrderState.REJECTED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "partial": OrderState.PARTIALLY_FILLED,
}

_LIVE_STATES: frozenset[OrderState] = frozenset(
    {
        OrderState.SUBMITTED,
        OrderState.ACCEPTED,
        OrderState.PARTIALLY_FILLED,
        OrderState.UNKNOWN,
    }
)


def _map_status(raw_status: str) -> OrderState:
    """Map an ExchangeOrderResult.status string to an OrderState.

    Any unrecognised status — including "timeout", "dry_run", etc. — maps to UNKNOWN.
    """
    return _STATUS_MAP.get(raw_status.lower(), OrderState.UNKNOWN)


def _apply_result(order: OmsOrder, result: dict[str, Any]) -> None:
    """Update order fields from an ExchangeOrderResult dict, then transition state."""
    venue_id = result.get("exchange_order_id")
    if venue_id is not None:
        order.venue_order_id = venue_id

    filled = result.get("filled_qty")
    if filled is not None:
        order.filled_quantity = float(filled)

    error_msg = result.get("error")
    if error_msg:
        order.error = str(error_msg)

    new_state = _map_status(str(result.get("status", "")))
    order._transition(new_state)


class Oms:
    """Exchange-agnostic Order Management System.

    Maintains an in-process order book keyed on client_order_id.
    All exchange I/O is delegated to self._adapter (ExchangeAdapter protocol).

    Args:
        adapter:  Any object satisfying the ExchangeAdapter protocol.
        dry_run:  When True, submit_order creates the order in CREATED state
                  but never calls adapter.place_order.
    """

    def __init__(self, *, adapter: ExchangeAdapter, dry_run: bool = False) -> None:
        self._adapter = adapter
        self._dry_run = dry_run
        # Primary store: client_order_id → OmsOrder
        self._orders: dict[str, OmsOrder] = {}
        # Reverse index for idempotency: idempotency_key → client_order_id
        self._idem_index: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Static factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def make_idempotency_key(
        strategy: str,
        run_id: str,
        symbol: str,
        side: str,
        order_type: str,
        nonce: str,
    ) -> str:
        """Return a deterministic SHA-256 hex digest from the supplied fields.

        The digest is stable: same inputs always produce the same key, making it
        safe to use as a dedup guard across restarts within the same run.
        """
        raw = "|".join([strategy, run_id, symbol, side, order_type, nonce])
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def make_client_order_id(
        strategy: str,
        run_id: str,
        symbol: str,
        side: str,
        order_type: str,
        nonce: str,
    ) -> str:
        """Return a human-readable client order ID with a short hash suffix.

        Format: ``<strategy>-<side>-<symbol_safe>-<short_hash>``
        where ``symbol_safe`` replaces ``/`` with ``-`` and short_hash is the
        first 8 hex chars of the SHA-256 of all fields.
        """
        symbol_safe = symbol.replace("/", "-")
        short = hashlib.sha256(
            "|".join([strategy, run_id, symbol, side, order_type, nonce]).encode()
        ).hexdigest()[:8]
        return f"{strategy}-{side}-{symbol_safe}-{short}"

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        strategy: str,
        run_id: str,
        nonce: str,
        client_order_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> OmsOrder:
        """Place a new order via the adapter and track it internally.

        Idempotency:
            If ``idempotency_key`` resolves to an order already in the store,
            the existing OmsOrder is returned immediately — adapter.place_order
            is NOT called again.

        Dry run:
            If ``self._dry_run`` is True the order is created in CREATED state
            and returned without any adapter call.

        Exception handling:
            Any exception raised by adapter.place_order is caught, recorded
            in ``order.error``, and the order is transitioned to FAILED.
        """
        idem_key = idempotency_key or self.make_idempotency_key(
            strategy, run_id, symbol, side, order_type, nonce
        )

        # Idempotency guard — return existing order immediately
        existing_coid = self._idem_index.get(idem_key)
        if existing_coid is not None and existing_coid in self._orders:
            return self._orders[existing_coid]

        coid = client_order_id or self.make_client_order_id(
            strategy, run_id, symbol, side, order_type, nonce
        )

        order = OmsOrder(
            client_order_id=coid,
            idempotency_key=idem_key,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )

        self._orders[coid] = order
        self._idem_index[idem_key] = coid

        if self._dry_run:
            # Dry run: persist the order in CREATED state, never touch the adapter
            return order

        # Transition to SUBMITTED before adapter call
        order._transition(OrderState.SUBMITTED)

        try:
            result = self._adapter.place_order(
                symbol=symbol,
                side=side,
                qty=quantity,
                order_type=order_type,
                price=price,
                client_order_id=coid,
            )
            _apply_result(order, result)
        except Exception as exc:
            order.error = str(exc)
            order._transition(OrderState.FAILED)

        return order

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel_order(self, *, client_order_id: str) -> OmsOrder:
        """Cancel an order.

        If the order has no ``venue_order_id`` (e.g. was never confirmed by the
        exchange), it is marked CANCELLED locally without contacting the adapter.

        Returns the order as-is if it is already in a terminal state.
        """
        order = self._orders.get(client_order_id)
        if order is None:
            raise KeyError(f"No order found with client_order_id={client_order_id!r}")

        if order.is_terminal:
            return order

        if order.venue_order_id is None:
            order._transition(OrderState.CANCELLED)
            return order

        try:
            result = self._adapter.cancel_order(
                symbol=order.symbol,
                exchange_order_id=order.venue_order_id,
            )
            _apply_result(order, result)
        except Exception as exc:
            order.error = str(exc)
            order._transition(OrderState.FAILED)

        return order

    # ------------------------------------------------------------------
    # Status refresh
    # ------------------------------------------------------------------

    def get_order_status(self, *, client_order_id: str) -> OmsOrder:
        """Refresh order state by querying the adapter.

        Returns the order as-is if it is already in a terminal state or has no
        venue_order_id to query against.
        """
        order = self._orders.get(client_order_id)
        if order is None:
            raise KeyError(f"No order found with client_order_id={client_order_id!r}")

        if order.is_terminal:
            return order

        if order.venue_order_id is None:
            return order

        try:
            result = self._adapter.get_order_status(
                symbol=order.symbol,
                exchange_order_id=order.venue_order_id,
            )
            _apply_result(order, result)
        except Exception as exc:
            order.error = str(exc)
            order._transition(OrderState.FAILED)

        return order

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def reconcile(self, *, known_venue_ids: set[str] | None = None) -> list[OmsOrder]:
        """Mark orders as EXPIRED when their venue_order_id is absent from known_venue_ids.

        Args:
            known_venue_ids:
                When None (default), this is a safe no-op — returns an empty list.
                When a set of venue IDs, any live order whose venue_order_id is not
                None and is NOT in the set is transitioned to EXPIRED.
                No exchange calls are made.

        Returns:
            List of orders whose state was changed to EXPIRED during this call.
        """
        if known_venue_ids is None:
            return []

        expired: list[OmsOrder] = []
        for order in list(self._orders.values()):
            if order.state not in _LIVE_STATES:
                continue
            if order.venue_order_id is None:
                continue
            if order.venue_order_id not in known_venue_ids:
                order._transition(OrderState.EXPIRED)
                expired.append(order)

        return expired

    # ------------------------------------------------------------------
    # Read-only accessors
    # ------------------------------------------------------------------

    def get_order(self, *, client_order_id: str) -> OmsOrder | None:
        """Return the OmsOrder for the given client_order_id, or None if not found."""
        return self._orders.get(client_order_id)

    def all_orders(self) -> list[OmsOrder]:
        """Return a snapshot list of all orders currently in the store."""
        return list(self._orders.values())


__all__ = ["Oms"]
