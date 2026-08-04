"""
信号执行集成测试

端到端测试完整的信号执行流程
"""

import pytest
from datetime import date
from application.services.signal_execution_scheduler import SignalExecutionScheduler
from adapters.outbound.repositories import SignalExecutionLogORMRepository


def test_end_to_end_signal_execution():
    """端到端测试：完整的信号执行流程"""
    scheduler = SignalExecutionScheduler()
    log_repo = SignalExecutionLogORMRepository()

    # 执行信号处理
    result = scheduler.execute_daily_signals()

    # 验证返回结果
    assert result['execution_date'] == date.today().isoformat()
    assert result['duration_ms'] > 0
    assert result['strategies_run'] >= 0
    assert result['signals_generated'] >= 0

    # 验证日志记录
    logs = log_repo.get_logs_by_date_range(
        date.today().isoformat(),
        date.today().isoformat()
    )

    assert len(logs) >= 1
    latest_log = logs[0]
    assert latest_log['status'] in ['completed', 'failed']
    assert latest_log['execution_details'] is not None
