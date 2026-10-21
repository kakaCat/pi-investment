"""signal_execution_daily 独立量化闭环测试（2026-10-20 重绑）

旧契约（兜底推送 Agent、不自动下单）已由用户裁定废止：
量化虚拟交易独立于「信号→推送 Agent→agent_virtual」主链路，
本任务 = 收盘后真实执行当日 pending 信号（rotation_main 账户）并回写状态。
"""
from unittest.mock import patch

from qs_ops.application.services.scheduler_tasks import handle_signal_execution_daily


@patch('qs_agenthub.application.services.agent_notification_service.agent_service')
@patch('application.services.signal_execution_scheduler.SignalExecutionScheduler')
def test_executes_pending_signals_without_agent_push(MockSched, mock_agent):
    MockSched.return_value.execute_pending_signals.return_value = {
        'success': True,
        'execution_date': '2026-10-19',
        'signals_pending': 60,
        'signals_approved': 40,
        'signals_rejected': 20,
        'orders_created': 7,
        'log_id': 1,
    }

    result = handle_signal_execution_daily()

    MockSched.return_value.execute_pending_signals.assert_called_once()
    # 不再走 Agent 推送
    mock_agent.notify_agent_detailed.assert_not_called()
    mock_agent.notify_agent.assert_not_called()
    assert result['status'] == 'success'
    assert result['signals_pending'] == 60
    assert result['orders_created'] == 7


@patch('qs_agenthub.application.services.agent_notification_service.agent_service')
@patch('application.services.signal_execution_scheduler.SignalExecutionScheduler')
def test_no_signals_still_success(MockSched, mock_agent):
    MockSched.return_value.execute_pending_signals.return_value = {
        'success': True,
        'execution_date': '2026-10-19',
        'signals_pending': 0,
        'signals_approved': 0,
        'signals_rejected': 0,
        'orders_created': 0,
        'log_id': 2,
    }

    result = handle_signal_execution_daily()

    mock_agent.notify_agent_detailed.assert_not_called()
    assert result['status'] == 'success'
    assert result['signals_pending'] == 0


@patch('application.services.signal_execution_scheduler.SignalExecutionScheduler')
def test_execution_failure_maps_to_failed(MockSched):
    MockSched.return_value.execute_pending_signals.return_value = {
        'success': False,
        'execution_date': '2026-10-19',
        'error': 'db down',
        'log_id': 3,
    }

    result = handle_signal_execution_daily()

    assert result['status'] == 'failed'
    assert result['error'] == 'db down'
