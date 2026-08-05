"""走势类型分析器 - 判断上涨/下跌/盘整

⚠️ DEPRECATED（2026-08-05）：旧线段流水线组件。
流水线已切换笔中枢趋势（bi_trend_analyzer），本文件仅为历史参考保留，勿用于新代码。
"""
from typing import List, Literal
from .types import Segment, ZhongShu


class TrendAnalyzer:
    """
    走势类型分析器

    规则：
    - 有中枢 = 盘整
    - 高点抬升 + 低点抬升 = 上涨
    - 高点下降 + 低点下降 = 下跌
    """

    def analyze(
        self,
        segments: List[Segment],
        zhongshus: List[ZhongShu]
    ) -> Literal['上涨', '下跌', '盘整']:
        """
        分析走势类型

        Args:
            segments: 线段列表
            zhongshus: 中枢列表

        Returns:
            '上涨' / '下跌' / '盘整'
        """
        # 规则1：有中枢 = 盘整
        if len(zhongshus) > 0:
            return '盘整'

        # 规则2：少于2个线段，无法判断
        if len(segments) < 2:
            return '盘整'

        # 规则3：比较首尾线段的高低点
        first_seg = segments[0]
        last_seg = segments[-1]

        high_up = last_seg.high > first_seg.high
        low_up = last_seg.low > first_seg.low

        if high_up and low_up:
            return '上涨'
        elif not high_up and not low_up:
            return '下跌'
        else:
            return '盘整'
