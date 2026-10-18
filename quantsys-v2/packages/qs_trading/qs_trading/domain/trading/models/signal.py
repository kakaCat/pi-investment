"""
交易信号数据类
"""
from typing import Optional
from dataclasses import dataclass


@dataclass
class Signal:
    """交易信号"""
    symbol: str
    action: str  # 'buy' | 'sell' | 'BUY' | 'SELL'
    strategy_id: Optional[int] = None
    strategy_name: str = ''
    strength: float = 1.0  # 信号强度 0-1
    price: Optional[float] = None  # 参考价格（None则用市价）
    stop_loss_pct: float = -0.08  # 止损比例
    take_profit_pct: float = 0.15  # 止盈比例
    reason: str = ''
    signal_id: Optional[str] = None

    def to_dict(self):
        return {
            'symbol': self.symbol,
            'action': self.action,
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'strength': self.strength,
            'price': self.price,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'reason': self.reason,
            'signal_id': self.signal_id,
        }
