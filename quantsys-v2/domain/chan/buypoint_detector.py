"""买卖点检测器 - 识别三类买卖点"""
from typing import List, Dict
from .types import Segment, ZhongShu, BuyPoint, KLine
from datetime import datetime


class BuyPointDetector:
    """
    买卖点检测器

    三类买卖点规则：
    - 1买：下跌背驰后（最安全，满仓）
    - 2买：回调不破中枢（次安全，半仓）
    - 3买：突破前高（激进，轻仓）
    """

    def detect_buypoints(
        self,
        segments: List[Segment],
        zhongshus: List[ZhongShu],
        divergences: Dict[int, bool],
        klines: List[KLine]
    ) -> List[BuyPoint]:
        """
        检测买卖点

        Args:
            segments: 线段列表
            zhongshus: 中枢列表
            divergences: 背驰字典 {segment_index: is_divergence}
            klines: K线数据

        Returns:
            买卖点列表
        """
        buypoints = []

        # 检测1买（下跌背驰）
        for i, seg in enumerate(segments):
            if seg.direction == 'down' and divergences.get(i, False):
                buypoints.append(BuyPoint(
                    type='1买',
                    index=seg.end_index,
                    price=seg.low,
                    date=klines[seg.end_index].date if seg.end_index < len(klines) else datetime.now(),
                    confidence=0.9,
                    reason='下跌背驰',
                    position_ratio=1.0
                ))

        # 检测2买（回调不破中枢）
        for zh in zhongshus:
            # 找中枢后的第一个下跌线段
            zh_end_idx = segments.index(zh.segments[-1])
            if zh_end_idx + 1 < len(segments):
                next_seg = segments[zh_end_idx + 1]
                if next_seg.direction == 'down' and next_seg.low >= zh.low:
                    buypoints.append(BuyPoint(
                        type='2买',
                        index=next_seg.end_index,
                        price=next_seg.low,
                        date=klines[next_seg.end_index].date if next_seg.end_index < len(klines) else datetime.now(),
                        confidence=0.7,
                        reason='回调不破中枢',
                        position_ratio=0.6
                    ))

        # 检测3买（突破前高）
        for i in range(1, len(segments)):
            seg = segments[i]
            if seg.direction == 'up':
                # 找前面的最高点
                prev_ups = [s.high for s in segments[:i] if s.direction == 'up']
                if prev_ups:  # 有前面的上升线段
                    prev_high = max(prev_ups)
                    if seg.high > prev_high:
                        buypoints.append(BuyPoint(
                            type='3买',
                            index=seg.end_index,
                            price=seg.high,
                            date=klines[seg.end_index].date if seg.end_index < len(klines) else datetime.now(),
                            confidence=0.5,
                            reason='突破前高',
                            position_ratio=0.3
                        ))

        return buypoints
