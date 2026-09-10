"""AgentChannel ↔ Agent OS 契约测试（2026-09-11，w-23c70356）。

背景：AgentChannel 原实现 POST {agent_url}/wake（旧 wake-channel 网关契约，默认 :3002，
该服务早已不存在），实测恒失败 → NotificationPolicy 里写好的「agent 优先、feishu 降级」
从未生效。本测试锁定新契约：
    POST {agent_os_url}/api/v1/notifications/send
    body {channel,title,content,urgency,metadata}
    resp {"log_id","success","error"?,"message_id"?}
并覆盖故障路径（业务失败/HTTP 错误/连接失败/响应超时）与渠道码映射。
"""

import requests

from domain.notification.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from domain.notification.policies.notification_policy import NotificationPolicy
from infrastructure.notification.channels.agent_channel import AgentChannel


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class StubChannel:
    def supports(self, notification_type):
        return True


def _channel():
    return AgentChannel(agent_url="http://os.test:8080", timeout=5)


def _notification(**kwargs):
    params = dict(
        notification_type=NotificationType.SYSTEM_ALERT,
        title="数据质量告警（2 项）",
        content="回填失败率过高",
    )
    params.update(kwargs)
    return Notification(**params)


def test_channel_code_mapping_by_type_and_priority():
    ch = _channel()
    assert ch.resolve_channel_code(_notification()) == "alerts"
    assert ch.resolve_channel_code(
        _notification(notification_type=NotificationType.TRADE_SIGNAL)
    ) == "trading"
    assert ch.resolve_channel_code(
        _notification(notification_type=NotificationType.DAILY_REPORT,
                      priority=NotificationPriority.LOW)
    ) == "reports"
    assert ch.resolve_channel_code(
        _notification(notification_type=NotificationType.DAILY_REPORT,
                      priority=NotificationPriority.HIGH)
    ) == "alerts"


def test_channel_code_explicit_override_wins():
    ch = _channel()
    n = _notification(notification_type=NotificationType.DAILY_REPORT,
                      priority=NotificationPriority.LOW,
                      variables={"os_channel": "trading"})
    assert ch.resolve_channel_code(n) == "trading"


def test_send_posts_agent_os_contract(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return FakeResponse(200, {"log_id": "log_1", "success": True, "message_id": "msg_1"})

    monkeypatch.setattr(requests, "post", fake_post)
    result = _channel().send(_notification(variables={"symbol": "600519", "os_channel": "reports"}))

    assert captured["url"] == "http://os.test:8080/api/v1/notifications/send"
    assert captured["json"]["channel"] == "reports"
    assert captured["json"]["title"] == "数据质量告警（2 项）"
    assert captured["json"]["urgency"] == "normal"
    assert captured["json"]["metadata"]["symbol"] == "600519"
    assert "os_channel" not in captured["json"]["metadata"]
    assert captured["timeout"] == (3, 5)
    assert result.success is True
    assert result.metadata["log_id"] == "log_1"


def test_send_reports_os_level_failure(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(
        200, {"success": False, "error": "channel not found or disabled"}))
    result = _channel().send(_notification())
    assert result.success is False
    assert "not found or disabled" in result.message


def test_send_reports_http_error(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(404, None, "404 page"))
    result = _channel().send(_notification())
    assert result.success is False
    assert "404" in result.message


def test_send_connection_error_is_reported_not_raised(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "post", boom)
    result = _channel().send(_notification())
    assert result.success is False
    assert "无法连接到 Agent OS" in result.message
    assert "os.test:8080" in result.message


def test_send_read_timeout_triggers_fallback(monkeypatch):
    """读超时必须报错（而非 success），否则 NotificationService 不会降级飞书。"""
    def boom(*a, **k):
        raise requests.exceptions.ReadTimeout("read timed out")

    monkeypatch.setattr(requests, "post", boom)
    result = _channel().send(_notification())
    assert result.success is False
    assert "降级下一渠道" in result.message


def test_healthcheck_hits_agent_os_health(monkeypatch):
    seen = {}

    def fake_get(url, timeout=None):
        seen.update(url=url, timeout=timeout)
        return FakeResponse(200, {})

    monkeypatch.setattr(requests, "get", fake_get)
    assert _channel().healthcheck() is True
    assert seen["url"] == "http://os.test:8080/health"

    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(requests, "get", boom)
    assert _channel().healthcheck() is False


def test_policy_orders_agent_first_then_feishu():
    """无 preferred_channels 时策略给出 OS 优先、飞书降级（P1 回归点）。"""
    policy = NotificationPolicy()
    channels = {"agent": StubChannel(), "feishu": StubChannel()}
    assert policy.select_channels(_notification(), channels) == ["agent", "feishu"]


def test_preferred_channels_still_short_circuits():
    """盯盘 direct 模式（facade.send_watch_triggered）仍可显式指定渠道，属设计而非缺陷。"""
    policy = NotificationPolicy()
    channels = {"agent": StubChannel(), "feishu": StubChannel()}
    n = _notification(preferred_channels=["feishu"])
    assert policy.select_channels(n, channels) == ["feishu"]
