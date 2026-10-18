"""旧版发送服务 → NotificationFacade 收敛测试（2026-09-11，w-23c70356）。

P2 迁移：application/services/feishu_service.py 的 FeishuNotificationService 曾直接
requests.post 飞书 webhook（绕过 DDD 通知域），本测试锁定它已收敛为门面薄壳。
P1 回归：门面不再硬编码 preferred_channels=['feishu']，策略的「agent 优先、飞书降级」生效。
"""

import application.notification as notification_pkg
import application.notification.legacy_adapters as legacy_adapters
from application.services.feishu_service import FeishuNotificationService
from domain.notification.models.channel import ChannelResult


def _patch_legacy_bridge(monkeypatch, fake):
    """让 legacy_adapters 的桥接层拿到假门面（并清掉单例缓存）。"""
    monkeypatch.setattr(legacy_adapters, "get_notification_facade", lambda: fake)
    monkeypatch.setattr(legacy_adapters, "_feishu_service_instance", None, raising=False)


class FakeFacade:
    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises

    def send_text(self, text, priority="normal", mention_all=False):
        self.calls.append(("send_text", text, mention_all))
        if self.raises:
            raise self.raises
        return True

    def send_card(self, title=None, content=None, urgency="normal", actions=None):
        self.calls.append(("send_card", title, content, urgency, actions))
        if self.raises:
            raise self.raises
        return True


def test_feishu_service_send_text_delegates_to_facade(monkeypatch):
    fake = FakeFacade()
    _patch_legacy_bridge(monkeypatch, fake)

    assert FeishuNotificationService().send_text("✅ 每日任务完成：watch_rule_health") is True
    assert fake.calls == [("send_text", "✅ 每日任务完成：watch_rule_health", False)]


def test_feishu_service_send_card_delegates_to_facade(monkeypatch):
    fake = FakeFacade()
    _patch_legacy_bridge(monkeypatch, fake)

    ok = FeishuNotificationService().send_card(
        title="🚨 每日任务失败：kline_sync", content="错误: timeout", urgency="high",
        actions=[{"label": "查看", "url": "http://x"}], extra_elements=[{"tag": "hr"}])
    assert ok is True
    assert fake.calls[0][0] == "send_card"
    assert fake.calls[0][1] == "🚨 每日任务失败：kline_sync"
    assert fake.calls[0][3] == "high"
    assert fake.calls[0][4] == [{"label": "查看", "url": "http://x"}]


def test_feishu_service_swallows_facade_exception(monkeypatch):
    fake = FakeFacade(raises=RuntimeError("facade down"))
    _patch_legacy_bridge(monkeypatch, fake)

    svc = FeishuNotificationService()
    assert svc.send_text("hi") is False
    assert svc.send_card(title="t", content="c") is False


def test_report_builders_funnel_through_send_card(monkeypatch):
    """send_daily_report/send_alert 等最终汇聚到 send_card → 一并收敛到门面。"""
    fake = FakeFacade()
    _patch_legacy_bridge(monkeypatch, fake)

    svc = FeishuNotificationService()
    svc.send_daily_report({"date": "2026-09-10", "sh_index_change": "+0.5%"})
    svc.send_alert(alert_type="risk", symbol="600519", message="测试告警")
    kinds = [c[0] for c in fake.calls]
    assert kinds == ["send_card", "send_card"]


def _capture_facade_notifications(monkeypatch):
    """替换真实门面的 service.send，捕获 Notification 对象（不真发）。"""
    facade = notification_pkg.get_notification_facade()
    captured = []

    def fake_send(notification):
        captured.append(notification)
        return ChannelResult.ok(message="captured")

    monkeypatch.setattr(facade.service, "send", fake_send)
    return facade, captured


def test_facade_no_longer_forces_feishu(monkeypatch):
    facade, captured = _capture_facade_notifications(monkeypatch)

    facade.send_card(title="数据质量告警（2 项）", content="回填失败率过高", urgency="high")
    facade.send_text("普通文本")
    facade.send_alert(alert_type="risk", symbol="600519", message="风险提示")

    assert len(captured) == 3
    for notification in captured:
        assert notification.preferred_channels == [], (
            "preferred_channels 短路会让 NotificationPolicy 失效（OS 优先被绕过）")


def test_facade_agent_reminder_still_agent_only(monkeypatch):
    facade, captured = _capture_facade_notifications(monkeypatch)

    facade.send_agent_reminder(agent_id="investor", message="提醒内容")

    assert captured[0].preferred_channels == ["agent"]


def test_watch_direct_mode_keeps_feishu(monkeypatch):
    """盯盘触发走「agent 优先、feishu 降级」的 send_with_fallback（现行契约；RFC 009
    双通道已由 REQ-260924104605-ad0a FR-2 的 fallback 链取代）：facade 不短路
    preferred_channels（[] = 交给 NotificationPolicy 在 service 内部决定顺序）。
    2026-10-16 改断言对齐现行契约（原断言基于已删除的 facade 层 feishu 直投逻辑，
    自 facade 改走 send_with_fallback 后本测试即红灯，与工作区改动无关）。"""
    facade, captured = _capture_facade_notifications(monkeypatch)
    fallback_calls = []

    def fake_fallback(notification, primary, fallback):
        fallback_calls.append((primary, fallback))
        captured.append(notification)
        return ChannelResult.ok(message="fallback")

    monkeypatch.setattr(facade.service, "send_with_fallback", fake_fallback)

    facade.send_watch_triggered(
        symbol="600519", name="贵州茅台", price=1500.0,
        condition={"type": "price_break"},
        message="突破", notify_mode="direct")

    assert fallback_calls == [('agent', 'feishu')]
    assert captured[0].preferred_channels == []


# ==================== 旁路清理（2026-09-11 第二轮：残留直接删除） ====================

def test_direct_webhook_notifier_is_gone():
    """utils/feishu_notifier.py（自行 POST 飞书 webhook 的旁路）不应复活。"""
    import importlib

    import pytest

    with pytest.raises(ImportError):
        importlib.import_module("utils.feishu_notifier")


def test_facade_send_rebalance_notification(monkeypatch):
    facade, captured = _capture_facade_notifications(monkeypatch)

    facade.send_rebalance_notification({
        "date": "2026-09-10",
        "positions": 2,
        "top_stocks": [("600519", 0.91, 0.15, "(¥1500.00，买入)")],
        "buy_trades": [("600519", 100, 1500.0)],
        "sell_trades": [("000001", 200, 11.5)],
    })

    notification = captured[0]
    assert notification.notification_type.value == "rebalance"
    assert notification.preferred_channels == []          # 交给策略选渠道（OS 优先）
    assert "600519" in notification.content
    assert "000001" in notification.content
    assert "2026-09-10" in notification.title


def test_facade_send_risk_alert_is_high_priority(monkeypatch):
    facade, captured = _capture_facade_notifications(monkeypatch)

    facade.send_risk_alert({"trigger": "回撤触发", "losing_stocks": ["600887"]})

    notification = captured[0]
    assert notification.notification_type.value == "risk_alert"
    assert notification.priority.value == "high"
    assert "回撤触发" in notification.content
    assert "600887" in notification.content

