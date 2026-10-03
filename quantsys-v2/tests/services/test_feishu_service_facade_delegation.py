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
    """盯盘 direct 模式是有意为之（RFC 009 双通道），不应被 P1 清理误伤。"""
    facade, captured = _capture_facade_notifications(monkeypatch)

    # 2026-10-02（REQ-261001145152-3982 审查）：**桩要把通知也记进 captured**。
    # helper 只挂了 `service.send`，而 direct 模式这条路径走的是 `send_with_fallback` ——
    # 原桩直接返回 ok 且**不记录**，于是下面的 `captured[0]` 必然
    # `IndexError: list index out of range`（**看起来像门面没发通知**，
    # 其实是测试自己的桩把证据丢了）。
    chain = []

    def _fake_with_fallback(notification, primary, fallback):
        captured.append(notification)
        chain.append((primary, fallback))
        return ChannelResult.ok(message="fallback")

    monkeypatch.setattr(facade.service, "send_with_fallback", _fake_with_fallback)

    facade.send_watch_triggered(
        symbol="600519", name="贵州茅台", price=1500.0,
        condition={"type": "price_break"},
        message="突破", notify_mode="direct")

    # 2026-10-02（REQ-261001145152-3982 审查）：**断言改为验"链路"，而非"强制通道"**。
    # 本用例的意图（docstring）是"direct 模式不应被清理误伤 → 飞书不能被丢掉"。
    # 而实现已演进为「**agent 优先、飞书降级**」（facade 第 241 行注释：
    # "direct 与 agent 两种 notify_mode 统一走「agent→feishu」"，
    # 调用为 `self.service.send_with_fallback(notification, 'agent', 'feishu')`）——
    # 飞书**仍在链路上**（且 Agent OS 不可达时直飞书兜底、并如实标注降级），
    # 只是不再用 `preferred_channels = ['feishu']` **强制短路**策略层
    # （同文件其它用例正是断言 `preferred_channels == []`，防的就是那种短路）。
    # 故这里改验"降级链确实包含 feishu"——**原意不变，口径跟上实现**。
    assert chain == [('agent', 'feishu')], f"direct 模式的降级链应含 feishu，实得 {chain}"


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

