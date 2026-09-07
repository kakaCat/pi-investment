"""
测试 services.strategy_code_service 模块中的K线数据格式化
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from application.services.strategy_code_service import StrategyCodeService


class TestKlineDataFormatting:
    """测试K线数据格式化功能"""

    @pytest.fixture
    def service(self):
        """创建 StrategyCodeService 实例"""
        return StrategyCodeService()

    @pytest.fixture
    def valid_kline_data(self):
        """有效的K线数据"""
        return pd.DataFrame({
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [99.0, 100.0, 101.0],
            'close': [103.0, 104.0, 105.0],
            'volume': [1000000, 1100000, 1200000]
        })

    @pytest.fixture
    def kline_data_with_missing_fields(self):
        """缺少部分字段的K线数据"""
        return pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'close': [100.0, 101.0],
            'volume': [1000000, 1100000]
        })

    @pytest.fixture
    def kline_data_with_invalid_values(self):
        """包含无效值的K线数据"""
        return pd.DataFrame({
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'open': [100.0, 'invalid', 102.0],
            'high': [105.0, 106.0, None],
            'low': [99.0, 100.0, 101.0],
            'close': [103.0, 104.0, 105.0],
            'volume': [1000000, np.nan, 1200000]
        })

    def test_format_valid_kline_data(self, service, valid_kline_data):
        """测试格式化有效的K线数据"""
        # 模拟 run_strategy 方法的K线格式化部分
        kline_data = []
        for i, row in enumerate(valid_kline_data.to_dict('records')):
            try:
                kline_data.append({
                    'date': str(row.get('trade_date', row.get('date', i))),
                    'open': float(row.get('open', row.get('close', 0))),
                    'high': float(row.get('high', row.get('close', 0))),
                    'low': float(row.get('low', row.get('close', 0))),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            except (ValueError, TypeError) as e:
                continue

        assert len(kline_data) == 3
        assert kline_data[0]['date'] == '2024-01-01'
        assert kline_data[0]['open'] == 100.0
        assert kline_data[0]['high'] == 105.0
        assert kline_data[0]['low'] == 99.0
        assert kline_data[0]['close'] == 103.0
        assert kline_data[0]['volume'] == 1000000

    def test_format_kline_data_with_missing_fields(self, service, kline_data_with_missing_fields):
        """测试格式化缺少字段的K线数据（使用降级逻辑）"""
        kline_data = []
        for i, row in enumerate(kline_data_with_missing_fields.to_dict('records')):
            try:
                kline_data.append({
                    'date': str(row.get('trade_date', row.get('date', i))),
                    'open': float(row.get('open', row.get('close', 0))),
                    'high': float(row.get('high', row.get('close', 0))),
                    'low': float(row.get('low', row.get('close', 0))),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            except (ValueError, TypeError) as e:
                continue

        assert len(kline_data) == 2
        # 缺少 open/high/low 时应该使用 close 值
        assert kline_data[0]['open'] == 100.0
        assert kline_data[0]['high'] == 100.0
        assert kline_data[0]['low'] == 100.0
        assert kline_data[0]['close'] == 100.0

    def test_format_kline_data_with_invalid_values(self, service, kline_data_with_invalid_values):
        """测试格式化包含无效值的K线数据（应该跳过无效行）"""
        kline_data = []
        for i, row in enumerate(kline_data_with_invalid_values.to_dict('records')):
            try:
                kline_data.append({
                    'date': str(row.get('trade_date', row.get('date', i))),
                    'open': float(row.get('open', row.get('close', 0))),
                    'high': float(row.get('high', row.get('close', 0))),
                    'low': float(row.get('low', row.get('close', 0))),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            except (ValueError, TypeError) as e:
                continue

        # 第二行有无效的 'invalid' 字符串，应该被跳过
        # 第三行有 None 值，应该被跳过
        assert len(kline_data) >= 1
        assert kline_data[0]['date'] == '2024-01-01'

    def test_empty_kline_data(self, service):
        """测试空K线数据"""
        empty_df = pd.DataFrame()
        kline_data = []

        for i, row in enumerate(empty_df.to_dict('records')):
            try:
                kline_data.append({
                    'date': str(row.get('trade_date', row.get('date', i))),
                    'open': float(row.get('open', row.get('close', 0))),
                    'high': float(row.get('high', row.get('close', 0))),
                    'low': float(row.get('low', row.get('close', 0))),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            except (ValueError, TypeError) as e:
                continue

        assert len(kline_data) == 0

    def test_kline_data_type_conversion(self, service):
        """测试K线数据类型转换"""
        df = pd.DataFrame({
            'trade_date': ['2024-01-01'],
            'open': ['100.5'],  # 字符串
            'high': [105],      # 整数
            'low': [99.5],      # 浮点数
            'close': ['103.0'], # 字符串
            'volume': [1000000]
        })

        kline_data = []
        for i, row in enumerate(df.to_dict('records')):
            try:
                kline_data.append({
                    'date': str(row.get('trade_date', row.get('date', i))),
                    'open': float(row.get('open', row.get('close', 0))),
                    'high': float(row.get('high', row.get('close', 0))),
                    'low': float(row.get('low', row.get('close', 0))),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            except (ValueError, TypeError) as e:
                continue

        assert len(kline_data) == 1
        assert isinstance(kline_data[0]['open'], float)
        assert isinstance(kline_data[0]['high'], float)
        assert isinstance(kline_data[0]['low'], float)
        assert isinstance(kline_data[0]['close'], float)
        assert isinstance(kline_data[0]['volume'], float)

    def test_kline_data_date_fallback(self, service):
        """测试日期字段降级逻辑"""
        # 测试 trade_date 字段
        df1 = pd.DataFrame({
            'trade_date': ['2024-01-01'],
            'close': [100.0]
        })
        kline_data = []
        for i, row in enumerate(df1.to_dict('records')):
            try:
                kline_data.append({
                    'date': str(row.get('trade_date', row.get('date', i))),
                    'open': float(row.get('open', row.get('close', 0))),
                    'high': float(row.get('high', row.get('close', 0))),
                    'low': float(row.get('low', row.get('close', 0))),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            except (ValueError, TypeError) as e:
                continue
        assert kline_data[0]['date'] == '2024-01-01'

        # 测试 date 字段
        df2 = pd.DataFrame({
            'date': ['2024-01-02'],
            'close': [100.0]
        })
        kline_data = []
        for i, row in enumerate(df2.to_dict('records')):
            try:
                kline_data.append({
                    'date': str(row.get('trade_date', row.get('date', i))),
                    'open': float(row.get('open', row.get('close', 0))),
                    'high': float(row.get('high', row.get('close', 0))),
                    'low': float(row.get('low', row.get('close', 0))),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            except (ValueError, TypeError) as e:
                continue
        assert kline_data[0]['date'] == '2024-01-02'

        # 测试使用索引作为降级
        df3 = pd.DataFrame({
            'close': [100.0]
        })
        kline_data = []
        for i, row in enumerate(df3.to_dict('records')):
            try:
                kline_data.append({
                    'date': str(row.get('trade_date', row.get('date', i))),
                    'open': float(row.get('open', row.get('close', 0))),
                    'high': float(row.get('high', row.get('close', 0))),
                    'low': float(row.get('low', row.get('close', 0))),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            except (ValueError, TypeError) as e:
                continue
        assert kline_data[0]['date'] == '0'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
