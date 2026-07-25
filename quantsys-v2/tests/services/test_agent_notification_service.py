"""
Agent 通知服务测试

覆盖链路二（v2 调度任务 → 通知 agent）的修复：
1. 模块可正常 import（修复前因缺 import logging 在 import 时抛 NameError）
2. send_reminder 通过 /wake 推送 agent_reminder 事件
3. handle_agent_reminder 在 agent 不可达时仍返回 success（降级记日志）
"""
from unittest.mock import patch, MagicMock


def test_agent_notification_service_module_imports():
    """模块 import 不应抛 NameError（缺 import logging 的回归测试）"""
    import importlib
    import application.services.agent_notification_service as m
    importlib.reload(m)
    assert hasattr(m, 'AgentNotificationService')
    assert hasattr(m, 'agent_service')


def test_market_monitor_scheduler_module_imports():
    """market_monitor_scheduler 模块 import 不应抛 NameError"""
    import importlib
    import application.services.market_monitor_scheduler as m
    importlib.reload(m)
    assert hasattr(m, 'MarketMonitorScheduler')


def test_send_reminder_posts_agent_reminder_event():
    """send_reminder 应向 agent /wake 发送 agent_reminder 事件"""
    from application.services.agent_notification_service import AgentNotificationService

    service = AgentNotificationService(agent_url='http://agent.test:3001')

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {'success': True}

    with patch('application.services.agent_notification_service.requests.post',
               return_value=mock_resp) as mock_post:
        result = service.send_reminder(
            agent_id='default_agent',
            message='每日复盘提醒',
            remind_at='2026-07-19 15:30'
        )

    assert result is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == 'http://agent.test:3001/wake'
    payload = kwargs['json']
    assert payload['event'] == 'agent_reminder'
    assert payload['data']['agent_id'] == 'default_agent'
    assert payload['data']['message'] == '每日复盘提醒'
    assert payload['data']['remind_at'] == '2026-07-19 15:30'


def test_send_reminder_returns_false_when_agent_unreachable():
    """agent 不可达时 send_reminder 返回 False 而不抛异常"""
    import requests as real_requests
    from application.services.agent_notification_service import AgentNotificationService

    service = AgentNotificationService(agent_url='http://agent.test:3001')

    with patch('application.services.agent_notification_service.requests.post',
               side_effect=real_requests.exceptions.ConnectionError('refused')):
        assert service.send_reminder(agent_id='a', message='m', remind_at=None) is False


def test_notify_agent_detailed_ok():
    """200 且 success → 'ok'，且 notify_agent 返回 True"""
    from application.services.agent_notification_service import AgentNotificationService

    service = AgentNotificationService(agent_url='http://agent.test:3001')
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {'success': True}

    with patch('application.services.agent_notification_service.requests.post',
               return_value=mock_resp):
        assert service.notify_agent_detailed('watch_triggered', {}) == 'ok'
        assert service.notify_agent('watch_triggered', {}) is True


def test_notify_agent_detailed_timeout():
    """Timeout → 'timeout'，且 notify_agent 返回 False"""
    import requests as real_requests
    from application.services.agent_notification_service import AgentNotificationService

    service = AgentNotificationService(agent_url='http://agent.test:3001')

    with patch('application.services.agent_notification_service.requests.post',
               side_effect=real_requests.exceptions.Timeout('slow')):
        assert service.notify_agent_detailed('watch_triggered', {}) == 'timeout'
        assert service.notify_agent('watch_triggered', {}) is False


def test_notify_agent_detailed_error():
    """ConnectionError → 'error'，且 notify_agent 返回 False"""
    import requests as real_requests
    from application.services.agent_notification_service import AgentNotificationService

    service = AgentNotificationService(agent_url='http://agent.test:3001')

    with patch('application.services.agent_notification_service.requests.post',
               side_effect=real_requests.exceptions.ConnectionError('refused')):
        assert service.notify_agent_detailed('watch_triggered', {}) == 'error'
        assert service.notify_agent('watch_triggered', {}) is False


def test_notify_agent_detailed_disabled():
    """通知禁用 → 'disabled'，不发请求"""
    from application.services.agent_notification_service import AgentNotificationService

    service = AgentNotificationService(agent_url='http://agent.test:3001')
    service.enabled = False

    with patch('application.services.agent_notification_service.requests.post') as mock_post:
        assert service.notify_agent_detailed('watch_triggered', {}) == 'disabled'
        mock_post.assert_not_called()


def test_init_timeout_override():
    """显式 timeout 参数优先于环境变量"""
    from application.services.agent_notification_service import AgentNotificationService

    assert AgentNotificationService(timeout=10).timeout == 10


def test_handle_agent_reminder_success_when_agent_unreachable():
    """调度任务 handler 在 agent 不可达时降级为记日志，仍返回 success"""
    from application.services.scheduler_tasks import handle_agent_reminder

    result = handle_agent_reminder({'agent_id': 'a', 'message': '复盘时间到'})

    assert result['action'] == 'agent_reminder'
    assert result['status'] == 'success'
    assert result['message'] == '复盘时间到'


def test_agent_reminder_handler_registered_once():
    """agent_reminder 只注册一次且指向有效 handler"""
    from application.services.scheduler_tasks import _TASK_HANDLERS, get_task_handler

    handler = get_task_handler('agent_reminder')
    assert handler is _TASK_HANDLERS['agent_reminder']
    result = handler({'message': 'test'})
    assert result['status'] == 'success'


def test_notify_sends_token_header_and_default_port_3002(monkeypatch):
    """token 配置时请求带 X-Wake-Token；默认 URL 为 3002"""
    from unittest.mock import patch, MagicMock
    monkeypatch.delenv('AGENT_API_URL', raising=False)
    monkeypatch.setenv('AGENT_API_TOKEN', 'tok-123')
    from application.services.agent_notification_service import AgentNotificationService

    service = AgentNotificationService()
    assert service.agent_url == 'http://127.0.0.1:3002'

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {'success': True}
    with patch('application.services.agent_notification_service.requests.post', return_value=mock_resp) as mock_post:
        assert service.notify_agent('agent_reminder', {'message': 'hi'}) is True
    assert mock_post.call_args.kwargs['headers']['X-Wake-Token'] == 'tok-123'
