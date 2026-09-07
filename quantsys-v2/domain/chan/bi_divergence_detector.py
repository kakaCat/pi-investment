"""笔组背驰检测器——比较进入/离开笔组的 MACD 面积"""
from typing import List
from .types import Bi, KLine
from .macd_calculator import MACDCalculator


class BiDivergenceDetector:
    """
    底背驰：离开下跌笔最低价 < 进入下跌笔最低价 且 |离开面积| < |进入面积|
    顶背驰：离开上涨笔最高价 > 进入上涨笔最高价 且 |离开面积| < |进入面积|
    """

    def __init__(self):
        self._macd = MACDCalculator()

    def _area(self, bi: Bi, klines: List[KLine]) -> float:
        return self._macd.calculate_area(
            klines, bi.start_fenxing.index, bi.end_fenxing.index)

    def is_bottom_divergence(self, enter: Bi, leave: Bi, klines: List[KLine]) -> bool:
        if enter.direction != 'down' or leave.direction != 'down':
            return False
        if leave.low >= enter.low:   # 必须价格新低
            return False
        return bool(abs(self._area(leave, klines)) < abs(self._area(enter, klines)))

    def is_top_divergence(self, enter: Bi, leave: Bi, klines: List[KLine]) -> bool:
        if enter.direction != 'up' or leave.direction != 'up':
            return False
        if leave.high <= enter.high:  # 必须价格新高
            return False
        return bool(abs(self._area(leave, klines)) < abs(self._area(enter, klines)))
