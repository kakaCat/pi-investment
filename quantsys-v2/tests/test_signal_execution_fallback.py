"""signal_execution_daily 兜底推送改造测试"""
from unittest.mock import patch

from application.services.task_handlers import handle_signal_execution_daily


@patch('application.services.agent_notification_service.agent_service')
@patch('application.services.signal_execution_scheduler.SignalExecutionScheduler')
def test_repushes_signals_without_executing(MockSched, mock_agent):
    MockSched.return_value._collect_signals.return_value = [
        {'id': 1, 'symbol': '600519.SH', 'signal_type': '买入', 'strength': 85},
    ]
    mock_agent.notify_agent_detailed.return_value = 'ok'

    result = handle_signal_execution_daily()

    MockSched.return_value.execute_daily_signals.assert_not_called()
    mock_agent.notify_agent_detailed.assert_called_once()
    event, data = mock_agent.notify_agent_detailed.call_args[0]
    assert event == 'signals_ready'
    assert data['account'] == 'agent_virtual'
    assert data['source'] == 'signal_execution_daily_fallback'
    assert result['signals_pending'] == 1
    assert result['pushed'] is True


@patch('application.services.agent_notification_service.agent_service')
@patch('application.services.signal_execution_scheduler.SignalExecutionScheduler')
def test_no_signals_no_push(MockSched, mock_agent):
    MockSched.return_value._collect_signals.return_value = []

    result = handle_signal_execution_daily()

    mock_agent.notify_agent_detailed.assert_not_called()
    assert result['signals_pending'] == 0
    assert result['pushed'] is False
