"""
测试趋势类技术因子
"""
import unittest
import pandas as pd
import numpy as np
from factors.technical.trend import MA, EMA, MACD, ADX, WMA


class TestTrendFactors(unittest.TestCase):
    """测试趋势类因子"""

    def setUp(self):
        """准备测试数据"""
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

        # 确保 high >= close >= low
        self.data['high'] = self.data[['high', 'close']].max(axis=1)
        self.data['low'] = self.data[['low', 'close']].min(axis=1)

    def test_ma_calculation(self):
        """测试MA计算"""
        ma5 = MA(period=5)
        result = ma5.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertFalse(result.isna().all())
        self.assertTrue(ma5.validate(result))

        # 验证第5个值是前5个收盘价的平均值
        expected = self.data['close'].iloc[:5].mean()
        self.assertAlmostEqual(result.iloc[4], expected, places=2)

    def test_ema_calculation(self):
        """测试EMA计算"""
        ema12 = EMA(period=12)
        result = ema12.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertFalse(result.isna().all())
        self.assertTrue(ema12.validate(result))

    def test_macd_calculation(self):
        """测试MACD计算"""
        macd = MACD()
        result = macd.calculate(self.data)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn('macd_dif', result.columns)
        self.assertIn('macd_dea', result.columns)
        self.assertIn('macd_histogram', result.columns)
        self.assertTrue(macd.validate(result))

        # 验证 histogram = dif - dea
        diff = result['macd_histogram'] - (result['macd_dif'] - result['macd_dea'])
        self.assertTrue((diff.abs() < 1e-10).all())

    def test_adx_calculation(self):
        """测试ADX计算"""
        adx = ADX(period=14)
        result = adx.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertTrue(adx.validate(result))

        # ADX值应该在0-100之间
        valid_values = result.dropna()
        self.assertTrue((valid_values >= 0).all())
        self.assertTrue((valid_values <= 100).all())

    def test_wma_calculation(self):
        """测试WMA计算"""
        wma10 = WMA(period=10)
        result = wma10.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertTrue(wma10.validate(result))

    def test_ma_different_periods(self):
        """测试不同周期的MA"""
        ma5 = MA(period=5)
        ma20 = MA(period=20)

        result5 = ma5.calculate(self.data)
        result20 = ma20.calculate(self.data)

        # MA20应该比MA5更平滑（标准差更小）
        std5 = result5.iloc[20:].std()
        std20 = result20.iloc[20:].std()
        self.assertLess(std20, std5)


if __name__ == '__main__':
    unittest.main()
