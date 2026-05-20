"""
风险事件记录器单元测试
"""

import unittest
from datetime import datetime, timedelta
import sys
from pathlib import Path
import tempfile
import shutil
sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.risk import (
    RiskEventLogger,
    RejectionEvent,
    CircuitBreakEvent,
    WarningEvent,
    ViolationEvent
)


class MockOrder:
    """模拟订单对象"""
    def __init__(self):
        self.symbol = '600036.SH'
        self.action = 'buy'
        self.price = 50.0
        self.shares = 1000


class TestRiskEventLogger(unittest.TestCase):
    """风险事件记录器测试"""

    def setUp(self):
        """测试前准备"""
        # 使用临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.logger = RiskEventLogger(log_dir=self.temp_dir, persist=False)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_rejection(self):
        """测试记录风控拒绝"""
        order = MockOrder()

        self.logger.record_rejection(
            strategy_id='ma_cross',
            rule_id='R1',
            reason='单股仓位超限',
            order=order
        )

        self.assertEqual(self.logger.rejection_count, 1)
        self.assertEqual(len(self.logger.events), 1)

        event = self.logger.events[0]
        self.assertIsInstance(event, RejectionEvent)
        self.assertEqual(event.strategy_id, 'ma_cross')
        self.assertEqual(event.rule_id, 'R1')
        self.assertEqual(event.order_symbol, '600036.SH')

    def test_record_circuit_break(self):
        """测试记录熔断事件"""
        self.logger.record_circuit_break(
            strategy_id='ma_cross',
            reason='连续亏损3次',
            trigger_type='consecutive_loss',
            trigger_value=3,
            threshold=3
        )

        self.assertEqual(self.logger.circuit_break_count, 1)
        self.assertEqual(len(self.logger.events), 1)

        event = self.logger.events[0]
        self.assertIsInstance(event, CircuitBreakEvent)
        self.assertEqual(event.trigger_type, 'consecutive_loss')
        self.assertEqual(event.trigger_value, 3)

    def test_record_warning(self):
        """测试记录预警事件"""
        self.logger.record_warning(
            strategy_id='rsi_reversal',
            reason='单日亏损接近限制',
            warning_type='daily_loss',
            current_value=0.04,
            threshold=0.05
        )

        self.assertEqual(self.logger.warning_count, 1)
        self.assertEqual(len(self.logger.events), 1)

        event = self.logger.events[0]
        self.assertIsInstance(event, WarningEvent)
        self.assertEqual(event.warning_type, 'daily_loss')

    def test_record_violation(self):
        """测试记录违规事件"""
        self.logger.record_violation(
            strategy_id='test_strategy',
            reason='超出最大持仓数量',
            violation_type='position_limit',
            violation_details='持仓5只，限制3只'
        )

        self.assertEqual(self.logger.violation_count, 1)
        self.assertEqual(len(self.logger.events), 1)

        event = self.logger.events[0]
        self.assertIsInstance(event, ViolationEvent)
        self.assertEqual(event.violation_type, 'position_limit')

    def test_get_events_filter_by_type(self):
        """测试按类型过滤事件"""
        # 记录不同类型的事件
        self.logger.record_rejection('s1', 'R1', 'test', MockOrder())
        self.logger.record_circuit_break('s1', 'test', 'daily_loss', 0.06, 0.05)
        self.logger.record_warning('s1', 'test', 'warning', 0.04, 0.05)

        # 过滤拒绝事件
        rejections = self.logger.get_events(event_type='rejection')
        self.assertEqual(len(rejections), 1)
        self.assertIsInstance(rejections[0], RejectionEvent)

        # 过滤熔断事件
        circuit_breaks = self.logger.get_events(event_type='circuit_break')
        self.assertEqual(len(circuit_breaks), 1)
        self.assertIsInstance(circuit_breaks[0], CircuitBreakEvent)

    def test_get_events_filter_by_strategy(self):
        """测试按策略过滤事件"""
        self.logger.record_rejection('strategy_a', 'R1', 'test', MockOrder())
        self.logger.record_rejection('strategy_b', 'R1', 'test', MockOrder())
        self.logger.record_rejection('strategy_a', 'R2', 'test', MockOrder())

        # 过滤 strategy_a 的事件
        events = self.logger.get_events(strategy_id='strategy_a')
        self.assertEqual(len(events), 2)

        # 过滤 strategy_b 的事件
        events = self.logger.get_events(strategy_id='strategy_b')
        self.assertEqual(len(events), 1)

    def test_get_events_filter_by_date(self):
        """测试按日期过滤事件"""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        # 记录不同时间的事件
        self.logger.record_rejection('s1', 'R1', 'test', MockOrder(), timestamp=yesterday)
        self.logger.record_rejection('s1', 'R1', 'test', MockOrder(), timestamp=now)
        self.logger.record_rejection('s1', 'R1', 'test', MockOrder(), timestamp=tomorrow)

        # 过滤今天及以后的事件
        events = self.logger.get_events(start_date=now)
        self.assertEqual(len(events), 2)

        # 过滤今天及以前的事件
        events = self.logger.get_events(end_date=now)
        self.assertEqual(len(events), 2)

    def test_get_rejections(self):
        """测试获取拒绝记录"""
        order = MockOrder()

        # 记录多个拒绝
        for i in range(5):
            self.logger.record_rejection(f'strategy_{i}', 'R1', 'test', order)

        # 获取所有拒绝
        rejections = self.logger.get_rejections()
        self.assertEqual(len(rejections), 5)

        # 获取特定策略的拒绝
        rejections = self.logger.get_rejections(strategy_id='strategy_0')
        self.assertEqual(len(rejections), 1)

    def test_get_strategy_summary(self):
        """测试获取策略摘要"""
        order = MockOrder()

        # 记录多种事件
        self.logger.record_rejection('test_strategy', 'R1', 'test', order)
        self.logger.record_rejection('test_strategy', 'R2', 'test', order)
        self.logger.record_circuit_break('test_strategy', 'test', 'daily_loss', 0.06, 0.05)
        self.logger.record_warning('test_strategy', 'test', 'warning', 0.04, 0.05)
        self.logger.record_violation('test_strategy', 'test', 'violation', 'details')

        summary = self.logger.get_strategy_summary('test_strategy')

        self.assertEqual(summary['total_rejections'], 2)
        self.assertEqual(summary['total_circuit_breaks'], 1)
        self.assertEqual(summary['total_warnings'], 1)
        self.assertEqual(summary['total_violations'], 1)

    def test_get_rule_statistics(self):
        """测试获取规则统计"""
        order = MockOrder()

        # 记录不同规则的拒绝
        self.logger.record_rejection('s1', 'R1', 'test', order)
        self.logger.record_rejection('s1', 'R1', 'test', order)
        self.logger.record_rejection('s1', 'R2', 'test', order)
        self.logger.record_rejection('s1', 'R3', 'test', order)
        self.logger.record_rejection('s1', 'R3', 'test', order)
        self.logger.record_rejection('s1', 'R3', 'test', order)

        rule_stats = self.logger.get_rule_statistics()

        self.assertEqual(rule_stats['R1'], 2)
        self.assertEqual(rule_stats['R2'], 1)
        self.assertEqual(rule_stats['R3'], 3)

    def test_get_overall_statistics(self):
        """测试获取总体统计"""
        order = MockOrder()

        # 记录各种事件
        self.logger.record_rejection('s1', 'R1', 'test', order)
        self.logger.record_rejection('s2', 'R1', 'test', order)
        self.logger.record_circuit_break('s1', 'test', 'daily_loss', 0.06, 0.05)
        self.logger.record_warning('s1', 'test', 'warning', 0.04, 0.05)

        stats = self.logger.get_overall_statistics()

        self.assertEqual(stats['total_events'], 4)
        self.assertEqual(stats['total_rejections'], 2)
        self.assertEqual(stats['total_circuit_breaks'], 1)
        self.assertEqual(stats['total_warnings'], 1)
        self.assertEqual(stats['strategies_monitored'], 2)

    def test_strategy_stats_tracking(self):
        """测试策略统计追踪"""
        order = MockOrder()

        # 记录策略A的事件
        self.logger.record_rejection('strategy_a', 'R1', 'test', order)
        self.logger.record_rejection('strategy_a', 'R1', 'test', order)

        # 记录策略B的事件
        self.logger.record_rejection('strategy_b', 'R1', 'test', order)

        self.assertEqual(self.logger.strategy_stats['strategy_a']['rejections'], 2)
        self.assertEqual(self.logger.strategy_stats['strategy_b']['rejections'], 1)

    def test_clear_old_events(self):
        """测试清理旧事件"""
        now = datetime.now()
        old_date = now - timedelta(days=100)

        # 记录旧事件
        self.logger.record_rejection('s1', 'R1', 'test', MockOrder(), timestamp=old_date)
        # 记录新事件
        self.logger.record_rejection('s1', 'R1', 'test', MockOrder(), timestamp=now)

        self.assertEqual(len(self.logger.events), 2)

        # 清理90天前的事件
        self.logger.clear_old_events(days=90)

        self.assertEqual(len(self.logger.events), 1)
        self.assertEqual(self.logger.events[0].timestamp.date(), now.date())

    def test_reset(self):
        """测试重置"""
        order = MockOrder()

        # 记录一些事件
        self.logger.record_rejection('s1', 'R1', 'test', order)
        self.logger.record_circuit_break('s1', 'test', 'daily_loss', 0.06, 0.05)

        self.assertGreater(len(self.logger.events), 0)
        self.assertGreater(self.logger.rejection_count, 0)

        # 重置
        self.logger.reset()

        self.assertEqual(len(self.logger.events), 0)
        self.assertEqual(self.logger.rejection_count, 0)
        self.assertEqual(self.logger.circuit_break_count, 0)
        self.assertEqual(len(self.logger.strategy_stats), 0)

    def test_event_severity(self):
        """测试事件严重程度"""
        order = MockOrder()

        self.logger.record_rejection('s1', 'R1', 'test', order)
        self.logger.record_circuit_break('s1', 'test', 'daily_loss', 0.06, 0.05)
        self.logger.record_warning('s1', 'test', 'warning', 0.04, 0.05)

        # 检查严重程度
        rejection = self.logger.events[0]
        circuit_break = self.logger.events[1]
        warning = self.logger.events[2]

        self.assertEqual(rejection.severity, 'WARN')
        self.assertEqual(circuit_break.severity, 'CRITICAL')
        self.assertEqual(warning.severity, 'WARN')

    def test_persist_to_file(self):
        """测试持久化到文件"""
        # 创建启用持久化的记录器
        logger = RiskEventLogger(log_dir=self.temp_dir, persist=True)

        # 记录事件
        logger.record_rejection('s1', 'R1', 'test', MockOrder())

        # 检查文件是否创建
        date_str = datetime.now().strftime('%Y-%m-%d')
        log_file = Path(self.temp_dir) / f'risk_events_{date_str}.jsonl'

        self.assertTrue(log_file.exists())

        # 读取文件内容
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('rejection', content)
            self.assertIn('R1', content)


if __name__ == '__main__':
    unittest.main()
