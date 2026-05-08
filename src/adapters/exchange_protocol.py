"""Structural protocol for exchange adapters.

Both NexusAdapter (paper/mock) and HyperliquidAdapter implement this protocol
via duck-typing (no inheritance required).
"""

from __future__ import annotations

from typing import Any, NotRequired, Protocol, TypedDict


class ExchangeOrderResult(TypedDict):
    status: str  # accepted | filled | cancelled | rejected | error | dry_run
    exchange_order_id: str | None
    client_order_id: str | None
    symbol: str
    side: str  # buy | sell | ""
    qty: float
    price: float | None
    filled_qty: float
    ts: int  # unix epoch seconds
    raw: dict[str, Any]  # raw exchange response for audit
    error: NotRequired[str]


class ExchangeAdapter(Protocol):
    """Structural protocol satisfied by NexusAdapter, HyperliquidAdapter, and test doubles."""

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        order_type: str,
        price: float | None,
        client_order_id: str | None,
    ) -> ExchangeOrderResult: ...

    def cancel_order(
        self,
        *,
        symbol: str,
        exchange_order_id: str,
    ) -> ExchangeOrderResult: ...

    def get_order_status(
        self,
        *,
        symbol: str,
        exchange_order_id: str,
    ) -> ExchangeOrderResult: ...

    def get_portfolio_health(
        self,
        *,
        account_id: str | None,
    ) -> dict[str, Any]: ...

    def fetch_market_depth(
        self,
        *,
        symbol: str,
        limit: int,
    ) -> dict[str, Any]: ...


__all__ = ["ExchangeAdapter", "ExchangeOrderResult"]
