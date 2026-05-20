"""
测试因子缓存
"""
import unittest
import os
import tempfile
import shutil
import pandas as pd
import numpy as np
from factors.cache import FactorCache


class TestFactorCache(unittest.TestCase):
    """测试因子缓存"""

    def setUp(self):
        """准备测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = FactorCache(cache_dir=self.temp_dir, ttl_hours=1)

        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        self.test_series = pd.Series(
            np.random.randn(50),
            index=dates,
            name='test_factor'
        )

    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_set_and_get_cache(self):
        """测试设置和获取缓存"""
        self.cache.set(
            factor_name='MA5',
            symbol='000001',
            start_date='2024-01-01',
            end_date='2024-02-20',
            value=self.test_series
        )

        result = self.cache.get(
            factor_name='MA5',
            symbol='000001',
            start_date='2024-01-01',
            end_date='2024-02-20'
        )

        self.assertIsNotNone(result)
        pd.testing.assert_series_equal(result, self.test_series)

    def test_cache_miss(self):
        """测试缓存未命中"""
        result = self.cache.get(
            factor_name='NONEXISTENT',
            symbol='000001',
            start_date='2024-01-01',
            end_date='2024-02-20'
        )

        self.assertIsNone(result)

    def test_cache_key_uniqueness(self):
        """测试缓存键的唯一性"""
        # 设置两个不同的缓存
        series1 = pd.Series([1, 2, 3])
        series2 = pd.Series([4, 5, 6])

        self.cache.set('MA5', '000001', '2024-01-01', '2024-02-20', series1)
        self.cache.set('MA5', '000002', '2024-01-01', '2024-02-20', series2)

        result1 = self.cache.get('MA5', '000001', '2024-01-01', '2024-02-20')
        result2 = self.cache.get('MA5', '000002', '2024-01-01', '2024-02-20')

        pd.testing.assert_series_equal(result1, series1)
        pd.testing.assert_series_equal(result2, series2)

    def test_clear_cache(self):
        """测试清除缓存"""
        self.cache.set('MA5', '000001', '2024-01-01', '2024-02-20', self.test_series)
        self.cache.set('RSI14', '000001', '2024-01-01', '2024-02-20', self.test_series)

        count = self.cache.clear()

        self.assertGreater(count, 0)

        # 验证缓存已清除
        result = self.cache.get('MA5', '000001', '2024-01-01', '2024-02-20')
        self.assertIsNone(result)

    def test_cache_stats(self):
        """测试缓存统计"""
        self.cache.set('MA5', '000001', '2024-01-01', '2024-02-20', self.test_series)
        self.cache.set('RSI14', '000001', '2024-01-01', '2024-02-20', self.test_series)

        stats = self.cache.get_cache_stats()

        self.assertIn('total_files', stats)
        self.assertIn('total_size_mb', stats)
        self.assertIn('expired_files', stats)
        self.assertIn('ttl_hours', stats)

        self.assertEqual(stats['total_files'], 2)
        self.assertEqual(stats['ttl_hours'], 1)


if __name__ == '__main__':
    unittest.main()
