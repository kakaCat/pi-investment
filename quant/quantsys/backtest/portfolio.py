"""
持仓管理 - 管理投资组合的持仓和资金

负责:
- 持仓跟踪
- 资金管理
- 风险监控
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Position:
    """持仓"""
    symbol: str
    entry_date: str
    entry_price: float
    shares: int
    cost: float  # 总成本 (包括佣金)
    entry_reason: str = ''
    highest_price: float = 0.0  # 用于移动止损
    current_price: float = 0.0
    market_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class Portfolio:
    """投资组合"""
    initial_capital: float
    cash: float = 0.0
    positions: Dict[str, Position] = field(default_factory=dict)
    total_equity: float = 0.0
    position_value: float = 0.0

    def __post_init__(self):
        if self.cash == 0:
            self.cash = self.initial_capital

    def add_position(self, position: Position):
        """添加持仓"""
        self.positions[position.symbol] = position

    def remove_position(self, symbol: str) -> Optional[Position]:
        """移除持仓"""
        return self.positions.pop(symbol, None)

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """是否持有"""
        return symbol in self.positions

    def update_positions(self, price_data: Dict[str, float]):
        """
        更新所有持仓的市值和盈亏

        Args:
            price_data: {symbol: current_price}
        """
        self.position_value = 0

        for symbol, position in self.positions.items():
            if symbol in price_data:
                current_price = price_data[symbol]
                position.current_price = current_price
                position.market_value = current_price * position.shares
                position.pnl = position.market_value - position.cost
                position.pnl_pct = position.pnl / position.cost if position.cost > 0 else 0

                # 更新最高价 (用于移动止损)
                if current_price > position.highest_price:
                    position.highest_price = current_price

                self.position_value += position.market_value

        self.total_equity = self.cash + self.position_value

    def get_position_pct(self, symbol: str) -> float:
        """获取单个持仓占比"""
        if symbol not in self.positions or self.total_equity == 0:
            return 0.0

        position = self.positions[symbol]
        return position.market_value / self.total_equity

    def get_total_position_pct(self) -> float:
        """获取总仓位占比"""
        if self.total_equity == 0:
            return 0.0
        return self.position_value / self.total_equity

    def get_available_cash_pct(self) -> float:
        """获取可用现金占比"""
        if self.total_equity == 0:
            return 0.0
        return self.cash / self.total_equity

    def get_portfolio_summary(self) -> dict:
        """获取组合摘要"""
        return {
            'total_equity': self.total_equity,
            'cash': self.cash,
            'position_value': self.position_value,
            'cash_pct': self.get_available_cash_pct(),
            'position_pct': self.get_total_position_pct(),
            'position_count': len(self.positions),
            'total_pnl': sum(p.pnl for p in self.positions.values()),
            'total_pnl_pct': (self.total_equity - self.initial_capital) / self.initial_capital
        }

    def get_top_positions(self, n: int = 5) -> List[Position]:
        """获取前N大持仓"""
        sorted_positions = sorted(
            self.positions.values(),
            key=lambda p: p.market_value,
            reverse=True
        )
        return sorted_positions[:n]

    def get_losing_positions(self) -> List[Position]:
        """获取亏损持仓"""
        return [p for p in self.positions.values() if p.pnl < 0]

    def get_winning_positions(self) -> List[Position]:
        """获取盈利持仓"""
        return [p for p in self.positions.values() if p.pnl > 0]
