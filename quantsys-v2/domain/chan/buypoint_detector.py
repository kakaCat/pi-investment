"""买卖点检测器（笔中枢版）——1/2/3 买 + 1/2/3 卖对称

定义（spec: 2026-08-05-chan-bi-zhongshu-redesign.md）：
- 1买：最后中枢后离开下跌笔底背驰；无中枢退化为最近两下跌笔比较
- 2买：1买后反弹笔成立，回抽下跌笔低点 > 1买低点
- 3买：上笔离开中枢（高 > ZG）后，回抽下跌笔低点 > ZG
- 1卖/2卖/3卖完全对称
"""
from typing import List, Optional
from .types import Bi, BiZhongShu, BuyPoint, KLine
from .bi_divergence_detector import BiDivergenceDetector


class BuyPointDetector:
    def __init__(self):
        self._divergence = BiDivergenceDetector()

    # 供测试 patch 的薄封装
    def _is_bottom_div(self, enter: Bi, leave: Bi, klines: List[KLine]) -> bool:
        return self._divergence.is_bottom_divergence(enter, leave, klines)

    def _is_top_div(self, enter: Bi, leave: Bi, klines: List[KLine]) -> bool:
        return self._divergence.is_top_divergence(enter, leave, klines)

    def detect(
        self,
        bis: List[Bi],
        zhongshus: List[BiZhongShu],
        klines: List[KLine],
        enable_types: Optional[List[str]] = None,
    ) -> List[BuyPoint]:
        points: List[BuyPoint] = []
        points += self._detect_first_buy(bis, zhongshus, klines)
        points += self._detect_first_sell(bis, zhongshus, klines)
        points += self._detect_second_buy(bis, points)
        points += self._detect_second_sell(bis, points)
        points += self._detect_third_buy(bis, zhongshus)
        points += self._detect_third_sell(bis, zhongshus)
        if enable_types:
            points = [p for p in points if p.type in enable_types]
        return points

    # ---------- 1买/1卖 ----------

    def _enter_leave_pairs(self, bis, zhongshus, direction):
        """(进入笔, 离开笔) 候选对：围绕每个中枢；无中枢时退化为所有相邻同向笔对
        （每个历史背驰都应产生信号，不只最近一对——否则 1买后的回抽笔会顶掉 1买本身）"""
        same = [b for b in bis if b.direction == direction]
        pairs = []
        if zhongshus:
            for zs in zhongshus:
                enter_candidates = [b for b in bis[:zs.start_bi_idx] if b.direction == direction]
                leave_candidates = [b for b in bis[zs.end_bi_idx + 1:] if b.direction == direction]
                if enter_candidates and leave_candidates:
                    pairs.append((enter_candidates[-1], leave_candidates[0]))
        if not pairs and len(same) >= 2:
            pairs = [(same[i], same[i + 1]) for i in range(len(same) - 1)]
        return pairs

    def _detect_first_buy(self, bis, zhongshus, klines) -> List[BuyPoint]:
        out = []
        for enter, leave in self._enter_leave_pairs(bis, zhongshus, 'down'):
            if self._is_bottom_div(enter, leave, klines):
                out.append(BuyPoint(
                    type='1买', index=leave.end_fenxing.index, price=leave.low,
                    date=leave.end_fenxing.date, confidence=0.9,
                    reason='下跌笔组底背驰', position_ratio=1.0,
                ))
        return out

    def _detect_first_sell(self, bis, zhongshus, klines) -> List[BuyPoint]:
        out = []
        for enter, leave in self._enter_leave_pairs(bis, zhongshus, 'up'):
            if self._is_top_div(enter, leave, klines):
                out.append(BuyPoint(
                    type='1卖', index=leave.end_fenxing.index, price=leave.high,
                    date=leave.end_fenxing.date, confidence=0.9,
                    reason='上涨笔组顶背驰', position_ratio=1.0,
                ))
        return out

    # ---------- 2买/2卖 ----------

    def _bi_after(self, bis, kline_index: int, direction: str) -> Optional[Bi]:
        """起点 K 线索引在 kline_index 之后的第一条 direction 笔"""
        for b in bis:
            if b.direction == direction and b.start_fenxing.index >= kline_index:
                return b
        return None

    def _detect_second_buy(self, bis, points) -> List[BuyPoint]:
        out = []
        for p in [p for p in points if p.type == '1买']:
            rebound = self._bi_after(bis, p.index, 'up')       # 反弹笔
            if not rebound:
                continue
            pullback = self._bi_after(bis, rebound.end_fenxing.index, 'down')
            if pullback and pullback.low > p.price:            # 不破 1买低点
                out.append(BuyPoint(
                    type='2买', index=pullback.end_fenxing.index, price=pullback.low,
                    date=pullback.end_fenxing.date, confidence=0.7,
                    reason='回抽不破1买低点', position_ratio=0.6,
                ))
        return out

    def _detect_second_sell(self, bis, points) -> List[BuyPoint]:
        out = []
        for p in [p for p in points if p.type == '1卖']:
            retreat = self._bi_after(bis, p.index, 'down')
            if not retreat:
                continue
            rally = self._bi_after(bis, retreat.end_fenxing.index, 'up')
            if rally and rally.high < p.price:                 # 不破 1卖高点
                out.append(BuyPoint(
                    type='2卖', index=rally.end_fenxing.index, price=rally.high,
                    date=rally.end_fenxing.date, confidence=0.7,
                    reason='回拉不破1卖高点', position_ratio=0.6,
                ))
        return out

    # ---------- 3买/3卖 ----------

    def _detect_third_buy(self, bis, zhongshus) -> List[BuyPoint]:
        out = []
        for zs in zhongshus:
            leave = self._bi_after(bis, bis[zs.end_bi_idx].end_fenxing.index, 'up')
            if not leave or leave.high <= zs.zg:               # 未离开中枢
                continue
            pullback = self._bi_after(bis, leave.end_fenxing.index, 'down')
            if pullback and pullback.low > zs.zg:              # 回抽不入中枢
                out.append(BuyPoint(
                    type='3买', index=pullback.end_fenxing.index, price=pullback.low,
                    date=pullback.end_fenxing.date, confidence=0.5,
                    reason='离开中枢回抽不入', position_ratio=0.3,
                ))
        return out

    def _detect_third_sell(self, bis, zhongshus) -> List[BuyPoint]:
        out = []
        for zs in zhongshus:
            leave = self._bi_after(bis, bis[zs.end_bi_idx].end_fenxing.index, 'down')
            if not leave or leave.low >= zs.zd:
                continue
            rally = self._bi_after(bis, leave.end_fenxing.index, 'up')
            if rally and rally.high < zs.zd:                   # 回拉不入中枢
                out.append(BuyPoint(
                    type='3卖', index=rally.end_fenxing.index, price=rally.high,
                    date=rally.end_fenxing.date, confidence=0.5,
                    reason='跌破中枢回拉不入', position_ratio=0.3,
                ))
        return out
