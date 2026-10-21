"""系统运维消息分群单测（2026-10-14 · 用户裁定）

背景：调度看门狗「✅ 调度看门狗：N 项已恢复」、每日任务「✅ 每日任务完成：X」
这类**系统消息**，与「【盘前例程】」「【实盘账户·保护线恢复】」这类**股票消息**
此前落在同一个飞书群（都走 FEISHU_WEBHOOK_URL / notification_channels.alerts）。
用户要求分开：系统类 → 独立运维群（FEISHU_WEBHOOK_OPS），股票类不动。

本文件锁死三件事（都可被证伪）：
  1. FeishuChannel 的渠道名可配 —— 否则两个飞书群在 NotificationService 的
     {name: channel} 索引里互相顶掉（第二个静默覆盖第一个）；
  2. facade.send_ops_card / send_ops_text **只**打运维渠道，且运维渠道缺失时
     返回 False 而**不偷偷改投通用群**（否则"已分群"是假的）；
  3. 工厂按 FEISHU_WEBHOOK_OPS 装配独立渠道；未配置时显式降级（回退通用群），
     而不是让运维消息无处可去。
"""
from types import SimpleNamespace

from qs_notification.application.notification_facade import (
    NotificationFacade,
    OPS_CHANNEL_NAME,
)
from qs_notification.application.notification_factory import NotificationFactory
from qs_notification.domain.models.channel import ChannelResult, NotificationChannel
from qs_notification.domain.policies.notification_policy import NotificationPolicy
from qs_notification.domain.services.notification_service import NotificationService
from qs_notification.infrastructure.channels.feishu_channel import FeishuChannel

GENERAL_HOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/general-group"
OPS_HOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/ops-group"


class _RecordingChannel(NotificationChannel):
    """只记录、不外发的最小渠道实现。"""

    def __init__(self, name: str):
        self.name = name
        self.sent = []

    def send(self, notification) -> ChannelResult:
        self.sent.append(notification)
        return ChannelResult.ok()

    def supports(self, notification_type) -> bool:
        return True

    def get_name(self) -> str:
        return self.name

    def healthcheck(self) -> bool:
        return True


def _facade_with(*names):
    chans = {n: _RecordingChannel(n) for n in names}
    service = NotificationService(list(chans.values()), NotificationPolicy())
    return NotificationFacade(service), chans


# ── 1. 渠道名可配（两个飞书群必须能共存） ──────────────────────────────

def test_feishu_channel_default_name_unchanged():
    """默认名仍是 'feishu'——既有装配/测试不受影响。"""
    assert FeishuChannel(GENERAL_HOOK, []).get_name() == "feishu"


def test_feishu_channel_name_is_configurable():
    """运维群实例必须能叫 'feishu_ops'，否则会顶掉通用渠道。"""
    ch = FeishuChannel(OPS_HOOK, [], name="feishu_ops")
    assert ch.get_name() == "feishu_ops"
    assert ch.webhook_url == OPS_HOOK


# ── 2. 门面路由：只打运维群，且不静默改投 ──────────────────────────────

def test_send_ops_card_only_hits_ops_channel():
    facade, chans = _facade_with("feishu", OPS_CHANNEL_NAME)
    assert facade.send_ops_card("✅ 每日任务完成：evolution_fitness", "耗时: 0.0 分钟") is True

    assert len(chans[OPS_CHANNEL_NAME].sent) == 1
    assert chans["feishu"].sent == [], "系统消息不得再落通用群"
    notification = chans[OPS_CHANNEL_NAME].sent[0]
    assert notification.preferred_channels == [OPS_CHANNEL_NAME]
    assert notification.variables.get("ops") is True


def test_send_ops_text_only_hits_ops_channel():
    facade, chans = _facade_with("feishu", OPS_CHANNEL_NAME)
    assert facade.send_ops_text("✅ 调度看门狗：1 项已恢复", priority="high") is True
    assert len(chans[OPS_CHANNEL_NAME].sent) == 1
    assert chans["feishu"].sent == []


def test_ops_send_fails_loudly_without_ops_channel():
    """没有运维渠道时返回 False 且**一条都不发**——不许静默退回通用群。

    这是本次分群的核心不变式：若这里回退通用群，用户会看到"分群了"但消息照旧混流。
    """
    facade, chans = _facade_with("feishu")
    assert facade.send_ops_card("🚨 每日任务失败：x", "err") is False
    assert facade.send_ops_text("探活失败") is False
    assert chans["feishu"].sent == []


def test_generic_send_card_still_uses_general_channel():
    """反向不变式：普通 send_card 不受影响（股票类消息维持原路由）。"""
    facade, chans = _facade_with("feishu", OPS_CHANNEL_NAME)
    assert facade.send_card(title="【盘前例程】", content="零委托", urgency="normal") is True
    assert len(chans["feishu"].sent) == 1
    assert chans[OPS_CHANNEL_NAME].sent == []


# ── 3. 工厂装配 ────────────────────────────────────────────────────────

def _stub_settings(general, ops, notify_enabled=False):
    return SimpleNamespace(
        external=SimpleNamespace(feishu_webhook_url=general, feishu_webhook_ops=ops),
        scheduler=SimpleNamespace(
            agent_os_url="http://localhost:8080",
            agent_os_notify_enabled=notify_enabled,
        ),
    )


def _channel_map(settings):
    return {c.get_name(): c for c in NotificationFactory._create_channels(settings, [])}


def test_factory_registers_distinct_ops_channel():
    chans = _channel_map(_stub_settings(GENERAL_HOOK, OPS_HOOK))
    assert set(chans) == {"feishu", "feishu_ops"}
    assert chans["feishu"].webhook_url == GENERAL_HOOK
    assert chans["feishu_ops"].webhook_url == OPS_HOOK, "运维群必须是独立 webhook"


def test_factory_falls_back_to_general_group_when_ops_unset():
    """未配 FEISHU_WEBHOOK_OPS：渠道仍在（不丢系统告警），但落通用群——
    这是一次**显式**降级（工厂打 warning），不是静默混群。"""
    chans = _channel_map(_stub_settings(GENERAL_HOOK, None))
    assert "feishu_ops" in chans
    assert chans["feishu_ops"].webhook_url == GENERAL_HOOK
