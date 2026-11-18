"""wake 传输幂等键：同一逻辑事件跨时间戳/重试保持稳定。"""
from unittest.mock import Mock, patch

from qs_agenthub.application.services.agent_notification_service import (
    AgentNotificationService, _wake_event_id,
)


def test_watch_trigger_id_ignores_order_and_transport_metadata():
    first = _wake_event_id('watch_trigger', {
        'trigger_ids': [4786, 4787], 'timestamp': '2026-11-18T09:31:00',
        'delivery_fallback_reason': 'first target unavailable',
    })
    retry = _wake_event_id('watch_trigger', {
        'trigger_ids': [4787, 4786], 'timestamp': '2026-11-18T09:38:00',
        'delivery_fallback_reason': 'another error',
    })
    changed = _wake_event_id('watch_trigger', {'trigger_ids': [4788]})
    assert first == retry
    assert first != changed


def test_post_once_sends_same_id_in_payload_and_headers():
    service = AgentNotificationService(agent_url='http://agent.invalid', allow_non_prod=True)
    response = Mock(status_code=200)
    response.json.return_value = {'success': True}
    with patch('qs_agenthub.application.services.agent_notification_service.requests.post',
               return_value=response) as post:
        status, detail = service._post_once(
            'http://agent.invalid', 'watch_trigger', {'trigger_ids': [4786]},
            target_key='agent-dh', event_id='watch_trigger:stable-4786')

    assert (status, detail) == ('ok', None)
    kwargs = post.call_args.kwargs
    assert kwargs['json']['event_id'] == 'watch_trigger:stable-4786'
    assert kwargs['headers']['Idempotency-Key'] == 'watch_trigger:stable-4786'
    assert kwargs['headers']['X-Wake-Event-Id'] == 'watch_trigger:stable-4786'


def test_watch_without_business_identity_is_rejected_before_network():
    service = AgentNotificationService(agent_url='http://agent.invalid', allow_non_prod=True)
    with patch('qs_agenthub.application.services.agent_notification_service.requests.post') as post:
        assert service.notify_agent_detailed('watch_trigger', {
            'timestamp': '2026-11-18T09:38:00', 'message': 'same trigger retried',
        }) == 'error'
    post.assert_not_called()
