# domain/trading/models/order.py
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"

class OrderStatus(Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"

@dataclass
class Order:
    """订单模型 - 表示一个交易订单"""
    id: Optional[int] = None
    account_name: str = ""
    symbol: str = ""
    name: str = ""
    action: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.LIMIT
    quantity: int = 0
    price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    avg_filled_price: float = 0.0
    reason: Optional[str] = None
    signal_id: Optional[int] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    parent_order_id: Optional[int] = None
    order_group: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
