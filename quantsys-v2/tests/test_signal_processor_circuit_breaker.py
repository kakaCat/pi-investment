"""
测试信号处理器的熔断集成
"""
import pytest
from unittest.mock import Mock, MagicMock
from application.services.signal_processor import SignalProcessor, SignalProcessingError
from application.services.strategy_circuit_breaker import StrategyCircuitBreaker


class TestSignalProcessorCircuitBreaker:
    """测试信号处理器的熔断集成"""

    @pytest.fixture
    def mock_data_service(self):
        """模拟数据服务"""
        ds = Mock()
        ds.get_latest_price = Mock(return_value=100.0)
        return ds

    @pytest.fixture
    def signal_processor(self, mock_data_service):
        """创建信号处理器"""
        return SignalProcessor(mock_data_service)

    @pytest.fixture
    def valid_signal(self):
        """有效的信号"""
        import time
        unique_name = f'test_strategy_circuit_{int(time.time() * 1000000)}'
        return {
            'strategy_name': unique_name,
            'action': 'BUY',
            'confidence': 0.8,
            'reason': '测试信号',
            'risk_management': {
                'stop_loss': {'type': 'percent', 'value': 0.05},
                'position_sizing': {'type': 'percent', 'value': 0.1, 'method': 'fixed_percent'}
            }
        }

    @pytest.fixture
    def account_balance(self):
        """账户余额"""
        return {
            'cash': 100000,
            'total_value': 150000
        }

    def test_allows_signal_when_strategy_is_active(
        self, signal_processor, valid_signal, account_balance
    ):
        """测试策略 ACTIVE 时允许信号处理"""
        # 确保策略是 ACTIVE 状态
        breaker = signal_processor.circuit_breaker
        state = breaker.get_state(valid_signal['strategy_name'])
        assert state['status'] == 'active'

        # 处理信号应该成功
        result = signal_processor.process_signal(
            signal=valid_signal,
            symbol='000001.SH',
            current_price=100.0,
            account_balance=account_balance
        )

        assert result['action'] == 'BUY'
        assert result['quantity'] > 0

    def test_blocks_signal_when_strategy_is_suspended(
        self, signal_processor, valid_signal, account_balance
    ):
        """测试策略 SUSPENDED 时阻止信号处理"""
        # 触发熔断
        breaker = signal_processor.circuit_breaker
        for _ in range(8):
            breaker.record_trade(valid_signal['strategy_name'], pnl_pct=-0.02)

        # 验证策略已被暂停
        assert not breaker.is_allowed(valid_signal['strategy_name'])

        # 处理信号应该失败
        with pytest.raises(SignalProcessingError) as exc_info:
            signal_processor.process_signal(
                signal=valid_signal,
                symbol='000001.SH',
                current_price=100.0,
                account_balance=account_balance
            )

        assert '熔断暂停' in str(exc_info.value)
        assert valid_signal['strategy_name'] in str(exc_info.value)

    def test_allows_signal_when_strategy_is_warning(
        self, signal_processor, valid_signal, account_balance
    ):
        """测试策略 WARNING 时仍允许信号处理（但有告警）"""
        # 触发 WARNING 状态（交替盈亏，避免连续亏损触发 SUSPENDED）
        breaker = signal_processor.circuit_breaker
        trades = [0.02, -0.01, -0.01, -0.01, 0.02, -0.01, -0.01, -0.01,
                  0.02, -0.01, -0.01, -0.01, 0.02, -0.01, -0.01, -0.01,
                  0.02, -0.01, -0.01, -0.01]  # 胜率 25%

        for pnl in trades:
            breaker.record_trade(valid_signal['strategy_name'], pnl_pct=pnl)

        # 验证策略是 WARNING 状态
        state = breaker.get_state(valid_signal['strategy_name'])
        assert state['status'] == 'warning'
        assert breaker.is_allowed(valid_signal['strategy_name'])

        # 处理信号应该成功
        result = signal_processor.process_signal(
            signal=valid_signal,
            symbol='000001.SH',
            current_price=100.0,
            account_balance=account_balance
        )

        assert result['action'] == 'BUY'
        assert result['quantity'] > 0

    def test_manual_suspend_blocks_signals(
        self, signal_processor, valid_signal, account_balance
    ):
        """测试手动暂停策略后阻止信号"""
        # 手动暂停策略
        breaker = signal_processor.circuit_breaker
        breaker.manual_suspend(
            valid_signal['strategy_name'],
            reason='手动暂停测试'
        )

        # 处理信号应该失败
        with pytest.raises(SignalProcessingError) as exc_info:
            signal_processor.process_signal(
                signal=valid_signal,
                symbol='000001.SH',
                current_price=100.0,
                account_balance=account_balance
            )

        assert '熔断暂停' in str(exc_info.value)

    def test_manual_resume_allows_signals(
        self, signal_processor, valid_signal, account_balance
    ):
        """测试手动恢复策略后允许信号"""
        breaker = signal_processor.circuit_breaker

        # 先触发熔断
        for _ in range(8):
            breaker.record_trade(valid_signal['strategy_name'], pnl_pct=-0.02)

        # 手动恢复
        breaker.manual_resume(valid_signal['strategy_name'])

        # 处理信号应该成功
        result = signal_processor.process_signal(
            signal=valid_signal,
            symbol='000001.SH',
            current_price=100.0,
            account_balance=account_balance
        )

        assert result['action'] == 'BUY'
        assert result['quantity'] > 0
