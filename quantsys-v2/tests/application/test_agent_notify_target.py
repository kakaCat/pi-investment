"""Agent 投递多目标单测（2026-09-11，w-aebfddcd）

分类 → agent 的**决策**在 domain 策略；本服务只做传输：按 agent 键解析地址、投递、回退。
"""
import pytest

from application.services.agent_notification_service import (
    AGENT_DH, AGENT_TS, AgentNotificationService,
)


class _Resp:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {"success": True}
        self.text = str(self._body)

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("AGENT_API_URL", "AGENT_API_URL_DH", "AGENT_API_URL_TS", "AGENT_NOTIFY_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AGENT_NOTIFY_ENABLED", "true")
    # 本模块测传输层（HTTP 已 mock），显式开非生产闸门；
    # 闸门本身的行为见 tests/application/test_notify_env_guard.py
    monkeypatch.setenv("AGENT_NOTIFY_ALLOW_TEST", "true")


def test_default_urls_split_by_agent():
    svc = AgentNotificationService()
    assert svc.resolve_target_url(None) == "http://127.0.0.1:13080"
    assert svc.resolve_target_url(AGENT_DH) == "http://127.0.0.1:13080"
    assert svc.resolve_target_url(AGENT_TS) == "http://127.0.0.1:3002"


def test_env_overrides_per_agent(monkeypatch):
    monkeypatch.setenv("AGENT_API_URL_TS", "http://127.0.0.1:3999/")
    assert AgentNotificationService().resolve_target_url(AGENT_TS) == "http://127.0.0.1:3999"


def test_explicit_targets_beat_env(monkeypatch):
    monkeypatch.setenv("AGENT_API_URL_TS", "http://127.0.0.1:3999")
    svc = AgentNotificationService(targets={AGENT_TS: "http://127.0.0.1:4001"})
    assert svc.resolve_target_url(AGENT_TS) == "http://127.0.0.1:4001"


def test_delivers_to_selected_agent(monkeypatch):
    calls = []
    monkeypatch.setattr("application.services.agent_notification_service.requests.post",
                        lambda url, **kw: (calls.append((url, kw.get("json"))), _Resp())[1])
    svc = AgentNotificationService()
    assert svc.notify_agent("watch_digest", {"a": 1}, target=AGENT_TS) is True
    assert calls[0][0] == "http://127.0.0.1:3002/wake"
    assert calls[0][1]["event"] == "watch_digest"


def test_unreachable_target_falls_back_to_default_with_marker(monkeypatch):
    """目标 agent 不在线 → 回退默认 agent 并在 payload 标注，绝不静默丢事件"""
    import requests as _requests
    calls = []

    def _post(url, **kw):
        calls.append((url, kw.get("json")))
        if len(calls) == 1:
            raise _requests.exceptions.ConnectionError("connection refused")
        return _Resp()

    monkeypatch.setattr("application.services.agent_notification_service.requests.post", _post)
    svc = AgentNotificationService()
    assert svc.notify_agent("watch_digest", {"a": 1}, target=AGENT_TS) is True
    assert len(calls) == 2
    assert calls[0][0] == "http://127.0.0.1:3002/wake"
    assert calls[1][0] == "http://127.0.0.1:13080/wake"
    fb = calls[1][1]["data"]
    assert fb["delivery_fallback_from"] == AGENT_TS
    assert fb["delivery_fallback_reason"]


def test_timeout_does_not_fall_back(monkeypatch):
    """超时=事件大概率已送达 → 不重投（避免重复唤醒/重复动作）"""
    import requests as _requests
    calls = []

    def _post(url, **kw):
        calls.append(url)
        raise _requests.exceptions.Timeout("slow")

    monkeypatch.setattr("application.services.agent_notification_service.requests.post", _post)
    svc = AgentNotificationService()
    assert svc.notify_agent_detailed("watch_digest", {}, target=AGENT_TS) == "timeout"
    assert len(calls) == 1


def test_disabled_short_circuits(monkeypatch):
    monkeypatch.setenv("AGENT_NOTIFY_ENABLED", "false")
    svc = AgentNotificationService()
    assert svc.notify_agent_detailed("x", {}, target=AGENT_TS) == "disabled"
