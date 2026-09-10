"""
交易结果数据类
"""
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from domain.trading.models.signal import Signal


@dataclass
class TradeResult:
    """交易结果"""
    signal: Signal
    success: bool
    shares: int = 0
    filled_price: float = 0.0
    amount: float = 0.0
    commission: float = 0.0
    pnl: float = 0.0  # 卖出时的盈亏
    pnl_pct: float = 0.0
    error: str = ''
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        return {
            'symbol': self.signal.symbol,
            'action': self.signal.action,
            'strategy_name': self.signal.strategy_name,
            'success': self.success,
            'shares': self.shares,
            'filled_price': self.filled_price,
            'amount': self.amount,
            'commission': self.commission,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'error': self.error,
            'timestamp': self.timestamp.isoformat(),
        }
