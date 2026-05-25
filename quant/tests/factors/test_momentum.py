"""
测试动量类技术因子
"""
import unittest
import pandas as pd
import numpy as np
from factors.technical.momentum import RSI, KDJ, CCI, ROC, WilliamsR, MOM, STOCH


class TestMomentumFactors(unittest.TestCase):
    """测试动量类因子"""

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

        self.data['high'] = self.data[['high', 'close']].max(axis=1)
        self.data['low'] = self.data[['low', 'close']].min(axis=1)

    def test_rsi_calculation(self):
        """测试RSI计算"""
        rsi = RSI(period=14)
        result = rsi.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertTrue(rsi.validate(result))

        # RSI值应该在0-100之间
        valid_values = result.dropna()
        self.assertTrue((valid_values >= 0).all())
        self.assertTrue((valid_values <= 100).all())

    def test_kdj_calculation(self):
        """测试KDJ计算"""
        kdj = KDJ()
        result = kdj.calculate(self.data)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn('k', result.columns)
        self.assertIn('d', result.columns)
        self.assertIn('j', result.columns)
        self.assertTrue(kdj.validate(result))

        # 验证 J = 3K - 2D
        diff = result['j'] - (3 * result['k'] - 2 * result['d'])
        self.assertTrue((diff.abs() < 1e-10).all())

    def test_cci_calculation(self):
        """测试CCI计算"""
        cci = CCI(period=20)
        result = cci.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertTrue(cci.validate(result))

    def test_roc_calculation(self):
        """测试ROC计算"""
        roc = ROC(period=12)
        result = roc.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertTrue(roc.validate(result))

    def test_williams_r_calculation(self):
        """测试Williams %R计算"""
        wr = WilliamsR(period=14)
        result = wr.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertTrue(wr.validate(result))

        # Williams %R值应该在-100到0之间（允许小的数值误差）
        valid_values = result.dropna()
        self.assertTrue((valid_values >= -100.1).all())
        self.assertTrue((valid_values <= 0.1).all())

    def test_mom_calculation(self):
        """测试动量指标计算"""
        mom = MOM(period=10)
        result = mom.calculate(self.data)

        self.assertEqual(len(result), len(self.data))
        self.assertTrue(mom.validate(result))

    def test_stoch_calculation(self):
        """测试随机指标计算"""
        stoch = STOCH(k_period=14, d_period=3)
        result = stoch.calculate(self.data)

        self.assertIsInstance(result, pd.DataFrame)
        self.assertIn('stoch_k', result.columns)
        self.assertIn('stoch_d', result.columns)
        self.assertTrue(stoch.validate(result))

        # K和D值应该在0-100之间（允许小的数值误差）
        valid_k = result['stoch_k'].dropna()
        valid_d = result['stoch_d'].dropna()
        self.assertTrue((valid_k >= -0.1).all() and (valid_k <= 100.1).all())
        self.assertTrue((valid_d >= -0.1).all() and (valid_d <= 100.1).all())


if __name__ == '__main__':
    unittest.main()
