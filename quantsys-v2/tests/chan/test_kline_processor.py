"""K线预处理器测试"""
import pytest
from datetime import datetime, timedelta
import pandas as pd
from domain.chan.kline_processor import KLineProcessor
from domain.chan.types import KLine


class TestKLineProcessor:
    """K线预处理器测试类"""

    def test_process_no_inclusion(self):
        """测试无包含关系的K线"""
        raw_data = pd.DataFrame({
            'date': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(3)],
            'open': [10.0, 11.0, 12.0],
            'high': [10.5, 11.5, 12.5],
            'low': [9.5, 10.5, 11.5],
            'close': [10.2, 11.2, 12.2],
            'volume': [1000, 1100, 1200]
        })

        processor = KLineProcessor()
        result = processor.process(raw_data)

        # 预期：3根K线无包含关系，保持原样
        assert len(result) == 3
        assert result[0].high == 10.5
        assert result[1].high == 11.5
        assert result[2].high == 12.5

    def test_process_inclusion_uptrend(self):
        """测试向上走势的包含关系处理"""
        raw_data = pd.DataFrame({
            'date': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(3)],
            'open': [10.0, 10.2, 11.0],
            'high': [10.5, 10.3, 11.5],  # 第2根被第1根包含
            'low': [9.5, 9.8, 10.5],     # 第2根被第1根包含
            'close': [10.2, 10.1, 11.2],
            'volume': [1000, 500, 1200]
        })

        processor = KLineProcessor()
        result = processor.process(raw_data, direction='up')

        # 预期：合并后2根K线
        assert len(result) == 2
        # 向上走势：高点取高，低点取高
        assert result[0].high == 10.5
        assert result[0].low == 9.8  # 低点取高
        assert result[0].volume == 1500  # 成交量合并
        assert len(result[0].original_indices) == 2  # 记录原始索引

    def test_process_inclusion_downtrend(self):
        """测试向下走势的包含关系处理"""
        raw_data = pd.DataFrame({
            'date': [datetime(2024, 1, 1) + timedelta(days=i) for i in range(3)],
            'open': [12.0, 11.8, 10.0],
            'high': [12.5, 12.2, 10.5],  # 第2根被第1根包含
            'low': [11.5, 11.7, 9.5],     # 第2根被第1根包含
            'close': [11.8, 11.9, 10.2],
            'volume': [1000, 500, 1200]
        })

        processor = KLineProcessor()
        result = processor.process(raw_data, direction='down')

        # 预期：合并后2根K线
        assert len(result) == 2
        # 向下走势：高点取低，低点取低
        assert result[0].high == 12.2  # 高点取低
        assert result[0].low == 11.5
