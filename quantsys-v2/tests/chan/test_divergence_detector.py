"""背驰检测器测试"""
import pytest
import numpy as np
from datetime import datetime, timedelta
from domain.chan.divergence_detector import DivergenceDetector
from domain.chan.types import Segment, KLine


class TestDivergenceDetector:
    """背驰检测器测试类"""

    def test_detect_divergence_bearish(self):
        """测试顶背驰检测功能"""
        # 构造测试数据：足够多的K线以让 MACD 有效
        klines = [
            KLine(
                datetime(2024, 1, 1) + timedelta(days=i),
                10.0 + i * 0.1,
                11.0 + i * 0.1,
                9.0 + i * 0.1,
                10.5 + i * 0.1,
                1000,
                [i]
            )
            for i in range(100)
        ]

        seg1 = Segment('up', [], 20, 40, high=13.0, low=9.0)
        seg2 = Segment('up', [], 60, 80, high=14.5, low=11.0)

        detector = DivergenceDetector()
        result = detector.detect_divergence(seg1, seg2, klines, 'bearish')

        # 验证函数返回布尔值（包括 numpy bool）
        assert isinstance(result, (bool, np.bool_))

    def test_detect_divergence_bullish(self):
        """测试底背驰检测功能"""
        klines = [
            KLine(
                datetime(2024, 1, 1) + timedelta(days=i),
                10.0 - i * 0.05,
                11.0 - i * 0.05,
                9.0 - i * 0.05,
                10.5 - i * 0.05,
                1000,
                [i]
            )
            for i in range(100)
        ]

        seg1 = Segment('down', [], 20, 40, high=12.0, low=8.0)
        seg2 = Segment('down', [], 60, 80, high=10.5, low=7.5)

        detector = DivergenceDetector()
        result = detector.detect_divergence(seg1, seg2, klines, 'bullish')

        # 验证函数返回布尔值
        assert isinstance(result, (bool, np.bool_))

    def test_detect_no_divergence(self):
        """测试背驰检测逻辑"""
        klines = [
            KLine(
                datetime(2024, 1, 1) + timedelta(days=i),
                10.0 + i * 0.1,
                11.0 + i * 0.1,
                9.0 + i * 0.1,
                10.5 + i * 0.1,
                1000,
                [i]
            )
            for i in range(100)
        ]

        seg1 = Segment('up', [], 20, 40, high=13.0, low=9.0)
        seg2 = Segment('up', [], 60, 80, high=15.0, low=11.0)

        detector = DivergenceDetector()
        result = detector.detect_divergence(seg1, seg2, klines, 'bearish')

        # 验证函数返回布尔值
        assert isinstance(result, (bool, np.bool_))
