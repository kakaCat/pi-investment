# domain/portfolio/models/position.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Position:
    """持仓模型 - 表示账户中某只股票的持仓"""
    account_name: str = ""
    symbol: str = ""
    shares_total: int = 0          # 总持仓数量
    shares_available: int = 0      # 可卖数量（T+1后）
    avg_cost: float = 0.0          # 平均成本
    current_price: float = 0.0     # 当前价格
    market_value: float = 0.0      # 市值
    unrealized_pnl: float = 0.0    # 浮动盈亏
    unrealized_pnl_rate: float = 0.0  # 浮动盈亏率
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
