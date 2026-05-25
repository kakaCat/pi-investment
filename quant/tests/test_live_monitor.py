"""
实盘监控单元测试
"""

import unittest
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.live import LiveMonitor, MonitorConfig, DriftDetector


class TestLiveMonitor(unittest.TestCase):
    """实盘监控器测试"""

    def setUp(self):
        """测试前准备"""
        self.config = MonitorConfig(
            signal_delay_warn_seconds=5.0,
            signal_delay_critical_seconds=15.0,
            price_deviation_warn=0.003,
            price_deviation_critical=0.008
        )
        self.monitor = LiveMonitor(self.config)

    def test_signal_delay_normal(self):
        """测试正常信号延迟"""
        signal_time = datetime.now()
        execution_time = signal_time + timedelta(seconds=2)

        has_alert, severity, alert = self.monitor.check_signal_delay(
            signal_time, execution_time, 'test_strategy'
        )

        self.assertFalse(has_alert)
        self.assertIsNone(severity)
        self.assertIsNone(alert)

    def test_signal_delay_warn(self):
        """测试预警级别信号延迟"""
        signal_time = datetime.now()
        execution_time = signal_time + timedelta(seconds=8)

        has_alert, severity, alert = self.monitor.check_signal_delay(
            signal_time, execution_time, 'test_strategy'
        )

        self.assertTrue(has_alert)
        self.assertEqual(severity, 'WARN')
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, 'signal_delay')

    def test_signal_delay_critical(self):
        """测试严重信号延迟"""
        signal_time = datetime.now()
        execution_time = signal_time + timedelta(seconds=20)

        has_alert, severity, alert = self.monitor.check_signal_delay(
            signal_time, execution_time, 'test_strategy'
        )

        self.assertTrue(has_alert)
        self.assertEqual(severity, 'CRITICAL')
        self.assertIsNotNone(alert)

    def test_price_deviation_normal(self):
        """测试正常价格偏差"""
        has_alert, severity, alert = self.monitor.check_price_deviation(
            expected_price=50.0,
            actual_price=50.05,  # 0.1%偏差
            symbol='600036.SH',
            strategy_id='test_strategy'
        )

        self.assertFalse(has_alert)

    def test_price_deviation_warn(self):
        """测试预警级别价格偏差"""
        has_alert, severity, alert = self.monitor.check_price_deviation(
            expected_price=50.0,
            actual_price=50.25,  # 0.5%偏差
            symbol='600036.SH',
            strategy_id='test_strategy'
        )

        self.assertTrue(has_alert)
        self.assertEqual(severity, 'WARN')
        self.assertEqual(alert.alert_type, 'price_deviation')

    def test_price_deviation_critical(self):
        """测试严重价格偏差"""
        has_alert, severity, alert = self.monitor.check_price_deviation(
            expected_price=50.0,
            actual_price=50.50,  # 1.0%偏差
            symbol='600036.SH',
            strategy_id='test_strategy'
        )

        self.assertTrue(has_alert)
        self.assertEqual(severity, 'CRITICAL')

    def test_strategy_drift_normal(self):
        """测试正常策略表现"""
        baseline = {
            'win_rate': 0.65,
            'profit_loss_ratio': 2.0,
            'max_drawdown': 0.10
        }
        self.monitor.update_strategy_baseline('test_strategy', baseline)

        recent = {
            'win_rate': 0.63,
            'profit_loss_ratio': 1.9,
            'max_drawdown': 0.11
        }

        has_alert, severity, alert = self.monitor.check_strategy_drift(
            'test_strategy', recent
        )

        self.assertFalse(has_alert)

    def test_strategy_drift_detected(self):
        """测试检测到策略漂移"""
        baseline = {
            'win_rate': 0.65,
            'profit_loss_ratio': 2.0,
            'max_drawdown': 0.10
        }
        self.monitor.update_strategy_baseline('test_strategy', baseline)

        recent = {
            'win_rate': 0.50,  # 下降15%
            'profit_loss_ratio': 1.5,
            'max_drawdown': 0.15
        }

        has_alert, severity, alert = self.monitor.check_strategy_drift(
            'test_strategy', recent
        )

        self.assertTrue(has_alert)
        self.assertEqual(severity, 'WARN')

    def test_pause_and_resume_strategy(self):
        """测试暂停和恢复策略"""
        strategy_id = 'test_strategy'

        # 暂停策略
        self.monitor.pause_strategy(strategy_id, 'test reason')
        self.assertTrue(self.monitor.is_strategy_paused(strategy_id))

        # 恢复策略
        self.monitor.resume_strategy(strategy_id)
        self.assertFalse(self.monitor.is_strategy_paused(strategy_id))

    def test_get_alerts(self):
        """测试查询告警"""
        # 触发几个告警
        signal_time = datetime.now()
        execution_time = signal_time + timedelta(seconds=8)
        self.monitor.check_signal_delay(signal_time, execution_time, 'strategy1')
        self.monitor.check_signal_delay(signal_time, execution_time, 'strategy2')

        # 查询所有告警
        all_alerts = self.monitor.get_alerts()
        self.assertEqual(len(all_alerts), 2)

        # 按策略过滤
        strategy1_alerts = self.monitor.get_alerts(strategy_id='strategy1')
        self.assertEqual(len(strategy1_alerts), 1)

        # 按类型过滤
        delay_alerts = self.monitor.get_alerts(alert_type='signal_delay')
        self.assertEqual(len(delay_alerts), 2)

    def test_statistics(self):
        """测试统计功能"""
        # 触发一些告警
        signal_time = datetime.now()
        execution_time = signal_time + timedelta(seconds=8)
        self.monitor.check_signal_delay(signal_time, execution_time, 'test_strategy')

        self.monitor.check_price_deviation(50.0, 50.25, '600036.SH', 'test_strategy')

        stats = self.monitor.get_statistics()

        self.assertGreater(stats['total_alerts'], 0)
        self.assertIn('signal_delay', stats['alerts_by_type'])
        self.assertIn('price_deviation', stats['alerts_by_type'])


class TestDriftDetector(unittest.TestCase):
    """策略漂移检测器测试"""

    def setUp(self):
        """测试前准备"""
        self.detector = DriftDetector(
            rolling_days=20,
            baseline_days=60,
            win_rate_threshold=0.08
        )

    def test_record_trade(self):
        """测试记录交易"""
        trade = {
            'date': datetime.now(),
            'pnl': 1000,
            'return_pct': 0.02
        }

        self.detector.record_trade('test_strategy', trade)
        self.assertIn('test_strategy', self.detector.trades)
        self.assertEqual(len(self.detector.trades['test_strategy']), 1)

    def test_detect_drift_insufficient_data(self):
        """测试数据不足时的漂移检测"""
        has_drift, metrics = self.detector.detect_drift('test_strategy')
        self.assertFalse(has_drift)
        self.assertIsNone(metrics)

    def test_detect_drift_with_data(self):
        """测试有数据时的漂移检测"""
        # 添加历史交易（基线）
        base_date = datetime.now() - timedelta(days=80)
        for i in range(30):
            trade = {
                'date': base_date + timedelta(days=i),
                'pnl': 1000 if i % 3 != 0 else -500,
                'return_pct': 0.02 if i % 3 != 0 else -0.01
            }
            self.detector.record_trade('test_strategy', trade)

        # 添加最近交易（表现下降）
        recent_date = datetime.now() - timedelta(days=20)
        for i in range(20):
            trade = {
                'date': recent_date + timedelta(days=i),
                'pnl': 800 if i % 2 == 0 else -600,
                'return_pct': 0.015 if i % 2 == 0 else -0.012
            }
            self.detector.record_trade('test_strategy', trade)

        # 检测漂移
        has_drift, metrics = self.detector.detect_drift('test_strategy')

        self.assertIsNotNone(metrics)
        self.assertIn('win_rate', metrics.baseline)
        self.assertIn('win_rate', metrics.current)

    def test_reset_baseline(self):
        """测试重置基线"""
        self.detector.baselines['test_strategy'] = {'win_rate': 0.6}
        self.assertIn('test_strategy', self.detector.baselines)

        self.detector.reset_baseline('test_strategy')
        self.assertNotIn('test_strategy', self.detector.baselines)


if __name__ == '__main__':
    unittest.main()
