"""动态池每日刷新任务测试"""
from datetime import date
from unittest.mock import patch, MagicMock

from application.services.scheduler_tasks import (
    handle_pool_refresh_daily,
    _is_pool_refresh_due,
)


def _pool(pid, ptype='dynamic', interval='daily', last=None):
    return {
        'id': pid, 'name': f'pool{pid}', 'pool_type': ptype,
        'refresh_interval': interval, 'last_refreshed_at': last,
    }


def _make_service(pools, before_after):
    """before_after: [(before_symbols, after_symbols), ...] 按刷新顺序"""
    svc = MagicMock()
    svc.list_pools.return_value = pools
    gets = []
    for before, after in before_after:
        gets.append({'symbols': before})
        gets.append({'symbols': after})
    svc.get_pool.side_effect = gets
    return svc


def test_is_refresh_due_daily_always():
    assert _is_pool_refresh_due(_pool(1, interval='daily'), date(2026, 7, 24)) is True
    assert _is_pool_refresh_due(_pool(1, interval=None), date(2026, 7, 24)) is True


def test_is_refresh_due_weekly():
    assert _is_pool_refresh_due(
        _pool(1, interval='weekly', last='2026-07-20'), date(2026, 7, 24)) is False
    assert _is_pool_refresh_due(
        _pool(1, interval='weekly', last='2026-07-16'), date(2026, 7, 24)) is True
    # 从未刷新过的 weekly 池：该刷
    assert _is_pool_refresh_due(
        _pool(1, interval='weekly', last=None), date(2026, 7, 24)) is True


@patch('application.services.agent_notification_service.agent_service')
def test_refresh_due_dynamic_pools_and_notify(mock_agent):
    svc = _make_service(
        pools=[_pool(1), _pool(2, ptype='static')],
        before_after=[(['A', 'B'], ['B', 'C'])],
    )

    result = handle_pool_refresh_daily(service=svc)

    svc.refresh_pool.assert_called_once_with(1)
    assert result['status'] == 'success'
    assert result['refreshed'] == 1
    assert result['changed'] == 1
    mock_agent.notify_agent.assert_called_once()
    event, data = mock_agent.notify_agent.call_args[0]
    assert event == 'pool_changed'
    assert data['pools_changed'][0]['added'] == ['C']
    assert data['pools_changed'][0]['removed'] == ['A']


@patch('application.services.agent_notification_service.agent_service')
def test_no_change_no_notify(mock_agent):
    svc = _make_service(
        pools=[_pool(1)],
        before_after=[(['A', 'B'], ['A', 'B'])],
    )

    result = handle_pool_refresh_daily(service=svc)

    assert result['changed'] == 0
    mock_agent.notify_agent.assert_not_called()


@patch('application.services.agent_notification_service.agent_service')
def test_refresh_failure_isolated(mock_agent):
    """单个池刷新失败不影响其他池"""
    svc = _make_service(
        pools=[_pool(1), _pool(2)],
        before_after=[],
    )
    # 第一个池 refresh 抛异常，第二个正常。
    # handler 对每个池先调 get_pool(before) 再 refresh，失败池的 after 不会查，
    # 所以 get_pool 调用序：pool1-before → pool2-before → pool2-after
    svc.refresh_pool.side_effect = [RuntimeError('scoring down'), None]
    svc.get_pool.side_effect = [
        {'symbols': ['X']},        # pool1 before
        {'symbols': ['A']},        # pool2 before
        {'symbols': ['A', 'B']},   # pool2 after
    ]

    result = handle_pool_refresh_daily(service=svc)

    assert result['status'] == 'partial'
    assert result['refreshed'] == 1
    assert len(result['failed']) == 1
    assert result['failed'][0]['pool_id'] == 1
