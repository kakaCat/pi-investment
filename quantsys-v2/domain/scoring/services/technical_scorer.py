"""
技术面评分引擎（领域层）

实现基于技术指标的股票评分逻辑，包括：
- RSI 灰度化评分（平滑化）
- MACD 强度评分（平滑化）
- ADX 趋势确认
- 成交量评分
- 多指标共振加成
"""

from typing import Dict, Any, Optional
import logging
import math
import numpy as np

logger = logging.getLogger(__name__)


class TechnicalScorer:
    """
    技术面评分引擎（领域层）

    评分公式：
    总分 = 基础分(50) + RSI(±15) + MACD(±10) + ADX(0-15) + 成交量(±20) + 共振(0-15)
    范围：0-100（自动截断）
    
    改进：
    - MACD 使用 tanh 平滑（替代金叉/死叉离散事件）
    - RSI 使用 sigmoid 平滑（替代线性跳变）
    """

    def __init__(self, factor_adapter=None):
        """
        初始化技术面评分器

        Args:
            factor_adapter: 因子计算适配器（可选，用于扩展）
        """
        self.factor_adapter = factor_adapter

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
        base = 50.0

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
        total = max(0, min(100, total))

        return {
            'total': round(total, 2),
            'breakdown': {k: round(v, 2) for k, v in breakdown.items()}
        }

    def _score_rsi(self, rsi: float) -> float:
        """
        RSI 平滑评分（±15分，连续过渡）
        
        原理：
        - RSI=50 为中性（0 分）
        - RSI<30 超卖（正分，最多+15分）
        - RSI>70 超买（负分，最多-15分）
        - 用 sigmoid 函数平滑过渡
        
        Args:
            rsi: RSI 指标值（0-100）
            
        Returns:
            评分（-15 到 +15）
        """
        # 超卖区（RSI<30）：加分
        if rsi < 30:
            # sigmoid 平滑：RSI=0 时 +15 分，RSI=30 时 0 分
            return 15 / (1 + math.exp(-(30 - rsi - 15) / 5))
        # 超买区（RSI>70）：扣分
        elif rsi > 70:
            # sigmoid 平滑：RSI=100 时 -15 分，RSI=70 时 0 分
            return -15 / (1 + math.exp(-(rsi - 70 - 15) / 5))
        # 中性区（30-70）：0 分
        else:
            return 0.0

    def _score_macd(self, factors: Dict) -> float:
        """
        MACD 平滑评分（±10分，不再突变）
        
        原理：
        - 不再区分金叉/死叉（离散事件）
        - 用 tanh 函数平滑过渡（连续函数）
        - hist 越大分越高，hist 越小分越低
        
        Args:
            factors: 包含 macd, macd_signal
            
        Returns:
            评分（-10 到 +10）
        """
        macd = factors.get('macd', 0)
        signal = factors.get('macd_signal', 0)
        hist = macd - signal
        
        # tanh 平滑：hist=0 时得 0 分，hist→+∞ 时得 +10 分
        # scale=30 让评分更平滑，避免单日大幅波动
        return 10 * math.tanh(hist * 30)

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
        if adx <= 25:
            return 0
        # 从 25 到 50 线性增长到 15 分
        return min(15, (adx - 25) / 25 * 15)

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
        volume_ratio = factors.get('volume_ratio_5d', 1.0)

        if volume_ratio > 1.5:
            # 放量：线性加分，最多20分
            return min(20, (volume_ratio - 1) * 20)
        elif volume_ratio < 0.8:
            # 缩量：扣分
            return -10
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
        bonus = 0
        rsi = factors.get('rsi', 50)
        volume_ratio = factors.get('volume_ratio_5d', 1.0)
        adx = factors.get('adx', 0)

        # 规则1：RSI超卖 + MACD金叉
        # MACD得分>10表示金叉
        if rsi < 30 and breakdown.get('macd', 0) > 10:
            bonus += 10

        # 规则2：放量 + 强趋势
        if volume_ratio > 1.5 and adx > 25:
            bonus += 5

        return min(bonus, 15)
