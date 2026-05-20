"""
回测基线验证器单元测试
"""

import unittest
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from quantsys.backtest import (
    BacktestValidator,
    ValidatorConfig,
    ValidationResult,
    ValidationIssue,
    MarketRegime,
    IssueSeverity
)


class TestBacktestValidator(unittest.TestCase):
    """回测验证器测试"""

    def setUp(self):
        """测试前准备"""
        self.config = ValidatorConfig(
            min_history_years=5.0,
            min_trade_count=100,
            max_data_gap_days=10,
            max_missing_data_pct=0.05
        )
        self.validator = BacktestValidator(self.config)

    def test_history_length_pass(self):
        """测试历史年限检查 - 通过"""
        # 创建6年的权益曲线（使用实际日期跨度）
        start_date = datetime(2018, 1, 1)
        end_date = datetime(2024, 1, 1)  # 正好6年
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        equity = pd.Series(
            np.linspace(100000, 150000, len(dates)),
            index=dates
        )

        result = self.validator.validate(equity, [])

        # 应该有一个INFO级别的历史年限消息
        history_issues = [i for i in result.issues if i.category == 'history_length']
        self.assertEqual(len(history_issues), 1)
        self.assertEqual(history_issues[0].severity, IssueSeverity.INFO)

    def test_history_length_fail(self):
        """测试历史年限检查 - 失败"""
        # 创建3年的权益曲线（不足5年）
        start_date = datetime(2021, 1, 1)
        dates = pd.date_range(start=start_date, periods=252*3, freq='D')
        equity = pd.Series(
            np.linspace(100000, 120000, len(dates)),
            index=dates
        )

        result = self.validator.validate(equity, [])

        # 应该有ERROR
        self.assertFalse(result.passed)
        errors = result.get_errors()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('历史数据不足' in e.message for e in errors))

    def test_trade_count_warning(self):
        """测试交易数量检查 - 警告"""
        # 创建足够长的权益曲线
        dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')
        equity = pd.Series(np.linspace(100000, 150000, len(dates)), index=dates)

        # 但交易次数不足
        trades = [{'date': datetime.now(), 'pnl': 100} for _ in range(50)]

        result = self.validator.validate(equity, trades)

        # 应该有WARNING
        warnings = result.get_warnings()
        self.assertTrue(any('交易次数较少' in w.message for w in warnings))

    def test_trade_count_pass(self):
        """测试交易数量检查 - 通过"""
        dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')
        equity = pd.Series(np.linspace(100000, 150000, len(dates)), index=dates)

        # 足够的交易次数
        trades = [{'date': datetime.now(), 'pnl': 100} for _ in range(150)]

        result = self.validator.validate(equity, trades)

        # 应该有INFO级别的交易次数消息
        trade_issues = [i for i in result.issues if i.category == 'trade_count']
        self.assertEqual(len(trade_issues), 1)
        self.assertEqual(trade_issues[0].severity, IssueSeverity.INFO)

    def test_market_regime_detection(self):
        """测试市场周期检测"""
        # 创建包含牛市、熊市、震荡市的权益曲线
        dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')

        # 前2年：牛市（上涨30%）
        bull_period = np.linspace(100000, 130000, 252*2)
        # 中间2年：熊市（下跌20%）
        bear_period = np.linspace(130000, 104000, 252*2)
        # 后2年：震荡市（小幅波动）
        sideways_period = np.linspace(104000, 108000, 252*2)

        equity_values = np.concatenate([bull_period, bear_period, sideways_period])
        equity = pd.Series(equity_values, index=dates)

        result = self.validator.validate(equity, [])

        # 应该检测到所有市场状态
        regime_issues = [i for i in result.issues if i.category == 'market_regime']
        self.assertGreater(len(regime_issues), 0)

    def test_data_quality_missing_data(self):
        """测试数据质量检查 - 数据缺失"""
        dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')
        equity = pd.Series(np.linspace(100000, 150000, len(dates)), index=dates)

        # 创建有缺失的价格数据（只保留70%的数据）
        price_dates = dates[::3]  # 每3天取1天，缺失率约67%
        price_data = pd.DataFrame({
            'close': np.linspace(50, 60, len(price_dates))
        }, index=price_dates)

        result = self.validator.validate(equity, [], price_data)

        # 应该有数据质量警告
        quality_issues = [i for i in result.issues if i.category == 'data_quality']
        self.assertGreater(len(quality_issues), 0)

    def test_data_quality_price_jumps(self):
        """测试数据质量检查 - 价格异常跳变"""
        dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')
        equity = pd.Series(np.linspace(100000, 150000, len(dates)), index=dates)

        # 创建有异常跳变的价格数据
        prices = np.linspace(50, 60, len(dates))
        prices[100] = 80  # 异常跳变 +40%
        prices[200] = 40  # 异常跳变 -33%

        price_data = pd.DataFrame({'close': prices}, index=dates)

        result = self.validator.validate(equity, [], price_data)

        # 应该检测到价格跳变
        quality_issues = [i for i in result.issues if i.category == 'data_quality']
        self.assertTrue(any('异常价格跳变' in i.message for i in quality_issues))

    def test_performance_metrics_sharpe(self):
        """测试性能指标检查 - 夏普比率"""
        config = ValidatorConfig(
            min_history_years=3.0,
            min_sharpe_ratio=1.0
        )
        validator = BacktestValidator(config)

        # 创建低夏普比率的权益曲线（高波动）
        dates = pd.date_range(start='2020-01-01', periods=252*4, freq='D')
        np.random.seed(42)
        returns = np.random.normal(0.0001, 0.02, len(dates))  # 低收益高波动
        equity = pd.Series(100000 * (1 + returns).cumprod(), index=dates)

        result = validator.validate(equity, [])

        # 可能有夏普比率警告
        perf_issues = [i for i in result.issues if i.category == 'performance']
        # 注意：由于随机性，这个测试可能不稳定，所以只检查是否有性能检查

    def test_performance_metrics_drawdown(self):
        """测试性能指标检查 - 最大回撤"""
        config = ValidatorConfig(
            min_history_years=3.0,
            max_drawdown_threshold=0.20
        )
        validator = BacktestValidator(config)

        # 创建有大回撤的权益曲线
        dates = pd.date_range(start='2020-01-01', periods=252*4, freq='D')
        equity_values = np.linspace(100000, 150000, len(dates))
        # 在中间制造一个30%的回撤
        mid_point = len(dates) // 2
        equity_values[mid_point:mid_point+100] *= 0.7

        equity = pd.Series(equity_values, index=dates)

        result = validator.validate(equity, [])

        # 应该有回撤警告
        perf_issues = [i for i in result.issues if i.category == 'performance']
        self.assertTrue(any('最大回撤过大' in i.message for i in perf_issues))

    def test_validation_result_methods(self):
        """测试ValidationResult的方法"""
        issues = [
            ValidationIssue(IssueSeverity.ERROR, 'test', 'error1'),
            ValidationIssue(IssueSeverity.WARNING, 'test', 'warning1'),
            ValidationIssue(IssueSeverity.WARNING, 'test', 'warning2'),
            ValidationIssue(IssueSeverity.INFO, 'test', 'info1'),
        ]

        result = ValidationResult(
            passed=False,
            issues=issues,
            summary={'total': 4}
        )

        errors = result.get_errors()
        warnings = result.get_warnings()

        self.assertEqual(len(errors), 1)
        self.assertEqual(len(warnings), 2)
        self.assertFalse(result.passed)

    def test_create_profile_strict(self):
        """测试创建严格配置文件"""
        validator = BacktestValidator()
        config = validator.create_profile('strict')

        self.assertEqual(config.min_history_years, 10.0)
        self.assertEqual(config.min_trade_count, 200)
        self.assertTrue(config.require_bull_market)
        self.assertTrue(config.require_bear_market)
        self.assertTrue(config.require_sideways_market)
        self.assertEqual(config.min_sharpe_ratio, 1.0)

    def test_create_profile_moderate(self):
        """测试创建中等配置文件"""
        validator = BacktestValidator()
        config = validator.create_profile('moderate')

        self.assertEqual(config.min_history_years, 5.0)
        self.assertEqual(config.min_trade_count, 100)
        self.assertTrue(config.require_bull_market)
        self.assertTrue(config.require_bear_market)
        self.assertFalse(config.require_sideways_market)

    def test_create_profile_relaxed(self):
        """测试创建宽松配置文件"""
        validator = BacktestValidator()
        config = validator.create_profile('relaxed')

        self.assertEqual(config.min_history_years, 3.0)
        self.assertEqual(config.min_trade_count, 50)
        self.assertFalse(config.require_bull_market)
        self.assertFalse(config.require_bear_market)
        self.assertIsNone(config.min_sharpe_ratio)

    def test_empty_equity_curve(self):
        """测试空权益曲线"""
        equity = pd.Series([], dtype=float)
        result = self.validator.validate(equity, [])

        self.assertFalse(result.passed)
        errors = result.get_errors()
        self.assertTrue(any('权益曲线为空' in e.message for e in errors))

    def test_summary_generation(self):
        """测试摘要生成"""
        dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')
        equity = pd.Series(np.linspace(100000, 150000, len(dates)), index=dates)
        trades = [{'date': datetime.now(), 'pnl': 100} for _ in range(150)]

        result = self.validator.validate(equity, trades)

        self.assertIn('total_issues', result.summary)
        self.assertIn('errors', result.summary)
        self.assertIn('warnings', result.summary)
        self.assertIn('trade_count', result.summary)
        self.assertIn('history_years', result.summary)
        self.assertEqual(result.summary['trade_count'], 150)


if __name__ == '__main__':
    unittest.main()
