"""
预交易风控 - Pre-Trade Risk Check

在订单执行前进行风险检查，防止违规交易。

检查项:
1. 黑名单检查 (ST股票、退市股)
2. 单股仓位限制 (< 10%)
3. 行业集中度限制 (< 30%)
4. 最大回撤限制 (< 20%)
5. 单日交易次数限制
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RiskConfig:
    """风控配置"""
    max_position_pct: float = 0.10          # 单股最大仓位 10%
    max_sector_pct: float = 0.30            # 单行业最大仓位 30%
    max_drawdown: float = 0.20              # 最大回撤限制 20%
    max_daily_trades: int = 10              # 单日最大交易次数
    blacklist: List[str] = None             # 黑名单
    allow_st_stocks: bool = False           # 是否允许ST股票
    min_liquidity: float = 1000000          # 最小流动性要求


class PreTradeRiskCheck:
    """预交易风控检查"""

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        初始化风控

        Args:
            config: 风控配置，如果为None则使用默认配置
        """
        self.config = config or RiskConfig()
        if self.config.blacklist is None:
            self.config.blacklist = []

        # 统计
        self.daily_trade_count: Dict[str, int] = {}  # {date: count}
        self.rejected_orders: List[Dict] = []

    def check(self, order, portfolio, market_data: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """
        执行预交易风控检查

        Args:
            order: 订单对象
            portfolio: 投资组合对象
            market_data: 市场数据 (可选)

        Returns:
            (is_valid, error_message)
            - is_valid: True表示通过检查，False表示拒绝
            - error_message: 拒绝原因，通过时为None
        """
        # 1. 黑名单检查
        if order.symbol in self.config.blacklist:
            return self._reject(order, "股票在黑名单中")

        # 2. ST股票检查
        if not self.config.allow_st_stocks and self._is_st_stock(order.symbol):
            return self._reject(order, "不允许交易ST股票")

        # 3. 仓位限制检查 (仅买入)
        if order.action == 'buy':
            passed, msg = self._check_position_limit(order, portfolio)
            if not passed:
                return self._reject(order, msg)

        # 4. 行业集中度检查 (仅买入)
        if order.action == 'buy' and market_data:
            passed, msg = self._check_sector_concentration(order, portfolio, market_data)
            if not passed:
                return self._reject(order, msg)

        # 5. 回撤限制检查
        if hasattr(portfolio, 'current_drawdown'):
            if portfolio.current_drawdown > self.config.max_drawdown:
                return self._reject(order, f"触发最大回撤限制 {self.config.max_drawdown*100:.1f}%")

        # 6. 单日交易次数限制
        passed, msg = self._check_daily_trade_limit(order)
        if not passed:
            return self._reject(order, msg)

        # 7. 流动性检查 (如果有市场数据)
        if market_data and order.action == 'buy':
            passed, msg = self._check_liquidity(order, market_data)
            if not passed:
                return self._reject(order, msg)

        return True, None

    def _is_st_stock(self, symbol: str) -> bool:
        """检查是否为ST股票"""
        # 简单检查：股票代码或名称包含ST
        return 'ST' in symbol.upper()

    def _check_position_limit(self, order, portfolio) -> Tuple[bool, Optional[str]]:
        """检查单股仓位限制"""
        if not hasattr(portfolio, 'total_equity') or portfolio.total_equity == 0:
            return True, None

        # 计算买入后的仓位占比
        order_value = order.price * order.shares
        new_position_pct = order_value / portfolio.total_equity

        # 如果已有持仓，加上现有仓位
        if hasattr(portfolio, 'positions') and order.symbol in portfolio.positions:
            existing_position = portfolio.positions[order.symbol]
            existing_value = existing_position.market_value if hasattr(existing_position, 'market_value') else 0
            new_position_pct = (order_value + existing_value) / portfolio.total_equity

        if new_position_pct > self.config.max_position_pct:
            return False, f"超过单股仓位限制 {self.config.max_position_pct*100:.1f}% (当前: {new_position_pct*100:.1f}%)"

        return True, None

    def _check_sector_concentration(self, order, portfolio, market_data: Dict) -> Tuple[bool, Optional[str]]:
        """检查行业集中度"""
        if not hasattr(portfolio, 'total_equity') or portfolio.total_equity == 0:
            return True, None

        # 获取股票所属行业
        sector = market_data.get('sectors', {}).get(order.symbol)
        if not sector:
            return True, None  # 无行业信息，跳过检查

        # 计算该行业当前仓位
        sector_value = 0
        if hasattr(portfolio, 'positions'):
            for symbol, position in portfolio.positions.items():
                if market_data.get('sectors', {}).get(symbol) == sector:
                    sector_value += getattr(position, 'market_value', 0)

        # 加上本次订单
        order_value = order.price * order.shares
        new_sector_pct = (sector_value + order_value) / portfolio.total_equity

        if new_sector_pct > self.config.max_sector_pct:
            return False, f"超过行业集中度限制 {self.config.max_sector_pct*100:.1f}% (行业: {sector}, 当前: {new_sector_pct*100:.1f}%)"

        return True, None

    def _check_daily_trade_limit(self, order) -> Tuple[bool, Optional[str]]:
        """检查单日交易次数限制"""
        date = order.date
        current_count = self.daily_trade_count.get(date, 0)

        if current_count >= self.config.max_daily_trades:
            return False, f"超过单日交易次数限制 {self.config.max_daily_trades}次"

        # 更新计数
        self.daily_trade_count[date] = current_count + 1
        return True, None

    def _check_liquidity(self, order, market_data: Dict) -> Tuple[bool, Optional[str]]:
        """检查流动性"""
        avg_volume = market_data.get('avg_volumes', {}).get(order.symbol)
        if not avg_volume:
            return True, None  # 无流动性数据，跳过检查

        avg_amount = market_data.get('avg_amounts', {}).get(order.symbol)
        if not avg_amount:
            return True, None

        # 检查是否满足最小流动性要求
        if avg_amount < self.config.min_liquidity:
            return False, f"流动性不足 (日均成交额: {avg_amount:,.0f} < {self.config.min_liquidity:,.0f})"

        # 检查订单量是否过大 (不超过日均成交量的10%)
        order_volume = order.shares
        if order_volume > avg_volume * 0.1:
            return False, f"订单量过大 (超过日均成交量10%)"

        return True, None

    def _reject(self, order, reason: str) -> Tuple[bool, str]:
        """拒绝订单并记录"""
        self.rejected_orders.append({
            'date': order.date,
            'symbol': order.symbol,
            'action': order.action,
            'reason': reason
        })
        return False, reason

    def get_statistics(self) -> Dict:
        """获取风控统计"""
        return {
            'total_rejected': len(self.rejected_orders),
            'rejected_by_reason': self._group_by_reason(),
            'daily_trades': dict(self.daily_trade_count)
        }

    def _group_by_reason(self) -> Dict[str, int]:
        """按拒绝原因分组统计"""
        reasons = {}
        for order in self.rejected_orders:
            reason = order['reason']
            reasons[reason] = reasons.get(reason, 0) + 1
        return reasons

    def reset_daily_stats(self, date: str):
        """重置指定日期的统计"""
        if date in self.daily_trade_count:
            del self.daily_trade_count[date]
