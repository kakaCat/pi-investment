"""风控限制配置

包含所有风险控制相关的阈值和限制参数。
这些参数直接影响交易风险控制，修改时需极其谨慎。
"""

from dataclasses import dataclass
from infrastructure.config.constants.base import ConfigBase


@dataclass(frozen=True)
class RiskLimits(ConfigBase):
    """风险控制限制配置

    所有百分比值使用小数表示（0.20 = 20%）
    所有负值表示损失（-0.08 = -8%）
    """

    # ============ 仓位控制 ============

    #: 单只股票最大仓位比例（默认 20%）
    MAX_SINGLE_POSITION_RATIO: float = 0.20

    #: 单行业最大集中度（默认 40%）
    MAX_SECTOR_CONCENTRATION: float = 0.40

    #: 最大同时持仓数量
    MAX_CONCURRENT_POSITIONS: int = 10

    # ============ 止损控制 ============

    #: 单只股票止损阈值（默认 -8%）
    STOP_LOSS_THRESHOLD: float = -0.08

    #: 单日最大回撤（默认 5%）
    MAX_DAILY_DRAWDOWN: float = 0.05

    # ============ 流动性控制 ============

    #: 委托量占日均成交量的最大比例（默认 20%）
    MAX_ORDER_VS_DAILY_VOLUME: float = 0.20

    #: 计算日均成交量的回溯天数
    VOLUME_LOOKBACK_DAYS: int = 60

    #: 计算日均成交量使用的最近天数
    VOLUME_RECENT_DAYS: int = 20

    #: 最小K线数量要求（用于各种计算）
    MIN_KLINE_COUNT: int = 20

    # ============ 相关性风险 ============

    #: 高相关性阈值（默认 80%）
    HIGH_CORRELATION_THRESHOLD: float = 0.80

    #: 相关性计算回溯天数
    CORRELATION_LOOKBACK_DAYS: int = 90

    # ============ Beta 敞口 ============

    #: 最小 Beta 值
    MIN_BETA_EXPOSURE: float = 0.5

    #: 最大 Beta 值
    MAX_BETA_EXPOSURE: float = 1.5

    # ============ 波动率 ============

    #: 单只股票最大波动率（默认 30%）
    MAX_STOCK_VOLATILITY: float = 0.30

    #: 波动率计算回溯天数
    VOLATILITY_LOOKBACK_DAYS: int = 60

    # ============ 市场环境 ============

    #: VIX 恐慌阈值
    VIX_PANIC_THRESHOLD: float = 30.0

    #: 最小涨跌家数比
    MIN_ADVANCE_DECLINE_RATIO: float = 0.30

    #: 市场状态回溯天数
    MARKET_REGIME_LOOKBACK_DAYS: int = 60

    #: 市场状态短期均线周期
    MARKET_REGIME_MA_SHORT: int = 20

    # ============ 交易时段 ============

    #: 开盘后避免交易的分钟数
    AVOID_OPEN_MINUTES: int = 30

    #: 收盘前避免交易的分钟数
    AVOID_CLOSE_MINUTES: int = 30

    # ============ 默认账户余额 ============

    #: 默认账户余额（元），用于无法获取真实余额时的降级
    DEFAULT_ACCOUNT_BALANCE: float = 1000000.0

    def validate(self) -> tuple[bool, list[str]]:
        """验证风控配置合法性"""
        errors = []

        # ========== 仓位控制验证 ==========

        if not 0 < self.MAX_SINGLE_POSITION_RATIO <= 1.0:
            errors.append(
                f"MAX_SINGLE_POSITION_RATIO 必须在 (0, 1] 范围内，当前: {self.MAX_SINGLE_POSITION_RATIO}"
            )

        if not 0 < self.MAX_SECTOR_CONCENTRATION <= 1.0:
            errors.append(
                f"MAX_SECTOR_CONCENTRATION 必须在 (0, 1] 范围内，当前: {self.MAX_SECTOR_CONCENTRATION}"
            )

        if self.MAX_CONCURRENT_POSITIONS <= 0:
            errors.append(
                f"MAX_CONCURRENT_POSITIONS 必须大于 0，当前: {self.MAX_CONCURRENT_POSITIONS}"
            )

        # 逻辑一致性：行业集中度应该大于等于单只股票仓位
        if self.MAX_SECTOR_CONCENTRATION < self.MAX_SINGLE_POSITION_RATIO:
            errors.append(
                f"MAX_SECTOR_CONCENTRATION ({self.MAX_SECTOR_CONCENTRATION}) "
                f"不能小于 MAX_SINGLE_POSITION_RATIO ({self.MAX_SINGLE_POSITION_RATIO})"
            )

        # ========== 止损控制验证 ==========

        if not -1.0 <= self.STOP_LOSS_THRESHOLD < 0:
            errors.append(
                f"STOP_LOSS_THRESHOLD 必须在 [-1, 0) 范围内，当前: {self.STOP_LOSS_THRESHOLD}"
            )

        if not 0 < self.MAX_DAILY_DRAWDOWN < 1.0:
            errors.append(
                f"MAX_DAILY_DRAWDOWN 必须在 (0, 1) 范围内，当前: {self.MAX_DAILY_DRAWDOWN}"
            )

        # ========== 流动性控制验证 ==========

        if not 0 < self.MAX_ORDER_VS_DAILY_VOLUME <= 1.0:
            errors.append(
                f"MAX_ORDER_VS_DAILY_VOLUME 必须在 (0, 1] 范围内，当前: {self.MAX_ORDER_VS_DAILY_VOLUME}"
            )

        if self.VOLUME_LOOKBACK_DAYS <= 0:
            errors.append(
                f"VOLUME_LOOKBACK_DAYS 必须大于 0，当前: {self.VOLUME_LOOKBACK_DAYS}"
            )

        if self.VOLUME_RECENT_DAYS <= 0:
            errors.append(
                f"VOLUME_RECENT_DAYS 必须大于 0，当前: {self.VOLUME_RECENT_DAYS}"
            )

        if self.VOLUME_RECENT_DAYS > self.VOLUME_LOOKBACK_DAYS:
            errors.append(
                f"VOLUME_RECENT_DAYS ({self.VOLUME_RECENT_DAYS}) "
                f"不能大于 VOLUME_LOOKBACK_DAYS ({self.VOLUME_LOOKBACK_DAYS})"
            )

        if self.MIN_KLINE_COUNT <= 0:
            errors.append(
                f"MIN_KLINE_COUNT 必须大于 0，当前: {self.MIN_KLINE_COUNT}"
            )

        # ========== 相关性风险验证 ==========

        if not 0 < self.HIGH_CORRELATION_THRESHOLD <= 1.0:
            errors.append(
                f"HIGH_CORRELATION_THRESHOLD 必须在 (0, 1] 范围内，当前: {self.HIGH_CORRELATION_THRESHOLD}"
            )

        if self.CORRELATION_LOOKBACK_DAYS <= 0:
            errors.append(
                f"CORRELATION_LOOKBACK_DAYS 必须大于 0，当前: {self.CORRELATION_LOOKBACK_DAYS}"
            )

        # ========== Beta 敞口验证 ==========

        if self.MIN_BETA_EXPOSURE < 0:
            errors.append(
                f"MIN_BETA_EXPOSURE 必须非负，当前: {self.MIN_BETA_EXPOSURE}"
            )

        if self.MAX_BETA_EXPOSURE <= 0:
            errors.append(
                f"MAX_BETA_EXPOSURE 必须大于 0，当前: {self.MAX_BETA_EXPOSURE}"
            )

        if self.MIN_BETA_EXPOSURE >= self.MAX_BETA_EXPOSURE:
            errors.append(
                f"MIN_BETA_EXPOSURE ({self.MIN_BETA_EXPOSURE}) "
                f"必须小于 MAX_BETA_EXPOSURE ({self.MAX_BETA_EXPOSURE})"
            )

        # ========== 波动率验证 ==========

        if not 0 < self.MAX_STOCK_VOLATILITY <= 1.0:
            errors.append(
                f"MAX_STOCK_VOLATILITY 必须在 (0, 1] 范围内，当前: {self.MAX_STOCK_VOLATILITY}"
            )

        if self.VOLATILITY_LOOKBACK_DAYS <= 0:
            errors.append(
                f"VOLATILITY_LOOKBACK_DAYS 必须大于 0，当前: {self.VOLATILITY_LOOKBACK_DAYS}"
            )

        # ========== 市场环境验证 ==========

        if self.VIX_PANIC_THRESHOLD <= 0:
            errors.append(
                f"VIX_PANIC_THRESHOLD 必须大于 0，当前: {self.VIX_PANIC_THRESHOLD}"
            )

        if not 0 <= self.MIN_ADVANCE_DECLINE_RATIO <= 1.0:
            errors.append(
                f"MIN_ADVANCE_DECLINE_RATIO 必须在 [0, 1] 范围内，当前: {self.MIN_ADVANCE_DECLINE_RATIO}"
            )

        if self.MARKET_REGIME_LOOKBACK_DAYS <= 0:
            errors.append(
                f"MARKET_REGIME_LOOKBACK_DAYS 必须大于 0，当前: {self.MARKET_REGIME_LOOKBACK_DAYS}"
            )

        if self.MARKET_REGIME_MA_SHORT <= 0:
            errors.append(
                f"MARKET_REGIME_MA_SHORT 必须大于 0，当前: {self.MARKET_REGIME_MA_SHORT}"
            )

        # ========== 交易时段验证 ==========

        if self.AVOID_OPEN_MINUTES < 0:
            errors.append(
                f"AVOID_OPEN_MINUTES 必须非负，当前: {self.AVOID_OPEN_MINUTES}"
            )

        if self.AVOID_CLOSE_MINUTES < 0:
            errors.append(
                f"AVOID_CLOSE_MINUTES 必须非负，当前: {self.AVOID_CLOSE_MINUTES}"
            )

        # ========== 默认账户余额验证 ==========

        if self.DEFAULT_ACCOUNT_BALANCE <= 0:
            errors.append(
                f"DEFAULT_ACCOUNT_BALANCE 必须大于 0，当前: {self.DEFAULT_ACCOUNT_BALANCE}"
            )

        return len(errors) == 0, errors


# 全局单例实例
RISK_LIMITS = RiskLimits()
