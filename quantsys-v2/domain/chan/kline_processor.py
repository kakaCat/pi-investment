"""K线预处理器 - 处理包含关系"""
from typing import List, Optional, Literal
import pandas as pd
from .types import KLine


class KLineProcessor:
    """
    K线预处理器

    职责：处理K线包含关系
    规则：
    - 向上走势：高点取高，低点取高
    - 向下走势：高点取低，低点取低
    """

    def process(
        self,
        raw_klines: pd.DataFrame,
        direction: Optional[Literal['up', 'down']] = None
    ) -> List[KLine]:
        """
        处理K线包含关系

        Args:
            raw_klines: 原始K线DataFrame（columns: date, open, high, low, close, volume）
            direction: 初始方向（None则自动判断）

        Returns:
            处理后的K线列表（无包含关系）
        """
        if len(raw_klines) == 0:
            return []

        # 转换为KLine对象列表
        klines = []
        for idx, row in raw_klines.iterrows():
            kline = KLine(
                date=row['date'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume'],
                original_indices=[idx]
            )
            klines.append(kline)

        if len(klines) < 2:
            return klines

        # 确定初始方向
        if direction is None:
            direction = self._determine_initial_direction(klines[0], klines[1])

        # 处理包含关系
        processed = [klines[0]]
        current_direction = direction

        for i in range(1, len(klines)):
            current = klines[i]
            prev = processed[-1]

            if self._has_inclusion(prev, current):
                # 有包含关系，合并
                merged = self._merge_klines(prev, current, current_direction)
                processed[-1] = merged
            else:
                # 无包含关系，添加并更新方向
                processed.append(current)
                if len(processed) >= 2:
                    current_direction = self._determine_initial_direction(
                        processed[-2], processed[-1]
                    )

        return processed

    def _has_inclusion(self, k1: KLine, k2: KLine) -> bool:
        """判断两根K线是否有包含关系"""
        return (k1.high >= k2.high and k1.low <= k2.low) or \
               (k2.high >= k1.high and k2.low <= k1.low)

    def _merge_klines(self, k1: KLine, k2: KLine, direction: str) -> KLine:
        """合并包含的K线"""
        if direction == 'up':
            # 向上走势：高点取高，低点取高
            return KLine(
                date=k2.date,
                open=k1.open,
                high=max(k1.high, k2.high),
                low=max(k1.low, k2.low),
                close=k2.close,
                volume=k1.volume + k2.volume,
                original_indices=k1.original_indices + k2.original_indices
            )
        else:
            # 向下走势：高点取低，低点取低
            return KLine(
                date=k2.date,
                open=k1.open,
                high=min(k1.high, k2.high),
                low=min(k1.low, k2.low),
                close=k2.close,
                volume=k1.volume + k2.volume,
                original_indices=k1.original_indices + k2.original_indices
            )

    def _determine_initial_direction(self, k1: KLine, k2: KLine) -> Literal['up', 'down']:
        """确定初始方向"""
        if k2.high > k1.high:
            return 'up'
        else:
            return 'down'
