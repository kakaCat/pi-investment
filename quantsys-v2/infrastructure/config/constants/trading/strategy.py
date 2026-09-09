"""交易策略默认参数配置

包含 V13 和 V14 策略的所有默认参数。
这些参数直接影响交易决策和风险控制，修改时需谨慎。
"""

from dataclasses import dataclass
from infrastructure.config.constants.base import ConfigBase


@dataclass(frozen=True)
class V13StrategyDefaults(ConfigBase):
    """V13 策略默认参数

    V13 策略特点：
    - 短周期调仓（5 天）
    - 较少持仓数量（8 只）
    - 适中的仓位比例（85%）
    - 较严格的止损（-12%）

    所有百分比值使用小数表示（0.85 = 85%）
    止损值为负数（-0.12 = -12%）
    """

    #: 调仓周期（天）
    REBALANCE_DAYS: int = 5

    #: 最大持仓数量
    MAX_POSITIONS: int = 8

    #: 最大仓位比例（85%）
    MAX_POSITION_PCT: float = 0.85

    #: 止损比例（-12%）
    STOP_LOSS_PCT: float = -0.12

    #: 移动止损比例（-8%）
    TRAILING_STOP_PCT: float = -0.08

    #: 组合止损比例（-20%）
    PORTFOLIO_STOP_LOSS_PCT: float = -0.20

    def validate(self) -> tuple[bool, list[str]]:
        """验证配置参数"""
        errors = []

        # 调仓周期必须为正数
        if self.REBALANCE_DAYS <= 0:
            errors.append(f"REBALANCE_DAYS 必须大于 0，当前: {self.REBALANCE_DAYS}")

        # 持仓数量必须为正数
        if self.MAX_POSITIONS <= 0:
            errors.append(f"MAX_POSITIONS 必须大于 0，当前: {self.MAX_POSITIONS}")

        # 仓位比例必须在 (0, 1] 范围内
        if not 0 < self.MAX_POSITION_PCT <= 1.0:
            errors.append(f"MAX_POSITION_PCT 必须在 (0, 1] 范围内，当前: {self.MAX_POSITION_PCT}")

        # 止损比例必须为负数
        if self.STOP_LOSS_PCT >= 0:
            errors.append(f"STOP_LOSS_PCT 必须为负数，当前: {self.STOP_LOSS_PCT}")

        if self.TRAILING_STOP_PCT >= 0:
            errors.append(f"TRAILING_STOP_PCT 必须为负数，当前: {self.TRAILING_STOP_PCT}")

        if self.PORTFOLIO_STOP_LOSS_PCT >= 0:
            errors.append(f"PORTFOLIO_STOP_LOSS_PCT 必须为负数，当前: {self.PORTFOLIO_STOP_LOSS_PCT}")

        # 移动止损应该比固定止损更严格（绝对值更小）
        if abs(self.TRAILING_STOP_PCT) > abs(self.STOP_LOSS_PCT):
            errors.append(
                f"TRAILING_STOP_PCT ({self.TRAILING_STOP_PCT}) 应该比 "
                f"STOP_LOSS_PCT ({self.STOP_LOSS_PCT}) 更严格"
            )

        # 组合止损应该比单只股票止损更宽松
        if abs(self.PORTFOLIO_STOP_LOSS_PCT) < abs(self.STOP_LOSS_PCT):
            errors.append(
                f"PORTFOLIO_STOP_LOSS_PCT ({self.PORTFOLIO_STOP_LOSS_PCT}) 应该比 "
                f"STOP_LOSS_PCT ({self.STOP_LOSS_PCT}) 更宽松"
            )

        return len(errors) == 0, errors


@dataclass(frozen=True)
class V14StrategyDefaults(ConfigBase):
    """V14 策略默认参数

    V14 策略特点：
    - 长周期调仓（30 天）
    - 较多持仓数量（15 只）
    - 更高的仓位比例（95%）
    - 较宽松的止损（-15%）

    所有百分比值使用小数表示（0.95 = 95%）
    止损值为负数（-0.15 = -15%）
    """

    #: 调仓周期（天）
    REBALANCE_DAYS: int = 30

    #: 最大持仓数量
    MAX_POSITIONS: int = 15

    #: 最大仓位比例（95%）
    MAX_POSITION_PCT: float = 0.95

    #: 止损比例（-15%）
    STOP_LOSS_PCT: float = -0.15

    #: 移动止损比例（-10%）
    TRAILING_STOP_PCT: float = -0.10

    #: 组合止损比例（-25%）
    PORTFOLIO_STOP_LOSS_PCT: float = -0.25

    def validate(self) -> tuple[bool, list[str]]:
        """验证配置参数"""
        errors = []

        # 调仓周期必须为正数
        if self.REBALANCE_DAYS <= 0:
            errors.append(f"REBALANCE_DAYS 必须大于 0，当前: {self.REBALANCE_DAYS}")

        # 持仓数量必须为正数
        if self.MAX_POSITIONS <= 0:
            errors.append(f"MAX_POSITIONS 必须大于 0，当前: {self.MAX_POSITIONS}")

        # 仓位比例必须在 (0, 1] 范围内
        if not 0 < self.MAX_POSITION_PCT <= 1.0:
            errors.append(f"MAX_POSITION_PCT 必须在 (0, 1] 范围内，当前: {self.MAX_POSITION_PCT}")

        # 止损比例必须为负数
        if self.STOP_LOSS_PCT >= 0:
            errors.append(f"STOP_LOSS_PCT 必须为负数，当前: {self.STOP_LOSS_PCT}")

        if self.TRAILING_STOP_PCT >= 0:
            errors.append(f"TRAILING_STOP_PCT 必须为负数，当前: {self.TRAILING_STOP_PCT}")

        if self.PORTFOLIO_STOP_LOSS_PCT >= 0:
            errors.append(f"PORTFOLIO_STOP_LOSS_PCT 必须为负数，当前: {self.PORTFOLIO_STOP_LOSS_PCT}")

        # 移动止损应该比固定止损更严格（绝对值更小）
        if abs(self.TRAILING_STOP_PCT) > abs(self.STOP_LOSS_PCT):
            errors.append(
                f"TRAILING_STOP_PCT ({self.TRAILING_STOP_PCT}) 应该比 "
                f"STOP_LOSS_PCT ({self.STOP_LOSS_PCT}) 更严格"
            )

        # 组合止损应该比单只股票止损更宽松
        if abs(self.PORTFOLIO_STOP_LOSS_PCT) < abs(self.STOP_LOSS_PCT):
            errors.append(
                f"PORTFOLIO_STOP_LOSS_PCT ({self.PORTFOLIO_STOP_LOSS_PCT}) 应该比 "
                f"STOP_LOSS_PCT ({self.STOP_LOSS_PCT}) 更宽松"
            )

        return len(errors) == 0, errors


# 全局单例实例
V13_DEFAULTS = V13StrategyDefaults()
V14_DEFAULTS = V14StrategyDefaults()
