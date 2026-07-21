"""背驰检测器 - MACD 面积背驰"""
from typing import List, Literal
from .types import Segment, KLine
from .macd_calculator import MACDCalculator


class DivergenceDetector:
    """
    背驰检测器

    使用真实 MACD 面积判断背驰
    - 顶背驰：价格新高，MACD 面积减小
    - 底背驰：价格新低，MACD 面积增大
    """

    def __init__(self):
        self.macd_calculator = MACDCalculator()

    def detect_divergence(
        self,
        seg1: Segment,
        seg2: Segment,
        klines: List[KLine],
        divergence_type: Literal['bullish', 'bearish']
    ) -> bool:
        """
        检测两个线段间是否背驰

        Args:
            seg1: 前一个线段
            seg2: 后一个线段
            klines: 完整K线数据
            divergence_type: 'bullish'(底背驰) 或 'bearish'(顶背驰)

        Returns:
            是否背驰
        """
        # 计算 MACD 面积
        area1 = self._calculate_macd_area(seg1, klines)
        area2 = self._calculate_macd_area(seg2, klines)

        if divergence_type == 'bearish':
            # 顶背驰：价格新高 且 MACD面积减小
            return seg2.high > seg1.high and area2 < area1
        else:
            # 底背驰：价格新低 且 MACD面积增大（绝对值减小）
            return seg2.low < seg1.low and abs(area2) < abs(area1)

    def _calculate_macd_area(self, segment: Segment, klines: List[KLine]) -> float:
        """
        计算线段对应的 MACD 柱面积

        使用真实 MACD 计算器
        """
        return self.macd_calculator.calculate_area(
            klines,
            segment.start_index,
            segment.end_index
        )
