"""
Detection & Technical Analysis Configuration

Centralized configuration for detection and technical analysis modules:
- ManipulationDetector: Market manipulation detection thresholds
- MarketRegimeDetector: Market regime identification parameters
- TechnicalAnalysisService: Technical indicators and analysis parameters

Created: 2026-09-09
Phase: 3 Detection & Technical Analysis
"""

from dataclasses import dataclass
from typing import List
from .base import ConfigBase


# ============================================================================
# Manipulation Detector Configuration
# ============================================================================

@dataclass(frozen=True)
class ManipulationDetectorConfig(ConfigBase):
    """
    操纵检测器参数配置

    检测市场操纵行为（拉高出货等），识别风险和机会
    """

    # 扫描控制参数
    scan_timeout_seconds: float = 15.0      # 扫描超时（秒）
    max_scan_stocks: int = 20               # 最大扫描股票数

    # 操纵信号检测阈值
    consecutive_zt_threshold: int = 3       # 连续涨停判定阈值（天）
    min_signal_count: int = 3               # 判定操纵的最少信号数
    turnover_rate_threshold: float = 30.0   # 换手率异常阈值（%）
    volume_surge_multiplier: float = 3.0    # 成交量放大倍数
    volume_surge_recent_days: int = 3       # 放量对比近端窗口（天）
    stagnation_lookback_days: int = 10      # 高位滞涨回看天数
    lhb_lookback_days: int = 5              # 龙虎榜回查天数
    fund_flow_lookback_days: int = 10       # 资金流回查天数
    min_fund_flow_records: int = 5          # 最少资金流记录数

    # 置信度计算参数
    confidence_base: float = 0.5            # 基础置信度
    confidence_per_signal: float = 0.15     # 每个信号增加的置信度
    confidence_max: float = 0.95            # 最大置信度

    # 价格估算参数
    daily_limit_gain: float = 0.10          # 每日涨停幅度（10%）
    fair_value_retracement: float = 0.5     # 公允价值回撤比例（50%）

    # 风险评估阈值
    extreme_risk_deviation: float = 50.0    # 极端风险偏离度（%）
    high_risk_deviation: float = 30.0       # 高风险偏离度（%）

    # 崩盘判定参数
    collapse_min_days: int = 7              # 崩盘最少天数
    collapse_price_tolerance: float = 0.2   # 价格偏离容忍度（±20%）

    # 抄底机会参数
    bottom_fishing_confidence: float = 0.75  # 崩盘完成抄底置信度

    # 龙虎榜游资席位关键词
    hot_money_keywords: List[str] = None    # 游资席位关键词列表

    def __post_init__(self):
        """初始化默认游资席位关键词"""
        if self.hot_money_keywords is None:
            object.__setattr__(self, 'hot_money_keywords', [
                '东方财富证券拉萨',
                '国泰君安成都',
                '华泰证券深圳',
                '银河证券绍兴',
                '中信证券杭州'
            ])

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证扫描参数
        if self.scan_timeout_seconds <= 0:
            raise ValueError("scan_timeout_seconds must be positive")
        if self.max_scan_stocks <= 0:
            raise ValueError("max_scan_stocks must be positive")

        # 验证阈值
        if self.consecutive_zt_threshold < 1:
            raise ValueError("consecutive_zt_threshold must be at least 1")
        if self.min_signal_count < 1:
            raise ValueError("min_signal_count must be at least 1")
        if self.turnover_rate_threshold <= 0:
            raise ValueError("turnover_rate_threshold must be positive")
        if self.volume_surge_multiplier <= 1.0:
            raise ValueError("volume_surge_multiplier must be greater than 1.0")
        if self.volume_surge_recent_days <= 0:
            raise ValueError("volume_surge_recent_days must be positive")
        if self.stagnation_lookback_days <= 0:
            raise ValueError("stagnation_lookback_days must be positive")

        # 验证置信度参数
        if not (0 <= self.confidence_base <= 1):
            raise ValueError("confidence_base must be in [0, 1]")
        if self.confidence_per_signal <= 0:
            raise ValueError("confidence_per_signal must be positive")
        if not (0 <= self.confidence_max <= 1):
            raise ValueError("confidence_max must be in [0, 1]")
        if not (0 < self.bottom_fishing_confidence <= 1):
            raise ValueError("bottom_fishing_confidence must be in (0, 1]")

        # 验证风险阈值
        if self.extreme_risk_deviation <= self.high_risk_deviation:
            raise ValueError("extreme_risk_deviation must be greater than high_risk_deviation")


# ============================================================================
# Market Regime Detector Configuration
# ============================================================================

@dataclass(frozen=True)
class MarketRegimeDetectorConfig(ConfigBase):
    """
    市场环境识别器参数配置

    识别当前市场状态（牛市/熊市/震荡市）
    """

    # 数据要求
    min_klines: int = 120                   # 最少K线数量
    fetch_klines: int = 150                 # 获取K线数量
    weeks_52_days: int = 252                # 52周交易日数

    # ADX（平均趋向指数）参数
    adx_period: int = 14                    # ADX计算周期
    adx_strong_threshold: float = 25.0      # 强趋势阈值（ADX>该值判强趋势）
    adx_default: float = 20.0               # 默认ADX值（计算失败时）

    # 波动率参数
    volatility_period: int = 20             # 波动率计算周期
    volatility_annualize_factor: float = 15.8745  # 年化系数 sqrt(252)
    volatility_low_threshold: float = 0.15  # 低波动阈值（15%）
    volatility_medium_threshold: float = 0.25  # 中波动阈值（25%）
    volatility_default: float = 0.20        # 默认波动率（20%）

    # 动量计算参数
    momentum_short_period: int = 20         # 短期动量周期
    momentum_long_period: int = 60          # 长期动量周期

    # 价格位置评分阈值
    price_position_bull: float = 0.7        # 牛市价格位置（70%）
    price_position_bear: float = 0.3        # 熊市价格位置（30%）
    price_position_default: float = 0.5     # 默认价格位置

    # 趋势评分阈值
    momentum_short_bull: float = 0.05       # 短期牛市动量（5%）
    momentum_short_bear: float = -0.05      # 短期熊市动量（-5%）
    momentum_long_bull: float = 0.10        # 长期牛市动量（10%）
    momentum_long_bear: float = -0.10       # 长期熊市动量（-10%）

    # 移动平均线参数
    ma_short: int = 20                      # 短期均线
    ma_medium: int = 60                     # 中期均线
    ma_long: int = 120                      # 长期均线

    # 评分权重
    score_trend: float = 2.0                # 趋势评分权重
    score_price_position_high: float = 2.0  # 价格位置高/低权重
    score_price_position_mid: float = 1.0   # 价格位置中等权重
    score_ma_arrangement: float = 2.0       # 均线排列权重
    score_momentum: float = 1.0             # 动量权重
    score_volatility: float = 0.5           # 波动率权重

    # 默认置信度
    confidence_default: float = 0.50        # 默认置信度（数据不足时）
    confidence_min: float = 0.33            # 最低置信度

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证数据要求
        if self.min_klines < 60:
            raise ValueError("min_klines should be at least 60")
        if self.fetch_klines < self.min_klines:
            raise ValueError("fetch_klines must be >= min_klines")

        # 验证ADX参数
        if self.adx_period < 5:
            raise ValueError("adx_period should be at least 5")
        if self.adx_strong_threshold <= self.adx_default:
            raise ValueError("adx_strong_threshold must be greater than adx_default")

        # 验证波动率阈值
        if not (0 < self.volatility_low_threshold < self.volatility_medium_threshold):
            raise ValueError("Volatility thresholds must be in ascending order")

        # 验证价格位置阈值
        if not (0 < self.price_position_bear < self.price_position_bull < 1):
            raise ValueError("Price position thresholds must be in range (0, 1)")

        # 验证动量阈值
        if self.momentum_short_bear >= self.momentum_short_bull:
            raise ValueError("momentum_short_bear must be less than momentum_short_bull")
        if self.momentum_long_bear >= self.momentum_long_bull:
            raise ValueError("momentum_long_bear must be less than momentum_long_bull")

        # 验证均线参数
        if not (0 < self.ma_short < self.ma_medium < self.ma_long):
            raise ValueError("Moving average periods must be in ascending order")


# ============================================================================
# Technical Analysis Service Configuration
# ============================================================================

@dataclass(frozen=True)
class TechnicalAnalysisConfig(ConfigBase):
    """
    技术分析服务参数配置

    提供价格行为分析、买入区间计算、退出计划、K线形态分析
    """

    # 数据获取参数
    default_period_days: int = 60           # 默认分析周期（天）
    price_action_extra_days: int = 10       # 价格行为分析额外天数
    buy_range_period_days: int = 120        # 买入区间分析周期
    exit_plan_period_days: int = 30         # 退出计划分析周期
    candlestick_extra_days: int = 5         # K线形态分析额外天数

    # 移动平均线参数
    ma_short: int = 5                       # 短期均线（MA5）
    ma_medium: int = 10                     # 中期均线（MA10）
    ma_long: int = 20                       # 长期均线（MA20）

    # 布林带参数
    bollinger_period: int = 20              # 布林带周期
    bollinger_std_multiplier: float = 2.0   # 标准差倍数
    bollinger_data_window: int = 60         # 布林带数据窗口（天）
    bollinger_default_upper_pct: float = 0.05  # 默认上界偏离（5%）
    bollinger_default_lower_pct: float = 0.05  # 默认下界偏离（5%）

    # 涨跌幅验证
    max_reasonable_change_pct: float = 30.0 # 最大合理涨跌幅（%）

    # 退出计划参数
    stop_loss_pct: float = 0.08             # 止损比例（8%）
    take_profit_1_pct: float = 0.10         # 第一止盈比例（10%）
    take_profit_2_pct: float = 0.20         # 第二止盈比例（20%）

    # K线形态检测参数
    candlestick_period: int = 30            # K线形态分析默认周期（天）
    doji_body_threshold_pct: float = 0.01   # 十字星实体阈值（1%）

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证周期参数
        if self.default_period_days < 20:
            raise ValueError("default_period_days should be at least 20")
        if self.buy_range_period_days < 60:
            raise ValueError("buy_range_period_days should be at least 60")

        # 验证均线参数
        if not (0 < self.ma_short < self.ma_medium < self.ma_long):
            raise ValueError("Moving average periods must be in ascending order")

        # 验证布林带参数
        if self.bollinger_period < 10:
            raise ValueError("bollinger_period should be at least 10")
        if self.bollinger_std_multiplier <= 0:
            raise ValueError("bollinger_std_multiplier must be positive")

        # 验证退出计划参数
        if not (0 < self.stop_loss_pct < 1):
            raise ValueError("stop_loss_pct must be in range (0, 1)")
        if not (0 < self.take_profit_1_pct < self.take_profit_2_pct):
            raise ValueError("take_profit_1_pct must be less than take_profit_2_pct")

        # 验证K线形态参数
        if self.doji_body_threshold_pct <= 0:
            raise ValueError("doji_body_threshold_pct must be positive")


# ============================================================================
# Default Instances
# ============================================================================

# 全局默认配置实例
DEFAULT_MANIPULATION_DETECTOR_CONFIG = ManipulationDetectorConfig()
DEFAULT_MARKET_REGIME_DETECTOR_CONFIG = MarketRegimeDetectorConfig()
DEFAULT_TECHNICAL_ANALYSIS_CONFIG = TechnicalAnalysisConfig()
