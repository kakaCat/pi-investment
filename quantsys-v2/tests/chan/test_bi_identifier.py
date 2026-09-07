"""笔识别器测试"""
import pytest
from datetime import datetime, timedelta
from domain.chan.bi_identifier import BiIdentifier
from domain.chan.types import KLine, FenXing


class TestBiIdentifier:
    """笔识别器测试类"""

    def test_identify_top_fenxing(self):
        """测试顶分型识别"""
        klines = [
            KLine(datetime(2024, 1, 1), 10.0, 10.5, 9.5, 10.2, 1000, [0]),
            KLine(datetime(2024, 1, 2), 10.2, 11.5, 10.5, 11.2, 1100, [1]),  # 顶分型
            KLine(datetime(2024, 1, 3), 11.2, 11.0, 10.0, 10.8, 1200, [2]),
        ]

        identifier = BiIdentifier()
        fenxings = identifier.identify_fenxings(klines)

        # 预期：识别出1个顶分型
        assert len(fenxings) == 1
        assert fenxings[0].type == 'top'
        assert fenxings[0].index == 1
        assert fenxings[0].price == 11.5

    def test_identify_bottom_fenxing(self):
        """测试底分型识别"""
        klines = [
            KLine(datetime(2024, 1, 1), 11.0, 11.5, 10.5, 10.8, 1000, [0]),
            KLine(datetime(2024, 1, 2), 10.8, 10.0, 9.0, 9.5, 1100, [1]),  # 底分型
            KLine(datetime(2024, 1, 3), 9.5, 10.5, 9.8, 10.2, 1200, [2]),
        ]

        identifier = BiIdentifier()
        fenxings = identifier.identify_fenxings(klines)

        # 预期：识别出1个底分型
        assert len(fenxings) == 1
        assert fenxings[0].type == 'bottom'
        assert fenxings[0].index == 1
        assert fenxings[0].price == 9.0

    def test_identify_bi_valid_5k_rule(self):
        """测试有效笔（满足5K规则）"""
        klines = [
            KLine(datetime(2024, 1, i+1), 10.0, 10.0 + i*0.5, 9.0 + i*0.5, 9.5 + i*0.5, 1000, [i])
            for i in range(10)
        ]

        fenxings = [
            FenXing('bottom', 0, 9.0, datetime(2024, 1, 1), [klines[0]]),
            FenXing('top', 5, 12.5, datetime(2024, 1, 6), [klines[5]]),  # 6根K线
        ]

        identifier = BiIdentifier()
        bis = identifier.identify_bis(fenxings, klines)

        # 预期：识别出1个上笔（满足5K规则）
        assert len(bis) == 1
        assert bis[0].direction == 'up'
        assert bis[0].length == 6

    def test_identify_bi_invalid_5k_rule(self):
        """测试无效笔（不满足5K规则）"""
        klines = [
            KLine(datetime(2024, 1, i+1), 10.0, 10.0 + i*0.5, 9.0 + i*0.5, 9.5 + i*0.5, 1000, [i])
            for i in range(10)
        ]

        fenxings = [
            FenXing('bottom', 0, 9.0, datetime(2024, 1, 1), [klines[0]]),
            FenXing('top', 3, 11.5, datetime(2024, 1, 4), [klines[3]]),  # 只有4根K线
        ]

        identifier = BiIdentifier()
        bis = identifier.identify_bis(fenxings, klines)

        # 预期：无笔（不满足5K规则）
        assert len(bis) == 0
