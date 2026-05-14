"""OmsOrder dataclass and OrderState StrEnum.

Deliberately has NO imports from oms.py or any exchange SDK.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class OrderState(StrEnum):
    """Lifecycle states for an OMS-tracked order.

    Terminal states (FILLED, CANCELLED, REJECTED, EXPIRED, FAILED) cannot be
    exited once entered — _transition() enforces this invariant.
    """

    CREATED = "created"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"
    UNKNOWN = "unknown"


_TERMINAL_STATES: frozenset[OrderState] = frozenset(
    {
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.EXPIRED,
        OrderState.FAILED,
    }
)


def _now() -> int:
    return int(time.time())


@dataclass
class OmsOrder:
    """A single order tracked by the OMS.

    Not frozen — state transitions happen in-place via _transition().
    created_at and updated_at are unix epoch seconds (int).
    """

    client_order_id: str
    idempotency_key: str
    symbol: str
    side: str  # "buy" | "sell"
    order_type: str  # "market" | "limit"
    quantity: float
    price: float | None = None
    state: OrderState = OrderState.CREATED
    venue_order_id: str | None = None
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    error: str | None = None
    created_at: int = field(default_factory=_now)
    updated_at: int = field(default_factory=_now)

    def _transition(self, new_state: OrderState) -> None:
        """Move to new_state unless already in a terminal state.

        Terminal states are a one-way door: calling _transition() on a terminal
        order is a no-op (the order is returned as-is by all mutation paths).
        """
        if self.state in _TERMINAL_STATES:
            return
        self.state = new_state
        self.updated_at = _now()

    @property
    def is_terminal(self) -> bool:
        """True if this order is in a state from which no further transitions are allowed."""
        return self.state in _TERMINAL_STATES


__all__ = ["OmsOrder", "OrderState"]
