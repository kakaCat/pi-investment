"""线段识别器测试"""
import pytest
from datetime import datetime
from domain.chan.segment_identifier import SegmentIdentifier
from domain.chan.types import Bi, FenXing, KLine


class TestSegmentIdentifier:
    """线段识别器测试类"""

    def test_identify_segment_valid_3bi(self):
        """测试有效线段（至少3笔）"""
        # 构造测试数据
        fx1 = FenXing('bottom', 0, 9.0, datetime(2024, 1, 1), [])
        fx2 = FenXing('top', 5, 11.0, datetime(2024, 1, 6), [])
        fx3 = FenXing('bottom', 10, 10.0, datetime(2024, 1, 11), [])
        fx4 = FenXing('top', 15, 12.0, datetime(2024, 1, 16), [])

        bis = [
            Bi('up', fx1, fx2, 11.0, 9.0, 6, 0.22),
            Bi('down', fx2, fx3, 11.0, 10.0, 6, -0.09),
            Bi('up', fx3, fx4, 12.0, 10.0, 6, 0.20),
        ]

        identifier = SegmentIdentifier()
        segments = identifier.identify_segments(bis)

        # 预期：识别出1个上升线段
        assert len(segments) == 1
        assert segments[0].direction == 'up'
        assert len(segments[0].bis) == 3
        assert segments[0].high == 12.0
        assert segments[0].low == 9.0

    def test_identify_segment_insufficient_bis(self):
        """测试笔数量不足（少于3笔）"""
        fx1 = FenXing('bottom', 0, 9.0, datetime(2024, 1, 1), [])
        fx2 = FenXing('top', 5, 11.0, datetime(2024, 1, 6), [])

        bis = [
            Bi('up', fx1, fx2, 11.0, 9.0, 6, 0.22),
        ]

        identifier = SegmentIdentifier()
        segments = identifier.identify_segments(bis)

        # 预期：无线段（笔数量不足）
        assert len(segments) == 0

    def test_identify_segment_extended(self):
        """测试线段扩展（超过3笔）"""
        fx1 = FenXing('bottom', 0, 9.0, datetime(2024, 1, 1), [])
        fx2 = FenXing('top', 5, 11.0, datetime(2024, 1, 6), [])
        fx3 = FenXing('bottom', 10, 10.0, datetime(2024, 1, 11), [])
        fx4 = FenXing('top', 15, 12.0, datetime(2024, 1, 16), [])
        fx5 = FenXing('bottom', 20, 11.0, datetime(2024, 1, 21), [])
        fx6 = FenXing('top', 25, 13.0, datetime(2024, 1, 26), [])

        bis = [
            Bi('up', fx1, fx2, 11.0, 9.0, 6, 0.22),
            Bi('down', fx2, fx3, 11.0, 10.0, 6, -0.09),
            Bi('up', fx3, fx4, 12.0, 10.0, 6, 0.20),
            Bi('down', fx4, fx5, 12.0, 11.0, 6, -0.08),
            Bi('up', fx5, fx6, 13.0, 11.0, 6, 0.18),
        ]

        identifier = SegmentIdentifier()
        segments = identifier.identify_segments(bis)

        # 预期：识别出1个扩展线段（5笔）
        assert len(segments) == 1
        assert len(segments[0].bis) == 5
        assert segments[0].high == 13.0
        assert segments[0].low == 9.0
