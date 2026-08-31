# domain/trading/models/trade.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Trade:
    """成交记录模型 - 表示一笔已成交的交易"""
    id: Optional[int] = None
    account_name: str = ""
    order_id: Optional[int] = None
    symbol: str = ""
    name: str = ""
    action: str = ""  # "buy" or "sell"
    shares: int = 0
    price: float = 0.0
    filled_price: float = 0.0
    amount: float = 0.0
    commission: float = 0.0
    stamp_duty: float = 0.0
    transfer_fee: float = 0.0
    realized_pnl: Optional[float] = None
    realized_pnl_rate: Optional[float] = None
    reason: Optional[str] = None
    trade_date: Optional[str] = None
    created_at: Optional[datetime] = None
