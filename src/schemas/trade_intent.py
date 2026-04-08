from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    QUOTE = "quote"


class SmartOrderStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"


class TradeIntent(BaseModel):
    """Single source of truth for trade decisions (fixes reviewer feedback)."""

    action: TradeAction
    qty: float = Field(gt=0, description="Quantity in base asset (BTC)")
    price: float | None = Field(None, description="Limit price or None for market")
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reason: str | dict[str, Any] = Field(default_factory=dict)
    timestamp_ms: int = Field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    symbol: str = "BTCUSDT"


class SmartOrder(BaseModel):
    """Standardized smart_order from workflow execution_result."""

    status: SmartOrderStatus
    intent: TradeIntent
    side: Literal["buy", "sell"]
    qty: float
    price: float | None = None
    slippage_bps: float = 0.0
    filled_qty: float | None = None
