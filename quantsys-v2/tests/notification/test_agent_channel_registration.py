"""REQ-ad0a t7 联调修复回归：通知渠道注册与降级原因如实化。

事故背景（2026-09-24 联调发现）：start-launchd.sh 的 AGENT_OS_ENABLED=false
（ADR-002 调度权拆分的本意）同时关掉了 AgentChannel 注册，「agent 优先」链路
静默失效——send_with_fallback 找不到主渠道直接降级且**无日志**。
修复：注册闸门拆为 agent_os_notify_enabled；主渠道未注册时告警并在
metadata.fallback_cause 标注，facade 据此区分降级原因。
"""
from types import SimpleNamespace

from application.notification.notification_factory import NotificationFactory
from application.notification.notification_facade import NotificationFacade
from domain.notification.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from domain.notification.services.notification_service import NotificationService


def _settings(agent_os_enabled=True, notify_enabled=None):
    scheduler = SimpleNamespace(agent_os_enabled=agent_os_enabled,
                                agent_os_url='http://localhost:8080')
    if notify_enabled is not None:
        scheduler.agent_os_notify_enabled = notify_enabled
    return SimpleNamespace(scheduler=scheduler,
                           external=SimpleNamespace(feishu_webhook_url=None))


def test_agent_channel_registered_despite_scheduler_flag_off():
    """ADR-002 调度旗 false 不再误伤通知注册（生产事故回归）。"""
    channels = NotificationFactory._create_channels(
        _settings(agent_os_enabled=False), formatters=[])
    assert any(type(c).__name__ == 'AgentChannel' for c in channels)


def test_agent_channel_skipped_only_when_notify_flag_off():
    """显式关投递开关才不注册 AgentChannel。"""
    channels = NotificationFactory._create_channels(
        _settings(agent_os_enabled=False, notify_enabled=False), formatters=[])
    assert not any(type(c).__name__ == 'AgentChannel' for c in channels)


class _OkChannel:
    def get_name(self):
        return 'feishu'

    def send(self, notification):
        from domain.notification.models.channel import ChannelResult
        return ChannelResult.ok(message='ok')

    def healthcheck(self):
        return True


def _watch_notification():
    return Notification(notification_type=NotificationType.WATCH_TRIGGERED,
                          title='盯盘触发 - 600519', content='price>1',
                          variables={'symbol': '600519', 'watch_channel': 'watch_symbol',
                                     'os_channel': 'watch_symbol'},
                          priority=NotificationPriority.NORMAL)


def test_unregistered_primary_logged_and_annotated():
    """主渠道未注册：降级送达 + metadata.fallback_cause=primary_unregistered（不再静默）。"""
    svc = NotificationService([_OkChannel()], None)          # 只注册 feishu
    facade = NotificationFacade(svc)
    result = facade.send_watch_triggered(symbol='600519', name='贵州茅台', price=1233.5,
                                         condition={}, message='触发', trigger_level='L1')
    assert result.success is True                            # 降级送达（不丢消息）
    assert result.metadata['fallback_cause'] == 'primary_unregistered'
    assert result.metadata['degraded'] is True
    assert result.metadata['degraded_reason'] == 'agent_channel_unregistered'
