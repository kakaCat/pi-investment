"""
测试因子计算器
"""
import unittest
import pandas as pd
import numpy as np
from factors.calculator import FactorCalculator
from factors.technical.trend import MA, EMA, MACD
from factors.technical.momentum import RSI, KDJ


class TestFactorCalculator(unittest.TestCase):
    """测试因子计算器"""

    def setUp(self):
        """准备测试数据和计算器"""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        np.random.seed(42)

        self.data = pd.DataFrame({
            'date': dates,
            'open': 100 + np.random.randn(100).cumsum(),
            'high': 102 + np.random.randn(100).cumsum(),
            'low': 98 + np.random.randn(100).cumsum(),
            'close': 100 + np.random.randn(100).cumsum(),
            'volume': np.random.randint(1000000, 5000000, 100)
        })

        self.data['high'] = self.data[['high', 'close']].max(axis=1)
        self.data['low'] = self.data[['low', 'close']].min(axis=1)

        self.calculator = FactorCalculator(max_workers=2)

    def test_register_factor(self):
        """测试注册因子"""
        ma5 = MA(period=5)
        self.calculator.register(ma5)

        self.assertEqual(len(self.calculator), 1)
        self.assertIn('MA5', self.calculator.factors)

    def test_register_batch(self):
        """测试批量注册因子"""
        factors = [
            MA(period=5),
            MA(period=20),
            EMA(period=12),
            RSI(period=14)
        ]
        self.calculator.register_batch(factors)

        self.assertEqual(len(self.calculator), 4)

    def test_calculate_single(self):
        """测试计算单个因子"""
        ma5 = MA(period=5)
        self.calculator.register(ma5)

        result = self.calculator.calculate_single('MA5', self.data)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), len(self.data))

    def test_calculate_batch(self):
        """测试批量计算因子"""
        factors = [
            MA(period=5),
            MA(period=20),
            RSI(period=14)
        ]
        self.calculator.register_batch(factors)

        result = self.calculator.calculate_batch(['MA5', 'MA20', 'RSI14'], self.data)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result.columns), 3)
        self.assertIn('MA5', result.columns)
        self.assertIn('MA20', result.columns)
        self.assertIn('RSI14', result.columns)

    def test_calculate_all(self):
        """测试计算所有因子"""
        factors = [
            MA(period=5),
            EMA(period=12),
            RSI(period=14)
        ]
        self.calculator.register_batch(factors)

        result = self.calculator.calculate_all(self.data)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result.columns), 3)

    def test_calculate_by_category(self):
        """测试按类别计算因子"""
        factors = [
            MA(period=5),
            EMA(period=12),
            RSI(period=14)
        ]
        self.calculator.register_batch(factors)

        result = self.calculator.calculate_all(self.data, category='technical')

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result.columns), 3)

    def test_get_factor_list(self):
        """测试获取因子列表"""
        factors = [
            MA(period=5),
            RSI(period=14)
        ]
        self.calculator.register_batch(factors)

        factor_list = self.calculator.get_factor_list()

        self.assertEqual(len(factor_list), 2)
        self.assertTrue(all('name' in f for f in factor_list))
        self.assertTrue(all('category' in f for f in factor_list))

    def test_parallel_calculation(self):
        """测试并行计算"""
        factors = [
            MA(period=5),
            MA(period=10),
            MA(period=20),
            RSI(period=14)
        ]
        self.calculator.register_batch(factors)

        # 并行计算
        result_parallel = self.calculator.calculate_batch(
            ['MA5', 'MA10', 'MA20', 'RSI14'],
            self.data,
            parallel=True
        )

        # 串行计算
        result_serial = self.calculator.calculate_batch(
            ['MA5', 'MA10', 'MA20', 'RSI14'],
            self.data,
            parallel=False
        )

        # 结果应该相同
        pd.testing.assert_frame_equal(result_parallel, result_serial)

    def test_invalid_factor_name(self):
        """测试无效的因子名称"""
        with self.assertRaises(ValueError):
            self.calculator.calculate_single('INVALID_FACTOR', self.data)


if __name__ == '__main__':
    unittest.main()
