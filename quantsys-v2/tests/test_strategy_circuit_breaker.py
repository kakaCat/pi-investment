"""
测试策略熔断器
"""
import pytest
from datetime import datetime, timedelta
from application.services.strategy_circuit_breaker import StrategyCircuitBreaker, CircuitBreakerState


@pytest.fixture
def unique_strategy_name():
    """生成唯一的策略名称"""
    import time
    return f'test_strategy_{int(time.time() * 1000000)}'


class TestStrategyCircuitBreaker:
    """测试策略熔断器"""

    def test_initial_state_is_active(self, unique_strategy_name):
        """测试初始状态为 ACTIVE"""
        breaker = StrategyCircuitBreaker()
        state = breaker.get_state(unique_strategy_name)

        assert state['status'] == CircuitBreakerState.ACTIVE
        assert state['consecutive_losses'] == 0
        assert state['rolling_win_rate'] is None

    def test_record_loss_increments_counter(self, unique_strategy_name):
        """测试记录亏损增加计数器"""
        breaker = StrategyCircuitBreaker()

        breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)
        state = breaker.get_state(unique_strategy_name)

        assert state['consecutive_losses'] == 1

    def test_record_profit_resets_loss_counter(self, unique_strategy_name):
        """测试记录盈利重置亏损计数器"""
        breaker = StrategyCircuitBreaker()

        breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)
        breaker.record_trade(unique_strategy_name, pnl_pct=-0.01)
        breaker.record_trade(unique_strategy_name, pnl_pct=0.03)

        state = breaker.get_state(unique_strategy_name)
        assert state['consecutive_losses'] == 0

    def test_five_consecutive_losses_triggers_warning(self, unique_strategy_name):
        """测试连续 5 次亏损触发 WARNING"""
        breaker = StrategyCircuitBreaker()

        for _ in range(5):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        state = breaker.get_state(unique_strategy_name)
        assert state['status'] == CircuitBreakerState.WARNING
        assert state['consecutive_losses'] == 5

    def test_eight_consecutive_losses_triggers_suspended(self, unique_strategy_name):
        """测试连续 8 次亏损触发 SUSPENDED"""
        breaker = StrategyCircuitBreaker()

        for _ in range(8):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        state = breaker.get_state(unique_strategy_name)
        assert state['status'] == CircuitBreakerState.SUSPENDED
        assert state['consecutive_losses'] == 8

    def test_low_win_rate_triggers_warning(self, unique_strategy_name):
        """测试低胜率触发 WARNING"""
        breaker = StrategyCircuitBreaker()

        # 20 笔交易，胜率 25%（低于 30% 阈值）
        # 交替盈亏，避免连续亏损触发 SUSPENDED
        trades = [0.02, -0.01, -0.01, -0.01, 0.02, -0.01, -0.01, -0.01,
                  0.02, -0.01, -0.01, -0.01, 0.02, -0.01, -0.01, -0.01,
                  0.02, -0.01, -0.01, -0.01]

        for pnl in trades:
            breaker.record_trade(unique_strategy_name, pnl_pct=pnl)

        state = breaker.get_state(unique_strategy_name)
        assert state['status'] == CircuitBreakerState.WARNING
        assert state['rolling_win_rate'] == 0.25

    def test_recovery_from_suspended_requires_three_wins(self, unique_strategy_name):
        """测试从 SUSPENDED 恢复需要连续 3 次盈利"""
        breaker = StrategyCircuitBreaker()

        # 触发 SUSPENDED
        for _ in range(8):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        assert breaker.get_state(unique_strategy_name)['status'] == CircuitBreakerState.SUSPENDED

        # 连续 2 次盈利，仍然 SUSPENDED
        breaker.record_trade(unique_strategy_name, pnl_pct=0.03)
        breaker.record_trade(unique_strategy_name, pnl_pct=0.02)
        assert breaker.get_state(unique_strategy_name)['status'] == CircuitBreakerState.SUSPENDED

        # 第 3 次盈利，恢复到 ACTIVE
        breaker.record_trade(unique_strategy_name, pnl_pct=0.04)
        assert breaker.get_state(unique_strategy_name)['status'] == CircuitBreakerState.ACTIVE

    def test_is_allowed_returns_true_for_active(self, unique_strategy_name):
        """测试 ACTIVE 状态允许实盘交易"""
        breaker = StrategyCircuitBreaker()

        assert breaker.is_allowed(unique_strategy_name) is True

    def test_is_allowed_returns_true_for_warning(self, unique_strategy_name):
        """测试 WARNING 状态允许实盘交易（但有告警）"""
        breaker = StrategyCircuitBreaker()

        for _ in range(5):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        assert breaker.is_allowed(unique_strategy_name) is True

    def test_is_allowed_returns_false_for_suspended(self, unique_strategy_name):
        """测试 SUSPENDED 状态禁止实盘交易"""
        breaker = StrategyCircuitBreaker()

        for _ in range(8):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        assert breaker.is_allowed(unique_strategy_name) is False

    def test_get_recommendation_for_suspended(self, unique_strategy_name):
        """测试 SUSPENDED 状态返回 avoid 建议"""
        breaker = StrategyCircuitBreaker()

        for _ in range(8):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        recommendation = breaker.get_recommendation(unique_strategy_name)
        assert recommendation == 'avoid'

    def test_get_recommendation_for_warning(self, unique_strategy_name):
        """测试 WARNING 状态返回 cautious 建议"""
        breaker = StrategyCircuitBreaker()

        for _ in range(5):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        recommendation = breaker.get_recommendation(unique_strategy_name)
        assert recommendation == 'cautious'

    def test_get_recommendation_for_active(self, unique_strategy_name):
        """测试 ACTIVE 状态返回 normal 建议"""
        breaker = StrategyCircuitBreaker()

        recommendation = breaker.get_recommendation(unique_strategy_name)
        assert recommendation == 'normal'

    def test_manual_suspend(self, unique_strategy_name):
        """测试手动暂停策略"""
        breaker = StrategyCircuitBreaker()

        breaker.manual_suspend(unique_strategy_name, reason='手动暂停测试')

        state = breaker.get_state(unique_strategy_name)
        assert state['status'] == CircuitBreakerState.SUSPENDED
        assert '手动暂停' in state['reason']

    def test_manual_resume(self, unique_strategy_name):
        """测试手动恢复策略"""
        breaker = StrategyCircuitBreaker()

        # 先暂停
        for _ in range(8):
            breaker.record_trade(unique_strategy_name, pnl_pct=-0.02)

        # 手动恢复
        breaker.manual_resume(unique_strategy_name)

        state = breaker.get_state(unique_strategy_name)
        assert state['status'] == CircuitBreakerState.ACTIVE
        assert state['consecutive_losses'] == 0

    def test_state_persists_across_instances(self, unique_strategy_name):
        """测试状态在实例间持久化"""
        breaker1 = StrategyCircuitBreaker()

        for _ in range(5):
            breaker1.record_trade(unique_strategy_name, pnl_pct=-0.02)

        # 创建新实例，应该能读取到之前的状态
        breaker2 = StrategyCircuitBreaker()
        state = breaker2.get_state(unique_strategy_name)

        assert state['status'] == CircuitBreakerState.WARNING
        assert state['consecutive_losses'] == 5
