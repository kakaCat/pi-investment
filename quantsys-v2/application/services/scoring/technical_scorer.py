"""
技术面评分引擎

实现基于技术指标的股票评分逻辑，包括：
- RSI 灰度化评分
- MACD 强度评分
- ADX 趋势确认
- 成交量评分
- 多指标共振加成
"""

from typing import Dict, Any, Optional
import logging
from .base_scorer import BaseScorer
from infrastructure.config.constants.scoring.scorer_params import (
    TechnicalScorerConfig,
    DEFAULT_TECHNICAL_SCORER_CONFIG,
)

logger = logging.getLogger(__name__)


class TechnicalScorer(BaseScorer):
    """
    技术面评分引擎

    评分公式：
    总分 = 基础分(50) + RSI(±20) + MACD(±20) + ADX(0-15) + 成交量(±20) + 共振(0-15)
    范围：0-100（自动截断）
    """

    def __init__(self, factor_adapter=None, config: Optional[TechnicalScorerConfig] = None):
        """
        初始化技术面评分器

        Args:
            factor_adapter: 因子计算适配器（可选，用于扩展）
            config: 评分器配置，None 时使用默认配置
        """
        self.factor_adapter = factor_adapter
        self.config = config or DEFAULT_TECHNICAL_SCORER_CONFIG

    def score(
        self,
        factors: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        计算技术面评分

        Args:
            factors: 技术指标字典，必须包含：
                - rsi: RSI指标值 (0-100)
                - macd: MACD快线值
                - macd_signal: MACD信号线值
                - macd_prev: 前一日MACD值
                - macd_signal_prev: 前一日信号线值
                - adx: ADX趋势强度 (0-100)
                - volume_ratio_5d: 5日成交量比

        Returns:
            {
                'total': 85.0,
                'breakdown': {
                    'base': 50.0,
                    'rsi': 18.5,
                    'macd': 15.0,
                    'adx': 10.0,
                    'volume': 16.0,
                    'resonance': 10.0
                }
            }
        """
        # 基础分
        base = self.config.base_score

        # 各维度评分
        rsi_score = self._score_rsi(factors.get('rsi', 50))
        macd_score = self._score_macd(factors)
        adx_score = self._score_adx(factors.get('adx', 0))
        volume_score = self._score_volume(factors)

        # 构建 breakdown
        breakdown = {
            'base': base,
            'rsi': rsi_score,
            'macd': macd_score,
            'adx': adx_score,
            'volume': volume_score,
        }

        # 共振加成
        resonance_score = self._calculate_resonance(factors, breakdown)
        breakdown['resonance'] = resonance_score

        # 计算总分并截断
        total = base + rsi_score + macd_score + adx_score + volume_score + resonance_score
        total = max(self.config.min_score, min(self.config.max_score, total))

        return {
            'total': round(total, 2),
            'breakdown': {k: round(v, 2) for k, v in breakdown.items()}
        }

    def _score_rsi(self, rsi: float) -> float:
        """
        RSI 灰度化评分（±20分）

        评分曲线：
        - rsi=0   → +20分（极度超卖）
        - rsi=30  → +0分（超卖边界）
        - rsi=40-60 → +5分（中性区间）
        - rsi=70  → +0分（超买边界）
        - rsi=100 → -20分（极度超买）

        Args:
            rsi: RSI指标值 (0-100)

        Returns:
            评分 (-20 到 +20)
        """
        cfg = self.config

        if rsi < cfg.rsi_oversold_threshold:
            # 超卖区：线性加分
            return cfg.rsi_oversold_max_score * (cfg.rsi_oversold_threshold - rsi) / cfg.rsi_oversold_threshold
        elif rsi > cfg.rsi_overbought_threshold:
            # 超买区：线性扣分
            return cfg.rsi_overbought_max_score * (rsi - cfg.rsi_overbought_threshold) / (100 - cfg.rsi_overbought_threshold)
        elif cfg.rsi_neutral_lower <= rsi <= cfg.rsi_neutral_upper:
            # 中性区：小幅加分
            return cfg.rsi_neutral_score
        return 0

    def _score_macd(self, factors: Dict) -> float:
        """
        MACD 强度评分（±20分）

        金叉：基础10分 + 柱状图强度（最多10分）
        死叉：扣分（最多-15分）

        Args:
            factors: 包含 macd, macd_signal, macd_prev, macd_signal_prev

        Returns:
            评分 (-15 到 +20)
        """
        cfg = self.config
        macd = factors.get('macd', 0)
        signal = factors.get('macd_signal', 0)
        hist = macd - signal  # 柱状图

        if self._is_golden_cross(factors):
            # 金叉强度 = 基础分 + 柱状图绝对值 × 系数
            strength = min(cfg.macd_golden_max_bonus, abs(hist) * cfg.macd_golden_strength_factor)
            return cfg.macd_golden_base_score + strength
        elif macd < signal:
            # 死叉扣分
            return -min(-cfg.macd_death_max_penalty, abs(hist) * cfg.macd_death_strength_factor)
        return 0

    def _is_golden_cross(self, factors: Dict) -> bool:
        """
        判断 MACD 金叉

        金叉定义：当前 MACD > 信号线 且 前一日 MACD <= 信号线

        Args:
            factors: 包含 macd, macd_signal, macd_prev, macd_signal_prev

        Returns:
            True 表示金叉，False 表示非金叉
        """
        macd = factors.get('macd', 0)
        signal = factors.get('macd_signal', 0)
        macd_prev = factors.get('macd_prev', 0)
        signal_prev = factors.get('macd_signal_prev', 0)

        return macd > signal and macd_prev <= signal_prev

    def _score_adx(self, adx: float) -> float:
        """
        ADX 趋势强度评分（0-15分）

        - adx < 20  → 0分（无趋势）
        - adx = 25  → 0分（弱趋势边界）
        - adx = 50  → 15分（强趋势）
        - adx > 50  → 15分（极强趋势）

        Args:
            adx: ADX指标值 (0-100)

        Returns:
            评分 (0 到 15)
        """
        cfg = self.config
        if adx <= cfg.adx_no_trend_threshold:
            return 0
        # 从 25 到 50 线性增长到 15 分
        return min(cfg.adx_max_score, (adx - cfg.adx_no_trend_threshold) /
                   (cfg.adx_strong_trend_threshold - cfg.adx_no_trend_threshold) * cfg.adx_max_score)

    def _score_volume(self, factors: Dict) -> float:
        """
        成交量评分（±20分）

        - 5日量比 > 1.5 → 最多+20分
        - 5日量比 < 0.8 → -10分（缩量）

        Args:
            factors: 包含 volume_ratio_5d

        Returns:
            评分 (-10 到 +20)
        """
        cfg = self.config
        volume_ratio = factors.get('volume_ratio_5d', 1.0)

        if volume_ratio > cfg.volume_surge_threshold:
            # 放量：线性加分，最多20分
            return min(cfg.volume_surge_max_score, (volume_ratio - 1) * cfg.volume_surge_factor)
        elif volume_ratio < cfg.volume_shrink_threshold:
            # 缩量：扣分
            return cfg.volume_shrink_penalty
        return 0

    def _calculate_resonance(self, factors: Dict, breakdown: Dict) -> float:
        """
        多指标共振加成（0-15分）

        规则：
        1. RSI超卖(rsi<30) + MACD金叉 → +10分
        2. 放量(ratio>1.5) + 强趋势(adx>25) → +5分

        最多累计15分

        Args:
            factors: 技术指标字典
            breakdown: 各维度评分明细

        Returns:
            共振加成分 (0 到 15)
        """
        cfg = self.config
        bonus = 0
        rsi = factors.get('rsi', 50)
        volume_ratio = factors.get('volume_ratio_5d', 1.0)
        adx = factors.get('adx', 0)

        # 规则1：RSI超卖 + MACD金叉
        # MACD得分>10表示金叉
        if rsi < cfg.resonance_rsi_oversold_threshold and breakdown.get('macd', 0) > cfg.resonance_macd_golden_threshold:
            bonus += cfg.resonance_oversold_golden_bonus

        # 规则2：放量 + 强趋势
        if volume_ratio > cfg.resonance_volume_surge_threshold and adx > cfg.resonance_adx_trend_threshold:
            bonus += cfg.resonance_volume_trend_bonus

        return min(bonus, cfg.resonance_max_bonus)
