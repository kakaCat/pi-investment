"""
滑点模型 - 模拟真实交易中的价格滑动

滑点类型:
1. 固定滑点: 固定百分比
2. 比例滑点: 根据订单大小动态调整
3. 冲击成本: 大单对价格的影响
"""

from typing import Optional


class SlippageModel:
    """滑点模型"""

    def __init__(
        self,
        fixed_slippage: float = 0.001,  # 固定滑点 0.1%
        impact_factor: float = 0.0001,  # 冲击成本系数
    ):
        self.fixed_slippage = fixed_slippage
        self.impact_factor = impact_factor

    def calculate_slippage(
        self,
        base_price: float,
        shares: int,
        action: str,
        avg_volume: Optional[float] = None
    ) -> float:
        """
        计算滑点后的成交价

        Args:
            base_price: 基准价格
            shares: 股数
            action: 'buy' or 'sell'
            avg_volume: 平均成交量 (用于计算冲击成本)

        Returns:
            成交价
        """
        # 1. 固定滑点
        if action == 'buy':
            slipped_price = base_price * (1 + self.fixed_slippage)
        else:
            slipped_price = base_price * (1 - self.fixed_slippage)

        # 2. 冲击成本 (如果订单量大)
        if avg_volume and avg_volume > 0:
            volume_ratio = shares / avg_volume
            if volume_ratio > 0.01:  # 超过日均成交量1%
                impact_cost = self.impact_factor * volume_ratio
                if action == 'buy':
                    slipped_price *= (1 + impact_cost)
                else:
                    slipped_price *= (1 - impact_cost)

        return slipped_price

    def calculate_fixed_slippage(self, base_price: float, action: str) -> float:
        """计算固定滑点"""
        if action == 'buy':
            return base_price * (1 + self.fixed_slippage)
        else:
            return base_price * (1 - self.fixed_slippage)

    def calculate_impact_cost(
        self,
        base_price: float,
        shares: int,
        avg_volume: float,
        action: str
    ) -> float:
        """
        计算冲击成本

        大单对价格的影响
        """
        if avg_volume <= 0:
            return base_price

        volume_ratio = shares / avg_volume

        # 冲击成本模型: 线性增长
        if volume_ratio > 0.1:  # 超过10%日均量
            impact = self.impact_factor * volume_ratio * 10
        elif volume_ratio > 0.01:  # 超过1%日均量
            impact = self.impact_factor * volume_ratio
        else:
            impact = 0

        if action == 'buy':
            return base_price * (1 + impact)
        else:
            return base_price * (1 - impact)
