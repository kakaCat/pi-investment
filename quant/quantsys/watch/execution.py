"""Order request and execution abstractions for watch decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass(frozen=True)
class OrderRequest:
    """Order proposed by the agent-assisted watch pipeline."""

    symbol: str
    action: str
    price: float
    shares: int
    reason: str
    created_at: datetime
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(frozen=True)
class OrderResult:
    """Execution result returned by an order executor."""

    order_id: str
    symbol: str
    action: str
    price: float
    shares: int
    status: str
    mode: str
    message: str


class SimulatedOrderExecutor:
    """Executor used for dry runs and tests before broker integration."""

    def execute(self, order: OrderRequest) -> OrderResult:
        return OrderResult(
            order_id=f"SIM-{uuid4().hex[:12]}",
            symbol=order.symbol,
            action=order.action,
            price=order.price,
            shares=order.shares,
            status="accepted",
            mode="simulated",
            message="simulated order accepted",
        )
