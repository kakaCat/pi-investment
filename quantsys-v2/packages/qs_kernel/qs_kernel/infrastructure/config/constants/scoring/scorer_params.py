"""
Scorer Parameters Configuration

Centralized configuration for all scorer modules:
- FundamentalScorer: PE, ROE, gross margin, debt ratio, revenue growth thresholds
- TechnicalScorer: RSI, MACD, ADX, volume ratio thresholds
- CapitalScorer: capital flow, volume, acceleration thresholds
- CyclePositionScorer: quarterly margin QoQ, 52w high thresholds
- WeightCalculator: profile weights, regime adjustment coefficients
- DataQualityGate: data quality check thresholds

Created: 2026-09-09
Phase: 2.2 Scorer Parameters
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Any
from ..base import ConfigBase


# ============================================================================
# Fundamental Scorer Configuration
# ============================================================================

@dataclass(frozen=True)
class FundamentalScorerConfig(ConfigBase):
    """
    基本面评分器参数配置

    评分公式：总分 = 基础分 + PE评分 + ROE评分 + 毛利率评分 + 负债率评分 + 营收增长评分 + 财务共振加成
    范围：0-100（自动截断）
    """

    # 基础配置
    base_score: float = 50.0
    min_score: float = 0.0
    max_score: float = 100.0

    # PE 评分阈值 (市盈率)
    pe_negative_score: float = -20.0          # PE < 0
    pe_excellent_threshold: float = 10.0      # PE <= 10
    pe_excellent_score: float = 20.0
    pe_good_threshold: float = 15.0           # PE <= 15
    pe_good_score: float = 15.0
    pe_fair_threshold: float = 25.0           # PE <= 25
    pe_fair_score: float = 10.0
    pe_acceptable_threshold: float = 40.0     # PE <= 40
    pe_acceptable_score: float = 0.0
    pe_warning_threshold: float = 60.0        # PE <= 60
    pe_warning_score: float = -10.0
    pe_poor_score: float = -20.0              # PE > 60

    # ROE 评分阈值 (净资产收益率 %)
    roe_negative_score: float = -20.0         # ROE < 0
    roe_poor_threshold: float = 5.0           # ROE < 5
    roe_poor_score: float = -10.0
    roe_fair_threshold: float = 10.0          # ROE <= 10
    roe_fair_score: float = 5.0
    roe_good_threshold: float = 15.0          # ROE <= 15
    roe_good_score: float = 12.0
    roe_excellent_threshold: float = 20.0     # ROE <= 20
    roe_excellent_score: float = 18.0
    roe_outstanding_score: float = 20.0       # ROE > 20

    # 毛利率评分阈值 (%)
    gross_margin_min_threshold: float = 10.0  # < 10%
    gross_margin_min_score: float = 0.0
    gross_margin_fair_threshold: float = 20.0 # <= 20%
    gross_margin_fair_score: float = 5.0
    gross_margin_good_threshold: float = 30.0 # <= 30%
    gross_margin_good_score: float = 10.0
    gross_margin_excellent_score: float = 15.0 # > 30%

    # 负债率评分阈值 (%)
    debt_ratio_excellent_threshold: float = 30.0  # < 30%
    debt_ratio_excellent_score: float = 15.0
    debt_ratio_good_threshold: float = 50.0       # <= 50%
    debt_ratio_good_score: float = 10.0
    debt_ratio_fair_threshold: float = 70.0       # <= 70%
    debt_ratio_fair_score: float = 5.0
    debt_ratio_poor_score: float = 0.0            # > 70%

    # 营收增长评分阈值 (%)
    revenue_growth_poor_threshold: float = -10.0  # < -10%
    revenue_growth_poor_score: float = 0.0
    revenue_growth_negative_threshold: float = 0.0 # <= 0%
    revenue_growth_negative_score: float = 3.0
    revenue_growth_fair_threshold: float = 10.0    # <= 10%
    revenue_growth_fair_score: float = 8.0
    revenue_growth_good_threshold: float = 30.0    # <= 30%
    revenue_growth_good_score: float = 13.0
    revenue_growth_excellent_score: float = 15.0   # > 30%

    # 财务共振规则阈值
    resonance_value_pe_threshold: float = 20.0     # 价值股：PE < 20
    resonance_value_roe_threshold: float = 15.0    # 且 ROE > 15%
    resonance_value_bonus: float = 10.0

    resonance_growth_margin_threshold: float = 30.0   # 成长股：毛利率 > 30%
    resonance_growth_revenue_threshold: float = 20.0  # 且营收增长 > 20%
    resonance_growth_bonus: float = 5.0

    resonance_quality_debt_threshold: float = 40.0    # 稳健股：负债率 < 40%
    resonance_quality_roe_threshold: float = 15.0     # 且 ROE > 15%
    resonance_quality_bonus: float = 5.0

    resonance_max_bonus: float = 15.0                 # 财务共振最大加成

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证分数范围
        if not (self.min_score <= self.base_score <= self.max_score):
            raise ValueError(
                f"base_score ({self.base_score}) must be between "
                f"min_score ({self.min_score}) and max_score ({self.max_score})"
            )

        # 验证 PE 阈值递增
        if not (0 < self.pe_excellent_threshold < self.pe_good_threshold <
                self.pe_fair_threshold < self.pe_acceptable_threshold <
                self.pe_warning_threshold):
            raise ValueError("PE thresholds must be in ascending order")

        # 验证 ROE 阈值递增
        if not (0 < self.roe_poor_threshold < self.roe_fair_threshold <
                self.roe_good_threshold < self.roe_excellent_threshold):
            raise ValueError("ROE thresholds must be in ascending order")

        # 验证共振规则阈值为正
        if self.resonance_max_bonus < 0:
            raise ValueError("resonance_max_bonus must be non-negative")


# ============================================================================
# Technical Scorer Configuration
# ============================================================================

@dataclass(frozen=True)
class TechnicalScorerConfig(ConfigBase):
    """
    技术面评分器参数配置

    评分公式：总分 = 基础分 + RSI评分 + MACD评分 + ADX评分 + 成交量评分 + 技术共振加成
    范围：0-100（自动截断）
    """

    # 基础配置
    base_score: float = 50.0
    min_score: float = 0.0
    max_score: float = 100.0

    # RSI 评分阈值 (0-100)
    rsi_oversold_threshold: float = 30.0      # RSI < 30 超卖
    rsi_oversold_max_score: float = 20.0
    rsi_neutral_lower: float = 40.0           # 40 <= RSI <= 60 中性区
    rsi_neutral_upper: float = 60.0
    rsi_neutral_score: float = 5.0
    rsi_overbought_threshold: float = 70.0    # RSI > 70 超买
    rsi_overbought_max_score: float = -20.0

    # MACD 评分参数
    macd_golden_base_score: float = 10.0      # 金叉基础分
    macd_golden_max_bonus: float = 10.0       # 金叉强度最大加成
    macd_golden_strength_factor: float = 100.0 # 柱状图绝对值 × 此系数 = 强度分
    macd_death_max_penalty: float = -15.0     # 死叉最大扣分
    macd_death_strength_factor: float = 100.0

    # ADX 趋势强度评分阈值 (0-100)
    adx_no_trend_threshold: float = 25.0      # ADX <= 25 无趋势
    adx_strong_trend_threshold: float = 50.0  # ADX >= 50 强趋势
    adx_max_score: float = 15.0               # ADX 最大得分

    # 成交量评分阈值
    volume_surge_threshold: float = 1.5       # 量比 > 1.5 放量
    volume_surge_max_score: float = 20.0
    volume_surge_factor: float = 20.0         # (量比 - 1) × 此系数
    volume_shrink_threshold: float = 0.8      # 量比 < 0.8 缩量
    volume_shrink_penalty: float = -10.0

    # 技术共振规则
    resonance_rsi_oversold_threshold: float = 30.0     # RSI < 30
    resonance_macd_golden_threshold: float = 10.0      # MACD 得分 > 10 表示金叉
    resonance_oversold_golden_bonus: float = 10.0      # RSI超卖 + MACD金叉

    resonance_volume_surge_threshold: float = 1.5      # 量比 > 1.5
    resonance_adx_trend_threshold: float = 25.0        # ADX > 25
    resonance_volume_trend_bonus: float = 5.0          # 放量 + 强趋势

    resonance_max_bonus: float = 15.0                  # 技术共振最大加成

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证分数范围
        if not (self.min_score <= self.base_score <= self.max_score):
            raise ValueError(
                f"base_score ({self.base_score}) must be between "
                f"min_score ({self.min_score}) and max_score ({self.max_score})"
            )

        # 验证 RSI 阈值
        if not (0 < self.rsi_oversold_threshold < self.rsi_neutral_lower <
                self.rsi_neutral_upper < self.rsi_overbought_threshold < 100):
            raise ValueError("RSI thresholds must be in valid range (0-100)")

        # 验证 ADX 阈值
        if not (0 < self.adx_no_trend_threshold < self.adx_strong_trend_threshold <= 100):
            raise ValueError("ADX thresholds must be in valid range")

        # 验证量比阈值
        if not (0 < self.volume_shrink_threshold < 1.0 < self.volume_surge_threshold):
            raise ValueError("Volume ratio thresholds must span around 1.0")


# ============================================================================
# Capital Scorer Configuration
# ============================================================================

@dataclass(frozen=True)
class CapitalScorerConfig(ConfigBase):
    """
    资金面评分器参数配置

    评分公式：总分 = 基础分 + 主力净流入 + 流入加速 + 量比 + 量能趋势 + 资金共振加成
    范围：0-100（自动截断）
    """

    # 基础配置
    base_score: float = 50.0
    min_score: float = 0.0
    max_score: float = 100.0

    # 主力净流入评分参数
    inflow_max_score: float = 30.0            # 主力净流入最大得分（±30）
    inflow_full_ratio: float = 0.02           # 累计净流入达流通市值 2% 为满分线
    inflow_fallback_threshold: float = 10000.0 # 无市值数据时：累计 ±1 亿元（万元）为满分

    # 流入加速评分参数
    acceleration_max_score: float = 20.0      # 流入加速最大得分
    acceleration_half_score: float = 10.0     # 由流出转流入得分（加速分的一半）
    acceleration_min_days: int = 5            # 最少需要 5 日数据
    acceleration_recent_days: int = 2         # 近 2 日均值
    acceleration_prev_days: int = 3           # 前 3 日均值

    # 量比评分参数
    volume_ratio_surge_threshold: float = 1.5 # 量比 > 1.5 放量
    volume_ratio_max_score: float = 20.0      # 量比最大得分
    volume_ratio_factor: float = 20.0         # (量比 - 1) × 此系数
    volume_ratio_shrink_threshold: float = 0.8 # 量比 < 0.8 缩量
    volume_ratio_shrink_penalty: float = -10.0

    # 量能趋势评分参数
    volume_trend_max_score: float = 15.0      # 5日均量 > 20日均量

    # 资金共振规则
    resonance_inflow_positive: float = 0.0    # 主力净流入 > 0
    resonance_volume_surge_threshold: float = 1.5  # 量比 > 1.5
    resonance_price_rise_threshold: float = 0.0    # 涨跌幅 > 0
    resonance_max_bonus: float = 15.0         # 量价资共振最大加成

    # 数据质量参数
    flow_unit: float = 1e4                    # fund_flows 金额单位：万元 → 元
    outlier_ratio: float = 0.20               # 单日净流入 > 流通市值 20% = 异常值
    consecutive_inflow_threshold: int = 3     # 连续 3 日净流入判定阈值

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证分数范围
        if not (self.min_score <= self.base_score <= self.max_score):
            raise ValueError(
                f"base_score ({self.base_score}) must be between "
                f"min_score ({self.min_score}) and max_score ({self.max_score})"
            )

        # 验证量比阈值
        if not (0 < self.volume_ratio_shrink_threshold < 1.0 < self.volume_ratio_surge_threshold):
            raise ValueError("Volume ratio thresholds must span around 1.0")

        # 验证加速检测参数
        if self.acceleration_recent_days + self.acceleration_prev_days > self.acceleration_min_days:
            raise ValueError(
                f"acceleration_recent_days ({self.acceleration_recent_days}) + "
                f"acceleration_prev_days ({self.acceleration_prev_days}) must be <= "
                f"acceleration_min_days ({self.acceleration_min_days})"
            )


# ============================================================================
# Cycle Position Scorer Configuration
# ============================================================================

@dataclass(frozen=True)
class CyclePositionScorerConfig(ConfigBase):
    """
    周期位置评分器参数配置

    评分公式：总分 = 基础分 + 毛利率QoQ + 距52周高点 + 同向/背离加减成
    范围：0-100（自动截断）
    """

    # 基础配置
    base_score: float = 50.0
    min_score: float = 0.0
    max_score: float = 100.0
    min_quarters: int = 4                     # 最少需要 4 个季度数据

    # 毛利率 QoQ 评分参数
    qoq_max_score: float = 35.0               # 毛利率 QoQ 最大得分（±35）
    qoq_expanding_moderate_score: float = 15.0 # 环比改善（非连续）
    qoq_contracting_moderate_score: float = -15.0 # 环比走弱（非连续）

    # 距 52 周高点评分参数
    high_max_score: float = 35.0              # 距高点最大得分（±35）
    high_golden_lower: float = 0.30           # 回撤 30%-50%：黄金坑
    high_golden_upper: float = 0.50
    high_golden_score: float = 35.0
    high_partial_lower: float = 0.15          # 回撤 15%-30%：部分定价
    high_partial_upper: float = 0.30
    high_partial_score: float = 20.0
    high_deep_threshold: float = 0.50         # 回撤 > 50%：深度回撤
    high_deep_score: float = 10.0
    high_near_threshold: float = 0.10         # 回撤 < 10%：接近高点
    high_near_score: float = -35.0
    high_moderate_score: float = 5.0          # 其他情况

    # 同向/背离评分参数
    alignment_max_score: float = 30.0         # 同向/背离最大得分（±30）
    alignment_golden_drawdown: float = 0.30   # 黄金坑：盈利扩张 + 回撤 >= 30%
    alignment_trap_drawdown: float = 0.10     # 顶部陷阱：盈利收缩 + 回撤 < 10%

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证分数范围
        if not (self.min_score <= self.base_score <= self.max_score):
            raise ValueError(
                f"base_score ({self.base_score}) must be between "
                f"min_score ({self.min_score}) and max_score ({self.max_score})"
            )

        # 验证回撤阈值
        if not (0 < self.high_near_threshold < self.high_partial_lower <
                self.high_partial_upper < self.high_golden_lower <
                self.high_golden_upper < self.high_deep_threshold < 1.0):
            raise ValueError("Drawdown thresholds must be in ascending order")

        # 验证最少季度数
        if self.min_quarters < 3:
            raise ValueError("min_quarters must be at least 3 for QoQ calculation")


# ============================================================================
# Weight Calculator Configuration
# ============================================================================

@dataclass(frozen=True)
class WeightCalculatorConfig(ConfigBase):
    """
    动态权重计算器参数配置

    两段式：
    1. base_weights: profile 基础权重（growth/value 按特征分位插值）
    2. apply_regime: regime 信号连续修正
    """

    # Profile 基础权重端点
    # 格式：Dict[profile, Dict[dimension, (weight_at_0, weight_at_1) | scalar]]
    # growth/value 用 tuple 表示插值端点，其他 profile 用 scalar 表示固定权重
    profile_weight_endpoints: Dict[str, Dict[str, Any]] = None

    # Regime 修正系数
    technical_regime_coef: float = 0.5        # 技术维度修正系数（趋势强度）
    technical_regime_mid: float = 0.5         # 技术维度中性点

    fundamental_regime_coef: float = 0.6      # 基本面维度修正系数（市场风险）
    fundamental_regime_mid: float = 0.4       # 基本面维度中性点

    capital_regime_coef: float = 0.5          # 资金维度修正系数（流动性热度）
    capital_regime_mid: float = 0.5           # 资金维度中性点

    # 权重限幅
    min_weight: float = 0.15                  # 单维度最小权重
    max_weight: float = 0.60                  # 单维度最大权重

    # 默认特征分位（当缺失时使用）
    default_feature_pct: float = 0.5

    def __post_init__(self):
        # 设置默认 profile 权重端点
        if self.profile_weight_endpoints is None:
            object.__setattr__(self, 'profile_weight_endpoints', {
                'growth': {
                    'technical': (0.45, 0.35),
                    'fundamental': (0.30, 0.40),
                    'capital': (0.25, 0.25)
                },
                'value': {
                    'technical': (0.30, 0.20),
                    'fundamental': (0.45, 0.55),
                    'capital': (0.25, 0.25)
                },
                'cyclical': {
                    'technical': 0.25,
                    'fundamental': 0.20,
                    'capital': 0.25,
                    'cycle': 0.30
                },
                'balanced': {
                    'technical': 0.50,
                    'fundamental': 0.30,
                    'capital': 0.20
                }
            })

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证权重限幅范围
        if not (0 < self.min_weight < self.max_weight <= 1.0):
            raise ValueError(
                f"Weight bounds must satisfy: 0 < min_weight ({self.min_weight}) < "
                f"max_weight ({self.max_weight}) <= 1.0"
            )

        # 验证 regime 中性点在 [0, 1] 范围内
        if not (0 <= self.technical_regime_mid <= 1.0):
            raise ValueError("technical_regime_mid must be in [0, 1]")
        if not (0 <= self.fundamental_regime_mid <= 1.0):
            raise ValueError("fundamental_regime_mid must be in [0, 1]")
        if not (0 <= self.capital_regime_mid <= 1.0):
            raise ValueError("capital_regime_mid must be in [0, 1]")

        # 验证特征分位默认值
        if not (0 <= self.default_feature_pct <= 1.0):
            raise ValueError("default_feature_pct must be in [0, 1]")


# ============================================================================
# Data Quality Gate Configuration
# ============================================================================

@dataclass(frozen=True)
class DataQualityGateConfig(ConfigBase):
    """
    数据质量门参数配置

    检测与自动修复：
    1. 脏 bar 剔除（close<=0、amount=0 但 volume>0）
    2. 近端缺口补抓（最后一根 K 线距今超过阈值）
    3. 修复预算控制
    """

    # 最小 K 线数量
    min_klines: int = 120                     # 最少需要 120 根 K 线

    # 近端缺口判定
    stale_days: int = 4                       # 最后一根 K 线距今超过 4 天 = 近端缺口

    # 脏数据检测
    recent_dirty_window: int = 10             # amount=0 脏数据仅判定最近 10 根
                                              # （历史 07-13 遗留容忍）

    # 修复预算
    default_repair_budget: int = 20           # 单实例最多补抓 20 次

    def validate(self) -> None:
        """验证配置参数的合理性"""
        # 验证最小 K 线数量
        if self.min_klines < 60:
            raise ValueError("min_klines should be at least 60 for indicator calculation")

        # 验证陈旧天数
        if self.stale_days < 1:
            raise ValueError("stale_days must be at least 1")

        # 验证脏数据窗口
        if self.recent_dirty_window < 1:
            raise ValueError("recent_dirty_window must be at least 1")

        # 验证修复预算
        if self.default_repair_budget < 0:
            raise ValueError("default_repair_budget must be non-negative")


# ============================================================================
# Default Instances
# ============================================================================

# 全局默认配置实例
DEFAULT_FUNDAMENTAL_SCORER_CONFIG = FundamentalScorerConfig()
DEFAULT_TECHNICAL_SCORER_CONFIG = TechnicalScorerConfig()
DEFAULT_CAPITAL_SCORER_CONFIG = CapitalScorerConfig()
DEFAULT_CYCLE_POSITION_SCORER_CONFIG = CyclePositionScorerConfig()
DEFAULT_WEIGHT_CALCULATOR_CONFIG = WeightCalculatorConfig()
DEFAULT_DATA_QUALITY_GATE_CONFIG = DataQualityGateConfig()
