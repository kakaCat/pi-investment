"""中枢识别器测试"""
import pytest
from datetime import datetime
from domain.chan.zhongshu_identifier import ZhongShuIdentifier
from domain.chan.types import Segment, Bi, FenXing, KLine


class TestZhongShuIdentifier:
    """中枢识别器测试类"""

    def test_identify_zhongshu_valid_3segments(self):
        """测试有效中枢（3个线段重叠）"""
        # 构造3个有重叠的线段
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=12.5, low=10.0),
        ]

        identifier = ZhongShuIdentifier()
        zhongshus = identifier.identify_zhongshus(segments)

        # 预期：识别出1个中枢
        assert len(zhongshus) == 1
        assert zhongshus[0].high == 11.5  # min(12.0, 11.5, 12.5)
        assert zhongshus[0].low == 10.0   # max(9.0, 9.5, 10.0)
        assert len(zhongshus[0].segments) == 3

    def test_identify_zhongshu_no_overlap(self):
        """测试无重叠（无中枢）"""
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.0, low=8.0),
            Segment('up', [], 20, 30, high=14.0, low=12.5),  # 无重叠
        ]

        identifier = ZhongShuIdentifier()
        zhongshus = identifier.identify_zhongshus(segments)

        # 预期：无中枢
        assert len(zhongshus) == 0

    def test_identify_zhongshu_extended(self):
        """测试中枢扩展（超过3个线段）"""
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=12.5, low=10.0),
            Segment('down', [], 30, 40, high=11.8, low=9.8),  # 继续重叠
        ]

        identifier = ZhongShuIdentifier()
        zhongshus = identifier.identify_zhongshus(segments)

        # 预期：1个扩展中枢（4个线段）
        assert len(zhongshus) == 1
        assert len(zhongshus[0].segments) == 4
