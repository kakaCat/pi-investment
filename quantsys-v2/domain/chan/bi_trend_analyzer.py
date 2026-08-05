"""走势类型分析（笔中枢版）"""
from typing import List, Literal
from .types import Bi, BiZhongShu


class BiTrendAnalyzer:
    """
    - ≥2 中枢依次上移（后 ZD > 前 ZD 且后 ZG > 前 ZG）→ 上涨；依次下移 → 下跌
    - 1 中枢 → 盘整
    - 0 中枢 → 退化为首尾笔高低点比较
    """

    def analyze(
        self,
        bis: List[Bi],
        zhongshus: List[BiZhongShu],
    ) -> Literal['上涨', '下跌', '盘整']:
        if len(zhongshus) >= 2:
            last, prev = zhongshus[-1], zhongshus[-2]
            if last.zd > prev.zd and last.zg > prev.zg:
                return '上涨'
            if last.zd < prev.zd and last.zg < prev.zg:
                return '下跌'
            return '盘整'

        if len(zhongshus) == 1:
            return '盘整'

        # 无中枢退化：比较首笔与末笔高低点
        if len(bis) < 2:
            return '盘整'
        first, last_b = bis[0], bis[-1]
        high_up = last_b.high > first.high
        low_up = last_b.low > first.low
        if high_up and low_up:
            return '上涨'
        if not high_up and not low_up:
            return '下跌'
        return '盘整'
