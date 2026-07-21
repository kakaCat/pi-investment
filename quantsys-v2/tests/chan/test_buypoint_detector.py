"""买卖点检测器测试"""
import pytest
from datetime import datetime, timedelta
from domain.chan.buypoint_detector import BuyPointDetector
from domain.chan.types import Segment, ZhongShu, KLine


class TestBuyPointDetector:
    """买卖点检测器测试类"""

    def test_detect_first_buy(self):
        """测试1买（下跌背驰）"""
        klines = [KLine(datetime(2024, 1, i+1), 10.0, 11.0, 9.0, 10.5, 1000, [i]) for i in range(30)]

        segments = [
            Segment('down', [], 0, 10, high=12.0, low=9.0),
            Segment('up', [], 10, 15, high=11.0, low=9.5),
            Segment('down', [], 15, 25, high=10.5, low=8.5),  # 背驰
        ]

        zhongshus = []
        divergences = {2: True}  # segments[2] 背驰

        detector = BuyPointDetector()
        buypoints = detector.detect_buypoints(segments, zhongshus, divergences, klines)

        # 预期：识别出1买
        assert len(buypoints) >= 1
        first_buy = [bp for bp in buypoints if bp.type == '1买']
        assert len(first_buy) == 1
        assert first_buy[0].position_ratio == 1.0  # 满仓

    def test_detect_second_buy(self):
        """测试2买（回调不破中枢）"""
        klines = [KLine(datetime(2024, 1, 1) + timedelta(days=i), 10.0, 11.0, 9.0, 10.5, 1000, [i]) for i in range(50)]

        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=12.5, low=10.0),
            Segment('down', [], 30, 40, high=11.8, low=10.2),  # 回调不破中枢
        ]

        zhongshus = [
            ZhongShu(segments[:3], high=11.5, low=10.0, start_index=0, end_index=30, type='震荡')
        ]
        divergences = {}

        detector = BuyPointDetector()
        buypoints = detector.detect_buypoints(segments, zhongshus, divergences, klines)

        # 预期：识别出2买
        second_buy = [bp for bp in buypoints if bp.type == '2买']
        assert len(second_buy) >= 1
        assert second_buy[0].position_ratio == 0.6  # 半仓

    def test_detect_third_buy(self):
        """测试3买（突破前高）"""
        klines = [KLine(datetime(2024, 1, 1) + timedelta(days=i), 10.0, 11.0, 9.0, 10.5, 1000, [i]) for i in range(50)]

        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=13.5, low=10.0),  # 突破前高
        ]

        zhongshus = []
        divergences = {}

        detector = BuyPointDetector()
        buypoints = detector.detect_buypoints(segments, zhongshus, divergences, klines)

        # 预期：识别出3买
        third_buy = [bp for bp in buypoints if bp.type == '3买']
        assert len(third_buy) >= 1
        assert third_buy[0].position_ratio == 0.3  # 轻仓
