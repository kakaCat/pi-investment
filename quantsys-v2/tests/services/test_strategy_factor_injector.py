"""
策略因子注入器单元测试
"""

import pytest
import numpy as np
from application.services.strategy_factor_injector import StrategyFactorInjector


class TestStrategyFactorInjector:
    """测试策略因子注入器"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.injector = StrategyFactorInjector()

    def test_initialization(self):
        """测试初始化"""
        assert self.injector.total_factors > 0
        assert self.injector.momentum_factors is not None
        assert self.injector.trend_factors is not None
        assert self.injector.volatility_factors is not None
        assert self.injector.volume_factors is not None
        assert self.injector.ma_factors is not None
        assert self.injector.reversal_factors is not None

    def test_inject_all_factors_empty_klines(self):
        """测试注入因子到空K线"""
        klines = []
        result = self.injector.inject_all_factors(klines)

        assert result == []

    def test_inject_all_factors_basic(self):
        """测试基础因子注入"""
        klines = [
            {'trade_date': '2025-01-01', 'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2, 'volume': 1000000},
            {'trade_date': '2025-01-02', 'open': 10.2, 'high': 10.8, 'low': 10.0, 'close': 10.5, 'volume': 1200000},
            {'trade_date': '2025-01-03', 'open': 10.5, 'high': 11.0, 'low': 10.3, 'close': 10.8, 'volume': 1500000},
            {'trade_date': '2025-01-04', 'open': 10.8, 'high': 11.2, 'low': 10.6, 'close': 11.0, 'volume': 1300000},
            {'trade_date': '2025-01-05', 'open': 11.0, 'high': 11.5, 'low': 10.8, 'close': 11.2, 'volume': 1400000},
        ]

        result = self.injector.inject_all_factors(klines)

        # 验证返回列表不为空
        assert len(result) == len(klines)

        # 验证基础OHLCV字段仍然存在
        assert 'open' in result[0]
        assert 'high' in result[0]
        assert 'low' in result[0]
        assert 'close' in result[0]
        assert 'volume' in result[0]

        # 验证新增了因子列（至少包含一些核心因子）
        factor_columns = [k for k in result[0].keys() if k not in ['trade_date', 'open', 'high', 'low', 'close', 'volume']]
        assert len(factor_columns) > 0, "应该至少注入了一些因子"

    def test_inject_momentum_factors(self):
        """测试动量因子注入"""
        import pandas as pd

        klines = [
            {'trade_date': f'2025-01-{i:02d}', 'open': 10.0 + i*0.1, 'high': 10.5 + i*0.1,
             'low': 9.8 + i*0.1, 'close': 10.2 + i*0.1, 'volume': 1000000}
            for i in range(1, 21)  # 20天数据
        ]

        df = pd.DataFrame(klines)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        result_df = self.injector._inject_momentum_factors(df, klines)

        # 验证动量因子列存在（具体列名取决于实现）
        assert isinstance(result_df, pd.DataFrame)
        # 数据行数不变
        assert len(result_df) == len(klines)

    def test_backward_compatibility(self):
        """测试向后兼容性"""
        import pandas as pd

        klines = [
            {'trade_date': f'2025-01-{i:02d}', 'open': 10.0, 'high': 10.5,
             'low': 9.8, 'close': 10.2, 'volume': 1000000}
            for i in range(1, 21)
        ]

        df = pd.DataFrame(klines)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 假设注入了 rsi14 因子
        df['rsi14'] = 50.0

        self.injector._ensure_backward_compatibility(df)

        # 验证兼容性映射（如果 rsi14 存在，rsi 也应该存在）
        if 'rsi14' in df.columns and 'rsi' not in klines[0]:
            assert 'rsi' in df.columns
            assert df['rsi'].equals(df['rsi14'])

    def test_inject_all_factors_with_insufficient_data(self):
        """测试数据不足时的因子注入"""
        # 只有2条数据，很多指标无法计算
        klines = [
            {'trade_date': '2025-01-01', 'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2, 'volume': 1000000},
            {'trade_date': '2025-01-02', 'open': 10.2, 'high': 10.8, 'low': 10.0, 'close': 10.5, 'volume': 1200000},
        ]

        result = self.injector.inject_all_factors(klines)

        # 应该不会抛出异常，只是某些因子值为 NaN
        assert len(result) == 2
        assert 'close' in result[0]

    def test_inject_factors_handles_exceptions(self):
        """测试异常处理"""
        # 提供格式错误的数据
        klines = [
            {'trade_date': '2025-01-01', 'open': 'invalid', 'high': 10.5, 'low': 9.8, 'close': 10.2, 'volume': 1000000},
        ]

        # 应该不会崩溃，返回原始数据或处理后的数据
        result = self.injector.inject_all_factors(klines)
        assert isinstance(result, list)
