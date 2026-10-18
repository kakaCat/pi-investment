from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OrderSide(Enum):
    """Side of a trading order."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Lifecycle status of a trading order."""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Order:
    """Immutable value object representing a single trading order.

    An order is produced by a strategy and consumed by execution services.
    It captures intent (symbol, side, quantity, price) together with fill
    state and audit metadata.
    """

    symbol: str
    side: OrderSide
    quantity: float
    price: float
    order_id: str = ""
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: datetime | None = None
    filled_price: float | None = None
    filled_quantity: float = 0.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        if not isinstance(self.side, OrderSide):
            raise ValueError("side must be an OrderSide enum value")
        if not isinstance(self.quantity, (int, float)) or self.quantity <= 0:
            raise ValueError("quantity must be a positive number")
        if not isinstance(self.price, (int, float)) or self.price < 0:
            raise ValueError("price must be a non-negative number")
        if not isinstance(self.order_id, str):
            raise TypeError("order_id must be a string")
        if not isinstance(self.status, OrderStatus):
            raise ValueError("status must be an OrderStatus enum value")
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")

    @property
    def amount(self) -> float:
        """Total notional amount of the order (quantity * price)."""
        return self.quantity * self.price

    @property
    def is_complete(self) -> bool:
        """Return True when the order has reached a terminal state."""
        return self.status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }
