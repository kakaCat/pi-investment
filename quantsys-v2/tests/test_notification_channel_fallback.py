"""通知渠道兜底测试（REQ-261004154902-a7cd · t8 / FR-9）。

覆盖验收标准：
- ``select_channels('rebalance')`` 与 ``select_channels('risk_alert')`` 必须**包含 feishu**
  （当前为 `['agent']` —— 这正是「不发信息」的根因：Agent OS 8080 已下线，7 类通知 100% 丢弃）；
- 渠道顺序仍是「agent 优先、飞书兜底」；
- 飞书渠道对**没有专用模板**的类型（REBALANCE / RISK_ALERT）必须能渲染，而不是返回
  「不支持的通知类型」；
- 若连兜底渲染器都没有，必须返回 None 并留 warning（不许静默）。

全部用例零网络：只调纯选择逻辑与格式化器选择，不做任何 HTTP。
"""
from __future__ import annotations

import logging

import pytest

from domain.notification.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from domain.notification.policies.notification_policy import NotificationPolicy
from infrastructure.notification.formatters.feishu_formatters import (
    SystemAlertFormatter,
    WatchTriggeredFormatter,
)
from infrastructure.notification.channels.feishu_channel import FeishuChannel


class _FakeChannel:
    """只实现 policy 需要的最小接口。"""

    def __init__(self, supports: bool) -> None:
        self._supports = supports

    def supports(self, notification_type) -> bool:  # noqa: ARG002 - 契约如此
        return self._supports

    def send(self, notification):  # pragma: no cover - policy 不调 send
        raise AssertionError("policy 不应在选渠道时发送")


def _notification(kind: NotificationType) -> Notification:
    return Notification(
        notification_type=kind,
        title="测试标题",
        content="测试正文",
        priority=NotificationPriority.NORMAL,
    )


# -- ① select_channels 必须把飞书带上（兜底） --------------------------------
@pytest.mark.parametrize(
    "kind",
    [
        NotificationType.REBALANCE,
        NotificationType.RISK_ALERT,
        NotificationType.TRADE_SIGNAL,
        NotificationType.VERIFICATION,
        NotificationType.PREMARKET_REPORT,
    ],
)
def test_feishu_is_kept_as_fallback_for_types_agent_claims_to_support(kind):
    """agent 恒报支持时，飞书必须仍作为兜底留在候选里（否则 8080 一死就全丢）。"""
    policy = NotificationPolicy()
    channels = {
        "agent": _FakeChannel(supports=True),   # 恒真，就是它把飞书挤出去的
        "feishu": _FakeChannel(supports=False),  # 没有专用模板 → 旧逻辑直接排除它
    }

    selected = policy.select_channels(_notification(kind), channels)

    assert "feishu" in selected, f"{kind.value} 仍会把飞书排除，8080 一死就丢消息"
    assert selected[0] == "agent", "顺序必须是 agent 优先（能力支持者排前面）"


def test_both_supported_keeps_priority_order():
    policy = NotificationPolicy()
    channels = {"agent": _FakeChannel(True), "feishu": _FakeChannel(True)}

    selected = policy.select_channels(_notification(NotificationType.STOP_LOSS), channels)

    assert selected == ["agent", "feishu"]


def test_no_supported_channel_returns_available():
    policy = NotificationPolicy()
    channels = {"agent": _FakeChannel(False), "feishu": _FakeChannel(False)}

    selected = policy.select_channels(_notification(NotificationType.REBALANCE), channels)

    assert set(selected) == {"agent", "feishu"}


def test_explicit_preferred_channel_is_still_respected():
    """显式指定首选渠道时不得被兜底逻辑改写。"""
    policy = NotificationPolicy()
    notification = _notification(NotificationType.REBALANCE)
    notification = Notification(
        notification_type=NotificationType.REBALANCE,
        title=notification.title,
        content=notification.content,
        preferred_channels=["feishu"],
    )
    channels = {"agent": _FakeChannel(True), "feishu": _FakeChannel(False)}

    assert policy.select_channels(notification, channels) == ["feishu"]


# -- ② 飞书渠道对无专用模板的类型必须能渲染 ----------------------------------
def _channel(formatters):
    return FeishuChannel(webhook_url="https://example.invalid/hook", formatters=formatters)


def test_catch_all_formatter_renders_rebalance():
    channel = _channel([WatchTriggeredFormatter(), SystemAlertFormatter()])
    formatter = channel._select_formatter(_notification(NotificationType.REBALANCE))

    assert formatter is not None, "调仓通知必须能渲染（否则永远到不了用户）"
    assert formatter.__class__.__name__ == "SystemAlertFormatter"


def test_catch_all_formatter_renders_risk_alert():
    channel = _channel([WatchTriggeredFormatter(), SystemAlertFormatter()])
    formatter = channel._select_formatter(_notification(NotificationType.RISK_ALERT))

    assert formatter is not None
    assert formatter.__class__.__name__ == "SystemAlertFormatter"


def test_dedicated_formatter_still_wins_over_catch_all():
    channel = _channel([SystemAlertFormatter(), WatchTriggeredFormatter()])
    formatter = channel._select_formatter(_notification(NotificationType.WATCH_TRIGGERED))

    assert formatter.__class__.__name__ == "WatchTriggeredFormatter", "专用模板必须优先于兜底"


def test_without_catch_all_returns_none(caplog):
    """没有任何兜底渲染器时必须返回 None（由调用方记 warning），不许静默成功。"""
    channel = _channel([WatchTriggeredFormatter()])

    with caplog.at_level(logging.INFO):
        formatter = channel._select_formatter(_notification(NotificationType.REBALANCE))

    assert formatter is None


def test_system_alert_formatter_is_the_designated_catch_all():
    assert getattr(SystemAlertFormatter(), "catch_all", False) is True
    assert getattr(WatchTriggeredFormatter(), "catch_all", False) is False
