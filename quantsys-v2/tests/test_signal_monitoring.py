"""
测试 SignalMonitor 服务
"""
import pytest
from application.services.signal_monitoring import SignalMonitor


class TestSignalMonitor:

    @pytest.fixture
    def monitor(self):
        """创建 SignalMonitor 实例"""
        return SignalMonitor()

    def test_record_signal_processing_success(self, monitor):
        """测试记录成功的信号处理"""
        monitor.record_signal_processing(
            strategy_name='TestStrategy',
            symbol='000001.SH',
            success=True,
            duration=0.025,
            warnings=['test warning']
        )

        metrics = monitor.get_metrics('TestStrategy')
        assert len(metrics) == 1

        key = 'TestStrategy:000001.SH'
        assert metrics[key]['count'] == 1
        assert metrics[key]['success'] == 1
        assert metrics[key]['failure'] == 0
        assert metrics[key]['warnings'] == 1
        assert metrics[key]['total_time'] == 0.025

    def test_record_signal_processing_failure(self, monitor):
        """测试记录失败的信号处理"""
        monitor.record_signal_processing(
            strategy_name='TestStrategy',
            symbol='000001.SH',
            success=False,
            duration=0.015,
            error='Test error'
        )

        metrics = monitor.get_metrics('TestStrategy')
        key = 'TestStrategy:000001.SH'

        assert metrics[key]['failure'] == 1
        assert len(metrics[key]['errors']) == 1
        assert metrics[key]['errors'][0]['error'] == 'Test error'

    def test_get_summary(self, monitor):
        """测试获取汇总统计"""
        # 记录多个信号
        monitor.record_signal_processing('S1', 'A', True, 0.01)
        monitor.record_signal_processing('S1', 'B', True, 0.02)
        monitor.record_signal_processing('S2', 'A', False, 0.03, error='err')

        summary = monitor.get_summary()

        assert summary['total_signals'] == 3
        assert summary['success_rate'] == pytest.approx(2/3)
        assert summary['failure_count'] == 1
        assert summary['avg_processing_time'] == pytest.approx(0.02)
        assert summary['strategies_monitored'] == 3  # S1:A, S1:B, S2:A

    def test_get_all_metrics(self, monitor):
        """测试获取所有指标"""
        monitor.record_signal_processing('S1', 'A', True, 0.01)
        monitor.record_signal_processing('S2', 'B', True, 0.02)

        all_metrics = monitor.get_metrics()  # No strategy_name
        assert len(all_metrics) == 2
        assert 'S1:A' in all_metrics
        assert 'S2:B' in all_metrics
