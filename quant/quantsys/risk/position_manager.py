"""
仓位管理 - Position Management

动态调整仓位大小，基于风险和市场条件。

策略:
1. 固定仓位 (Fixed Position)
2. Kelly公式 (Kelly Criterion)
3. 波动率调整 (Volatility-based)
4. ATR仓位 (ATR-based)
5. 风险平价 (Risk Parity)
"""

from typing import Dict, Optional
from dataclasses import dataclass
import math


@dataclass
class PositionSizeConfig:
    """仓位管理配置"""
    method: str = 'fixed'                   # 仓位计算方法
    fixed_pct: float = 0.10                 # 固定仓位比例 10%
    kelly_fraction: float = 0.25            # Kelly公式保守系数
    target_volatility: float = 0.15         # 目标波动率 15%
    atr_multiplier: float = 2.0             # ATR倍数
    max_position_pct: float = 0.20          # 单股最大仓位 20%
    min_position_pct: float = 0.02          # 单股最小仓位 2%


class PositionManager:
    """仓位管理器"""

    def __init__(self, config: Optional[PositionSizeConfig] = None):
        """
        初始化仓位管理器

        Args:
            config: 仓位管理配置
        """
        self.config = config or PositionSizeConfig()

    def calculate_position_size(
        self,
        symbol: str,
        price: float,
        total_equity: float,
        signal_strength: float = 1.0,
        market_data: Optional[Dict] = None
    ) -> int:
        """
        计算仓位大小

        Args:
            symbol: 股票代码
            price: 当前价格
            total_equity: 总权益
            signal_strength: 信号强度 (0-1)
            market_data: 市场数据 (包含波动率、ATR等)

        Returns:
            建议买入股数
        """
        # 根据方法计算仓位比例
        if self.config.method == 'fixed':
            position_pct = self._fixed_position()
        elif self.config.method == 'kelly':
            position_pct = self._kelly_position(market_data)
        elif self.config.method == 'volatility':
            position_pct = self._volatility_position(market_data)
        elif self.config.method == 'atr':
            position_pct = self._atr_position(price, market_data)
        else:
            position_pct = self.config.fixed_pct

        # 应用信号强度调整
        position_pct *= signal_strength

        # 限制在最大/最小仓位之间
        position_pct = max(self.config.min_position_pct,
                          min(position_pct, self.config.max_position_pct))

        # 计算股数
        position_value = total_equity * position_pct
        shares = int(position_value / price)

        # 确保至少买入100股 (1手)
        shares = max(100, shares // 100 * 100)

        return shares

    def _fixed_position(self) -> float:
        """固定仓位"""
        return self.config.fixed_pct

    def _kelly_position(self, market_data: Optional[Dict]) -> float:
        """
        Kelly公式仓位

        Kelly% = (p * b - q) / b
        其中:
        - p: 胜率
        - q: 败率 (1-p)
        - b: 盈亏比 (平均盈利/平均亏损)
        """
        if not market_data:
            return self.config.fixed_pct

        win_rate = market_data.get('win_rate', 0.5)
        profit_loss_ratio = market_data.get('profit_loss_ratio', 1.5)

        if profit_loss_ratio <= 0:
            return self.config.fixed_pct

        # Kelly公式
        kelly_pct = (win_rate * profit_loss_ratio - (1 - win_rate)) / profit_loss_ratio

        # 应用保守系数 (通常使用1/4 Kelly)
        kelly_pct *= self.config.kelly_fraction

        # 确保非负
        return max(0, kelly_pct)

    def _volatility_position(self, market_data: Optional[Dict]) -> float:
        """
        波动率调整仓位

        仓位 = 目标波动率 / 股票波动率 * 基础仓位
        """
        if not market_data:
            return self.config.fixed_pct

        volatility = market_data.get('volatility', 0.20)

        if volatility <= 0:
            return self.config.fixed_pct

        # 波动率调整
        position_pct = (self.config.target_volatility / volatility) * self.config.fixed_pct

        return position_pct

    def _atr_position(self, price: float, market_data: Optional[Dict]) -> float:
        """
        ATR仓位

        基于ATR止损，计算合适的仓位大小
        仓位 = 风险金额 / (ATR * 倍数)
        """
        if not market_data:
            return self.config.fixed_pct

        atr = market_data.get('atr', price * 0.02)  # 默认2%

        if atr <= 0:
            return self.config.fixed_pct

        # 假设愿意承担的风险是总权益的2%
        risk_pct = 0.02
        stop_distance = atr * self.config.atr_multiplier

        # 计算仓位
        position_pct = risk_pct / (stop_distance / price)

        return position_pct

    def adjust_position_for_correlation(
        self,
        symbol: str,
        base_position_pct: float,
        portfolio_positions: Dict,
        correlation_matrix: Optional[Dict] = None
    ) -> float:
        """
        根据相关性调整仓位

        如果组合中已有高相关性股票，降低新仓位

        Args:
            symbol: 股票代码
            base_position_pct: 基础仓位比例
            portfolio_positions: 当前持仓
            correlation_matrix: 相关性矩阵

        Returns:
            调整后的仓位比例
        """
        if not correlation_matrix or not portfolio_positions:
            return base_position_pct

        # 计算与现有持仓的平均相关性
        correlations = []
        for held_symbol in portfolio_positions.keys():
            if held_symbol in correlation_matrix.get(symbol, {}):
                corr = correlation_matrix[symbol][held_symbol]
                correlations.append(abs(corr))

        if not correlations:
            return base_position_pct

        avg_correlation = sum(correlations) / len(correlations)

        # 高相关性时降低仓位
        if avg_correlation > 0.7:
            adjustment_factor = 0.5  # 减半
        elif avg_correlation > 0.5:
            adjustment_factor = 0.75
        else:
            adjustment_factor = 1.0

        return base_position_pct * adjustment_factor

    def calculate_rebalance_trades(
        self,
        target_positions: Dict[str, float],  # {symbol: target_pct}
        current_positions: Dict[str, Dict],  # {symbol: {shares, price}}
        total_equity: float,
        threshold: float = 0.05  # 5%偏差才调仓
    ) -> Dict[str, int]:
        """
        计算再平衡交易

        Args:
            target_positions: 目标仓位 {symbol: pct}
            current_positions: 当前持仓
            total_equity: 总权益
            threshold: 触发调仓的偏差阈值

        Returns:
            调仓指令 {symbol: shares_to_trade}
            正数=买入，负数=卖出
        """
        trades = {}

        # 计算当前仓位比例
        current_pcts = {}
        for symbol, position in current_positions.items():
            value = position['shares'] * position['price']
            current_pcts[symbol] = value / total_equity

        # 计算需要调整的仓位
        all_symbols = set(target_positions.keys()) | set(current_pcts.keys())

        for symbol in all_symbols:
            target_pct = target_positions.get(symbol, 0)
            current_pct = current_pcts.get(symbol, 0)

            diff_pct = target_pct - current_pct

            # 只有偏差超过阈值才调仓
            if abs(diff_pct) > threshold:
                # 计算需要交易的金额
                trade_value = diff_pct * total_equity

                # 获取当前价格
                if symbol in current_positions:
                    price = current_positions[symbol]['price']
                else:
                    # 新股票，需要从市场数据获取价格
                    # 这里简化处理，实际应该传入价格
                    continue

                # 计算股数 (100股为单位)
                shares = int(trade_value / price / 100) * 100

                if shares != 0:
                    trades[symbol] = shares

        return trades

    def get_max_shares(
        self,
        price: float,
        total_equity: float,
        max_position_pct: Optional[float] = None
    ) -> int:
        """
        计算最大可买入股数

        Args:
            price: 股票价格
            total_equity: 总权益
            max_position_pct: 最大仓位比例 (可选)

        Returns:
            最大股数
        """
        max_pct = max_position_pct or self.config.max_position_pct
        max_value = total_equity * max_pct
        max_shares = int(max_value / price / 100) * 100
        return max_shares
