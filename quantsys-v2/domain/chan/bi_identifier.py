"""笔识别器 - 识别顶底分型和笔"""
from typing import List
from .types import KLine, FenXing, Bi


class BiIdentifier:
    """
    笔识别器

    职责：
    1. 识别顶底分型（3K模式）
    2. 根据严格5K规则识别笔
    """

    def identify_fenxings(self, klines: List[KLine]) -> List[FenXing]:
        """
        识别顶底分型

        规则：
        - 顶分型：中间K线高点>左右K线高点 且 中间K线低点>左右K线低点
        - 底分型：中间K线高点<左右K线高点 且 中间K线低点<左右K线低点
        """
        if len(klines) < 3:
            return []

        fenxings = []

        for i in range(1, len(klines) - 1):
            k_left = klines[i - 1]
            k_mid = klines[i]
            k_right = klines[i + 1]

            # 检查顶分型
            if self._is_top_fenxing(k_left, k_mid, k_right):
                fenxings.append(FenXing(
                    type='top',
                    index=i,
                    price=k_mid.high,
                    date=k_mid.date,
                    klines=[k_left, k_mid, k_right]
                ))
            # 检查底分型
            elif self._is_bottom_fenxing(k_left, k_mid, k_right):
                fenxings.append(FenXing(
                    type='bottom',
                    index=i,
                    price=k_mid.low,
                    date=k_mid.date,
                    klines=[k_left, k_mid, k_right]
                ))

        return fenxings

    def _is_top_fenxing(self, k1: KLine, k2: KLine, k3: KLine) -> bool:
        """判断是否为顶分型"""
        return (k2.high > k1.high and k2.high > k3.high and
                k2.low > k1.low and k2.low > k3.low)

    def _is_bottom_fenxing(self, k1: KLine, k2: KLine, k3: KLine) -> bool:
        """判断是否为底分型"""
        return (k2.high < k1.high and k2.high < k3.high and
                k2.low < k1.low and k2.low < k3.low)

    def identify_bis(self, fenxings: List[FenXing], klines: List[KLine]) -> List[Bi]:
        """
        识别笔

        规则（严格5K）：
        - 顶底分型之间至少5根K线（含分型的3根）
        - 方向明确（上笔/下笔）
        """
        if len(fenxings) < 2:
            return []

        bis = []

        for i in range(len(fenxings) - 1):
            fx1 = fenxings[i]
            fx2 = fenxings[i + 1]

            # 检查K线数量（至少5根）
            kline_count = fx2.index - fx1.index + 1
            if kline_count < 5:
                continue

            # 检查方向一致性
            if fx1.type == 'bottom' and fx2.type == 'top':
                # 上笔
                if fx2.price > fx1.price:
                    bis.append(Bi(
                        direction='up',
                        start_fenxing=fx1,
                        end_fenxing=fx2,
                        high=fx2.price,
                        low=fx1.price,
                        length=kline_count,
                        price_change=(fx2.price - fx1.price) / fx1.price
                    ))
            elif fx1.type == 'top' and fx2.type == 'bottom':
                # 下笔
                if fx2.price < fx1.price:
                    bis.append(Bi(
                        direction='down',
                        start_fenxing=fx1,
                        end_fenxing=fx2,
                        high=fx1.price,
                        low=fx2.price,
                        length=kline_count,
                        price_change=(fx2.price - fx1.price) / fx1.price
                    ))

        return bis
