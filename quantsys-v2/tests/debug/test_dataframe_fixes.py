#!/usr/bin/env python3
"""
DataFrame修复验证测试

测试所有修复的DataFrame boolean判断问题
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

# 添加项目路径
sys.path.insert(0, '.')

from infrastructure.utils.dataframe_utils import (
    is_dataframe_empty,
    dataframe_length,
    to_pandas,
    to_polars
)


class TestDataFrameUtils(unittest.TestCase):
    """测试DataFrame工具函数"""

    def test_is_dataframe_empty_with_none(self):
        """测试None输入"""
        self.assertTrue(is_dataframe_empty(None))

    def test_is_dataframe_empty_with_pandas_empty(self):
        """测试空的Pandas DataFrame"""
        df = pd.DataFrame()
        self.assertTrue(is_dataframe_empty(df))

    def test_is_dataframe_empty_with_pandas_nonempty(self):
        """测试非空的Pandas DataFrame"""
        df = pd.DataFrame({'a': [1, 2, 3]})
        self.assertFalse(is_dataframe_empty(df))

    def test_is_dataframe_empty_with_list_empty(self):
        """测试空列表"""
        self.assertTrue(is_dataframe_empty([]))

    def test_is_dataframe_empty_with_list_nonempty(self):
        """测试非空列表"""
        self.assertFalse(is_dataframe_empty([1, 2, 3]))

    def test_dataframe_length_with_none(self):
        """测试None的长度"""
        self.assertEqual(dataframe_length(None), 0)

    def test_dataframe_length_with_pandas(self):
        """测试Pandas DataFrame的长度"""
        df = pd.DataFrame({'a': [1, 2, 3]})
        self.assertEqual(dataframe_length(df), 3)

    def test_dataframe_length_with_list(self):
        """测试列表的长度"""
        self.assertEqual(dataframe_length([1, 2, 3]), 3)

    def test_to_pandas_with_pandas(self):
        """测试已经是Pandas的情况"""
        df = pd.DataFrame({'a': [1, 2, 3]})
        result = to_pandas(df)
        self.assertIs(result, df)

    def test_to_pandas_with_none(self):
        """测试None输入"""
        self.assertIsNone(to_pandas(None))


class TestPolarsCompatibility(unittest.TestCase):
    """测试Polars兼容性（如果Polars可用）"""

    def setUp(self):
        """设置测试"""
        try:
            import polars as pl
            self.polars_available = True
            self.pl = pl
        except ImportError:
            self.polars_available = False
            self.skipTest("Polars not available")

    def test_is_dataframe_empty_with_polars_empty(self):
        """测试空的Polars DataFrame"""
        if not self.polars_available:
            return
        df = self.pl.DataFrame()
        self.assertTrue(is_dataframe_empty(df))

    def test_is_dataframe_empty_with_polars_nonempty(self):
        """测试非空的Polars DataFrame"""
        if not self.polars_available:
            return
        df = self.pl.DataFrame({'a': [1, 2, 3]})
        self.assertFalse(is_dataframe_empty(df))

    def test_dataframe_length_with_polars(self):
        """测试Polars DataFrame的长度"""
        if not self.polars_available:
            return
        df = self.pl.DataFrame({'a': [1, 2, 3]})
        self.assertEqual(dataframe_length(df), 3)

    def test_to_pandas_from_polars(self):
        """测试从Polars转换到Pandas"""
        if not self.polars_available:
            return
        df_polars = self.pl.DataFrame({'a': [1, 2, 3]})
        df_pandas = to_pandas(df_polars)
        self.assertIsInstance(df_pandas, pd.DataFrame)
        self.assertEqual(len(df_pandas), 3)

    def test_to_polars_from_pandas(self):
        """测试从Pandas转换到Polars"""
        if not self.polars_available:
            return
        df_pandas = pd.DataFrame({'a': [1, 2, 3]})
        df_polars = to_polars(df_pandas)
        self.assertIsInstance(df_polars, self.pl.DataFrame)
        self.assertEqual(len(df_polars), 3)


class TestStrategyServiceIntegration(unittest.TestCase):
    """测试策略服务集成"""

    def test_strategy_code_service_empty_check(self):
        """测试策略代码服务的空检查"""
        from application.services.strategy_code_service import _is_empty_df_or_list, _get_length

        # 测试None
        self.assertTrue(_is_empty_df_or_list(None))
        self.assertEqual(_get_length(None), 0)

        # 测试空列表
        self.assertTrue(_is_empty_df_or_list([]))
        self.assertEqual(_get_length([]), 0)

        # 测试非空列表
        self.assertFalse(_is_empty_df_or_list([1, 2, 3]))
        self.assertEqual(_get_length([1, 2, 3]), 3)

        # 测试Pandas DataFrame
        df_empty = pd.DataFrame()
        df_nonempty = pd.DataFrame({'a': [1, 2, 3]})
        self.assertTrue(_is_empty_df_or_list(df_empty))
        self.assertFalse(_is_empty_df_or_list(df_nonempty))
        self.assertEqual(_get_length(df_nonempty), 3)


def run_api_integration_tests():
    """运行API集成测试"""
    import requests
    import json

    base_url = "http://127.0.0.1:5001"

    print("\n" + "="*60)
    print("API集成测试")
    print("="*60)

    tests = [
        {
            'name': '回测API - 正常情况',
            'endpoint': '/api/indicators/backtest',
            'data': {
                'indicatorId': '415',
                'symbol': '002714',
                'startDate': '2025-06-22',
                'endDate': '2026-06-22',
                'initialCash': 1000000,
                'period': 'daily'
            }
        },
        {
            'name': '回测API - 不同股票',
            'endpoint': '/api/indicators/backtest',
            'data': {
                'indicatorId': '415',
                'symbol': '600737',
                'startDate': '2025-06-22',
                'endDate': '2026-06-22',
                'initialCash': 1000000,
                'period': 'daily'
            }
        },
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            response = requests.post(
                f"{base_url}{test['endpoint']}",
                json=test['data'],
                timeout=30
            )
            data = response.json()

            if data.get('success'):
                print(f"✅ {test['name']}")
                if 'data' in data and 'totalReturn' in data['data']:
                    print(f"   收益率: {data['data']['totalReturn']:.2%}")
                passed += 1
            else:
                print(f"❌ {test['name']}")
                print(f"   错误: {data.get('error', 'Unknown')}")
                failed += 1
        except Exception as e:
            print(f"❌ {test['name']}")
            print(f"   异常: {str(e)}")
            failed += 1

    print("\n" + "="*60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("="*60)

    return failed == 0


if __name__ == '__main__':
    print("="*60)
    print("DataFrame修复验证测试套件")
    print("="*60)

    # 运行单元测试
    print("\n1. 运行单元测试...")
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDataFrameUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestPolarsCompatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestStrategyServiceIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 运行API集成测试
    print("\n2. 运行API集成测试...")
    api_success = run_api_integration_tests()

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"单元测试: {result.testsRun} 个, {len(result.failures)} 失败, {len(result.errors)} 错误")
    print(f"API测试: {'通过' if api_success else '失败'}")

    if result.wasSuccessful() and api_success:
        print("\n✅ 所有测试通过!")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败")
        sys.exit(1)
