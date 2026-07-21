"""
测试熔断告警服务
"""
import pytest
from unittest.mock import Mock, patch
from application.services.strategy_circuit_breaker import StrategyCircuitBreaker
from application.services.circuit_breaker_alert_service import CircuitBreakerAlertService, CircuitBreakerAlert


class TestCircuitBreakerAlertService:
    """测试熔断告警服务"""

    def test_alert_creation(self):
        """测试告警对象创建"""
        alert = CircuitBreakerAlert(
            strategy_name='test_strategy',
            old_status='active',
            new_status='warning',
            reason='连续亏损5次',
            state={'consecutive_losses': 5}
        )

        assert alert.strategy_name == 'test_strategy'
        assert alert.old_status == 'active'
        assert alert.new_status == 'warning'
        assert alert.reason == '连续亏损5次'

    def test_alert_to_dict(self):
        """测试告警转换为字典"""
        alert = CircuitBreakerAlert(
            strategy_name='test_strategy',
            old_status='active',
            new_status='suspended',
            reason='连续亏损8次',
            state={'consecutive_losses': 8, 'rolling_win_rate': 0.25}
        )

        alert_dict = alert.to_dict()

        assert alert_dict['strategy_name'] == 'test_strategy'
        assert alert_dict['old_status'] == 'active'
        assert alert_dict['new_status'] == 'suspended'
        assert alert_dict['consecutive_losses'] == 8
        assert alert_dict['rolling_win_rate'] == 0.25

    def test_send_alert_calls_handlers(self):
        """测试发送告警调用处理器"""
        service = CircuitBreakerAlertService()
        mock_handler = Mock()
        service.add_handler(mock_handler)

        service.send_alert(
            strategy_name='test_strategy',
            old_status='active',
            new_status='warning',
            reason='测试告警',
            state={'consecutive_losses': 5}
        )

        # 验证处理器被调用
        assert mock_handler.call_count == 1
        alert = mock_handler.call_args[0][0]
        assert isinstance(alert, CircuitBreakerAlert)
        assert alert.strategy_name == 'test_strategy'

    def test_send_suspended_alert(self):
        """测试发送暂停告警"""
        service = CircuitBreakerAlertService()
        mock_handler = Mock()
        service.add_handler(mock_handler)

        service.send_suspended_alert(
            strategy_name='test_strategy',
            state={'consecutive_losses': 8, 'reason': '连续亏损触发熔断'}
        )

        assert mock_handler.call_count == 1
        alert = mock_handler.call_args[0][0]
        assert alert.new_status == 'suspended'

    def test_send_warning_alert(self):
        """测试发送告警"""
        service = CircuitBreakerAlertService()
        mock_handler = Mock()
        service.add_handler(mock_handler)

        service.send_warning_alert(
            strategy_name='test_strategy',
            state={'consecutive_losses': 5, 'reason': '连续亏损5次'}
        )

        assert mock_handler.call_count == 1
        alert = mock_handler.call_args[0][0]
        assert alert.new_status == 'warning'

    def test_send_recovery_alert(self):
        """测试发送恢复告警"""
        service = CircuitBreakerAlertService()
        mock_handler = Mock()
        service.add_handler(mock_handler)

        service.send_recovery_alert(
            strategy_name='test_strategy',
            state={'consecutive_wins': 3, 'reason': '连续盈利3次'}
        )

        assert mock_handler.call_count == 1
        alert = mock_handler.call_args[0][0]
        assert alert.new_status == 'active'


class TestCircuitBreakerWithAlerts:
    """测试熔断器集成告警"""

    @pytest.fixture
    def unique_strategy_name(self):
        """生成唯一的策略名称"""
        import time
        return f'test_alert_strategy_{int(time.time() * 1000000)}'

    def test_alert_sent_on_warning_transition(self, unique_strategy_name):
        """测试 WARNING 状态转换时发送告警"""
        breaker = StrategyCircuitBreaker()
        mock_handler = Mock()

        # 添加自定义处理器
        from application.services.circuit_breaker_alert_service import circuit_breaker_alert_service
        circuit_breaker_alert_service.add_handler(mock_handler)

        # 触发 WARNING
        for _ in range(5):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        # 验证告警被发送
        assert mock_handler.call_count >= 1
        # 找到最后一次调用
        last_call = mock_handler.call_args_list[-1]
        alert = last_call[0][0]
        assert alert.new_status == 'warning'
        assert alert.strategy_name == unique_strategy_name

    def test_alert_sent_on_suspended_transition(self, unique_strategy_name):
        """测试 SUSPENDED 状态转换时发送告警"""
        breaker = StrategyCircuitBreaker()
        mock_handler = Mock()

        from application.services.circuit_breaker_alert_service import circuit_breaker_alert_service
        circuit_breaker_alert_service.add_handler(mock_handler)

        # 触发 SUSPENDED
        for _ in range(8):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        # 验证告警被发送（应该有 WARNING 和 SUSPENDED 两次）
        assert mock_handler.call_count >= 2

        # 检查最后一次是 SUSPENDED
        last_call = mock_handler.call_args_list[-1]
        alert = last_call[0][0]
        assert alert.new_status == 'suspended'

    def test_alert_sent_on_recovery(self, unique_strategy_name):
        """测试恢复时发送告警"""
        breaker = StrategyCircuitBreaker()
        mock_handler = Mock()

        from application.services.circuit_breaker_alert_service import circuit_breaker_alert_service
        circuit_breaker_alert_service.add_handler(mock_handler)

        # 先触发 SUSPENDED
        for _ in range(8):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        # 清空之前的调用记录
        mock_handler.reset_mock()

        # 恢复
        for _ in range(3):
            breaker.record_trade(unique_strategy_name, pnl_pct=0.03)

        # 验证恢复告警被发送
        assert mock_handler.call_count >= 1
        last_call = mock_handler.call_args_list[-1]
        alert = last_call[0][0]
        assert alert.new_status == 'active'
