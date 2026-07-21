"""MACD 计算器测试"""
import pytest
import numpy as np
from datetime import datetime, timedelta
from domain.chan.macd_calculator import MACDCalculator
from domain.chan.types import KLine


class TestMACDCalculator:
    """MACD 计算器测试类"""

    def test_calculate_macd_basic(self):
        """测试基本 MACD 计算"""
        # 构造测试数据（30根K线，上涨趋势）
        klines = [
            KLine(
                datetime(2024, 1, 1) + timedelta(days=i),
                10.0 + i * 0.5,
                11.0 + i * 0.5,
                9.0 + i * 0.5,
                10.5 + i * 0.5,
                1000,
                [i]
            )
            for i in range(30)
        ]

        calculator = MACDCalculator()
        macd_df = calculator.calculate(klines)

        # 验证返回的 DataFrame
        assert 'macd' in macd_df.columns
        assert 'signal' in macd_df.columns
        assert 'hist' in macd_df.columns
        assert len(macd_df) == len(klines)

        # MACD 柱在上涨趋势中最后几根应该为正（去除前面的 NaN）
        valid_hist = macd_df['hist'].dropna()
        if len(valid_hist) > 0:
            positive_hist = (valid_hist > 0).sum()
            assert positive_hist > 0  # 至少有正值

    def test_calculate_macd_area(self):
        """测试 MACD 面积计算"""
        # 构造更多数据以确保 MACD 有效
        klines = [
            KLine(
                datetime(2024, 1, 1) + timedelta(days=i),
                10.0 + i * 0.1,  # 更平缓的上涨
                11.0 + i * 0.1,
                9.0 + i * 0.1,
                10.5 + i * 0.1,
                1000,
                [i]
            )
            for i in range(100)
        ]

        calculator = MACDCalculator()
        # 使用更后面的区间
        area = calculator.calculate_area(klines, 50, 80)

        # 验证面积计算函数能正常运行（不报错）
        assert isinstance(area, (int, float))
