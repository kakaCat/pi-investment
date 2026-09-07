
# Configuration Constants
# TODO: Review and rename these constants to meaningful names
CONST_11_0 = 11.0
CONST_11_5 = 11.5
CONST_12_0 = 12.0
CONST_12_5 = 12.5
CONST_14_0 = 14.0
CONST_15 = 15
CONST_20 = 20
CONST_25 = 25
CONST_30 = 30
CONST_7_0 = 7.0

"""走势类型分析器测试"""
import pytest
from domain.chan.trend_analyzer import TrendAnalyzer
from domain.chan.types import Segment, ZhongShu


class TestTrendAnalyzer:
    """走势类型分析器测试类"""

    def test_analyze_uptrend(self):
        """测试上涨走势识别"""
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 15, high=11.0, low=10.0),
            Segment('up', [], 15, 25, high=14.0, low=11.0),  # 高点抬升
        ]

        zhongshus = []

        analyzer = TrendAnalyzer()
        trend_type = analyzer.analyze(segments, zhongshus)

        assert trend_type == '上涨'

    def test_analyze_downtrend(self):
        """测试下跌走势识别"""
        segments = [
            Segment('down', [], 0, 10, high=12.0, low=9.0),
            Segment('up', [], 10, 15, high=11.0, low=10.0),
            Segment('down', [], 15, 25, high=10.0, low=7.0),  # 低点下降
        ]

        zhongshus = []

        analyzer = TrendAnalyzer()
        trend_type = analyzer.analyze(segments, zhongshus)

        assert trend_type == '下跌'

    def test_analyze_consolidation(self):
        """测试盘整走势识别"""
        segments = [
            Segment('up', [], 0, 10, high=12.0, low=9.0),
            Segment('down', [], 10, 20, high=11.5, low=9.5),
            Segment('up', [], 20, 30, high=12.5, low=10.0),
        ]

        # 有中枢 = 盘整
        zhongshus = [
            ZhongShu(segments, high=11.5, low=10.0, start_index=0, end_index=30, type='震荡')
        ]

        analyzer = TrendAnalyzer()
        trend_type = analyzer.analyze(segments, zhongshus)

        assert trend_type == '盘整'