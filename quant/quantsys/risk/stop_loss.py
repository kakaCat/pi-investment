"""
止损机制 - Stop Loss Management

多种止损策略，保护资金安全。

止损类型:
1. 固定止损 (Fixed Stop Loss)
2. ATR止损 (ATR-based Stop Loss)
3. 移动止损 (Trailing Stop Loss)
4. 时间止损 (Time-based Stop Loss)
5. 技术止损 (Technical Stop Loss)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class StopLossConfig:
    """止损配置"""
    method: str = 'fixed'                   # 止损方法
    fixed_pct: float = 0.05                 # 固定止损 5%
    atr_multiplier: float = 2.0             # ATR倍数
    trailing_pct: float = 0.10              # 移动止损 10%
    max_holding_days: int = 60              # 最大持仓天数
    profit_protect_pct: float = 0.15        # 盈利保护阈值 15%
    profit_protect_stop: float = 0.05       # 盈利保护止损 5%


class StopLossManager:
    """止损管理器"""

    def __init__(self, config: Optional[StopLossConfig] = None):
        """
        初始化止损管理器

        Args:
            config: 止损配置
        """
        self.config = config or StopLossConfig()
        self.stop_prices: Dict[str, float] = {}  # {symbol: stop_price}
        self.stop_reasons: Dict[str, str] = {}   # {symbol: reason}

    def calculate_stop_price(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        highest_price: float,
        entry_date: str,
        current_date: str,
        market_data: Optional[Dict] = None
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        计算止损价格

        Args:
            symbol: 股票代码
            entry_price: 入场价格
            current_price: 当前价格
            highest_price: 持仓期间最高价
            entry_date: 入场日期
            current_date: 当前日期
            market_data: 市场数据 (包含ATR等)

        Returns:
            (stop_price, reason)
            - stop_price: 止损价格，None表示不止损
            - reason: 止损原因
        """
        # 1. 固定止损
        if self.config.method == 'fixed':
            stop_price = entry_price * (1 - self.config.fixed_pct)
            if current_price <= stop_price:
                return stop_price, f"固定止损 {self.config.fixed_pct*100:.1f}%"

        # 2. ATR止损
        elif self.config.method == 'atr':
            if market_data and 'atr' in market_data:
                atr = market_data['atr']
                stop_price = entry_price - (atr * self.config.atr_multiplier)
                if current_price <= stop_price:
                    return stop_price, f"ATR止损 ({self.config.atr_multiplier}x ATR)"

        # 3. 移动止损
        elif self.config.method == 'trailing':
            stop_price = highest_price * (1 - self.config.trailing_pct)
            if current_price <= stop_price:
                return stop_price, f"移动止损 {self.config.trailing_pct*100:.1f}%"

        # 4. 组合止损 (推荐)
        elif self.config.method == 'combined':
            # 先检查固定止损 (防止大幅亏损)
            fixed_stop = entry_price * (1 - self.config.fixed_pct)
            if current_price <= fixed_stop:
                return fixed_stop, f"固定止损 {self.config.fixed_pct*100:.1f}%"

            # 盈利后启用移动止损
            profit_pct = (current_price - entry_price) / entry_price
            if profit_pct >= self.config.profit_protect_pct:
                # 盈利保护：锁定部分利润
                protect_stop = entry_price * (1 + self.config.profit_protect_stop)
                if current_price <= protect_stop:
                    return protect_stop, f"盈利保护止损 (锁定{self.config.profit_protect_stop*100:.1f}%利润)"

                # 移动止损
                trailing_stop = highest_price * (1 - self.config.trailing_pct)
                if current_price <= trailing_stop:
                    return trailing_stop, f"移动止损 {self.config.trailing_pct*100:.1f}%"

        # 5. 时间止损
        holding_days = self._calculate_holding_days(entry_date, current_date)
        if holding_days >= self.config.max_holding_days:
            return current_price, f"时间止损 (持仓{holding_days}天)"

        # 6. 技术止损 (跌破关键支撑位)
        if market_data and 'support_level' in market_data:
            support = market_data['support_level']
            if current_price <= support:
                return support, "跌破技术支撑位"

        return None, None

    def should_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        highest_price: float,
        entry_date: str,
        current_date: str,
        market_data: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        判断是否应该止损

        Returns:
            (should_stop, reason)
        """
        stop_price, reason = self.calculate_stop_price(
            symbol, entry_price, current_price, highest_price,
            entry_date, current_date, market_data
        )

        if stop_price is not None:
            self.stop_prices[symbol] = stop_price
            self.stop_reasons[symbol] = reason
            return True, reason

        return False, None

    def _calculate_holding_days(self, entry_date: str, current_date: str) -> int:
        """计算持仓天数"""
        try:
            entry = datetime.strptime(entry_date, '%Y-%m-%d')
            current = datetime.strptime(current_date, '%Y-%m-%d')
            return (current - entry).days
        except:
            return 0

    def update_trailing_stop(
        self,
        symbol: str,
        entry_price: float,
        highest_price: float
    ) -> float:
        """
        更新移动止损价格

        Args:
            symbol: 股票代码
            entry_price: 入场价格
            highest_price: 最高价

        Returns:
            新的止损价格
        """
        # 移动止损
        trailing_stop = highest_price * (1 - self.config.trailing_pct)

        # 确保止损价不低于入场价 (盈利保护)
        profit_pct = (highest_price - entry_price) / entry_price
        if profit_pct >= self.config.profit_protect_pct:
            min_stop = entry_price * (1 + self.config.profit_protect_stop)
            trailing_stop = max(trailing_stop, min_stop)

        self.stop_prices[symbol] = trailing_stop
        return trailing_stop

    def get_stop_price(self, symbol: str) -> Optional[float]:
        """获取止损价格"""
        return self.stop_prices.get(symbol)

    def get_stop_reason(self, symbol: str) -> Optional[str]:
        """获取止损原因"""
        return self.stop_reasons.get(symbol)

    def remove_stop(self, symbol: str):
        """移除止损 (平仓后)"""
        if symbol in self.stop_prices:
            del self.stop_prices[symbol]
        if symbol in self.stop_reasons:
            del self.stop_reasons[symbol]

    def batch_check_stops(
        self,
        positions: Dict[str, Dict],
        current_prices: Dict[str, float],
        current_date: str,
        market_data: Optional[Dict] = None
    ) -> List[Dict]:
        """
        批量检查止损

        Args:
            positions: 持仓信息 {symbol: {entry_price, entry_date, highest_price, shares}}
            current_prices: 当前价格 {symbol: price}
            current_date: 当前日期
            market_data: 市场数据

        Returns:
            需要止损的列表 [{symbol, reason, stop_price, shares}]
        """
        stops = []

        for symbol, position in positions.items():
            current_price = current_prices.get(symbol)
            if not current_price:
                continue

            should_stop, reason = self.should_stop_loss(
                symbol=symbol,
                entry_price=position['entry_price'],
                current_price=current_price,
                highest_price=position.get('highest_price', position['entry_price']),
                entry_date=position['entry_date'],
                current_date=current_date,
                market_data=market_data.get(symbol) if market_data else None
            )

            if should_stop:
                stops.append({
                    'symbol': symbol,
                    'reason': reason,
                    'stop_price': self.stop_prices[symbol],
                    'shares': position['shares'],
                    'entry_price': position['entry_price'],
                    'current_price': current_price,
                    'loss_pct': (current_price - position['entry_price']) / position['entry_price']
                })

        return stops

    def calculate_position_risk(
        self,
        entry_price: float,
        stop_price: float,
        shares: int
    ) -> Dict:
        """
        计算持仓风险

        Args:
            entry_price: 入场价格
            stop_price: 止损价格
            shares: 股数

        Returns:
            风险指标字典
        """
        risk_per_share = entry_price - stop_price
        total_risk = risk_per_share * shares
        risk_pct = risk_per_share / entry_price

        return {
            'risk_per_share': risk_per_share,
            'total_risk': total_risk,
            'risk_pct': risk_pct,
            'risk_reward_ratio': None  # 需要目标价格才能计算
        }
