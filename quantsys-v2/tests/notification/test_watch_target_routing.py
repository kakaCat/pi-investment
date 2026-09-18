"""REQ-c9f899 返工项 A：L2 盯盘触发的 target_agent 真实路由测试。

背景（复核结论，可复核）：
  · 通用通知渠道层**没有 per-agent 字段**：AgentChannel 只认 variables[os_channel]、
    Agent OS SendRequest 无 target、FeishuChannel 忽略 target_agent；
  · 真实目标路由在 AgentNotificationService.resolve_target_url（POST {url}/wake）——
    agent-dh :13080 的 /wake 已实现并投递到 investor 窗口（lifecycle wake-webhook）。
  因此 L2（行动层）改走 wake 通道；L0/L1 直发路径行为不变。

可失败性（为什么不是烟雾测试）：
  · 断言 wake 实收 (event, data, target) 三元组——断掉 target 传递 / 改错落点即红；
  · 断言 wake 成功时**不走**通用渠道层，失败时**必走**飞书降级；
  · 断言响应 metadata 的 wake_target_transport：成功=agent_wake、失败=feishu_fallback，
    改坏任一分支（静默吞错 / 假装成功）即红；
  · 断言 L0/L1 与 notify_mode=agent 旧路径不触发 wake（行为不变）；
  · 断言 target 为空不抛错且落默认 agent；
  · 断言未注入 wake 通道时退回既有 agent→feishu 链路（回归保护）。
"""
import pytest

from application.notification.notification_facade import (
    NotificationFacade,
    TARGET_AGENT_TRANSPORT,
    TARGET_AGENT_TRANSPORT_WAKE,
    TARGET_AGENT_TRANSPORT_WAKE_FALLBACK,
    WAKE_EVENT_WATCH_L2,
)
from domain.notification.models.channel import ChannelResult
from domain.notification.policies.watch_delivery_policy import DEFAULT_AGENT


# ── 假实现（不触网）────────────────────────────────────────────────────────
class _RecordingNotificationService:
    """记录门面真正调用的通用渠道层方法（sent=直发 / fallback=降级链）。"""

    def __init__(self):
        self.sent = []
        self.fallback = []

    def send(self, notification):
        self.sent.append(notification)
        return ChannelResult.ok('fake feishu')

    def send_with_fallback(self, notification, primary, fallback):
        self.fallback.append((notification, primary, fallback))
        return ChannelResult.ok('fake fallback')

    def get_available_channels(self):
        return ['fake']

    def healthcheck_all(self):
        return {'fake': True}


class _FakeWakeService:
    """记录型假 wake 通道：暴露 facade 组装的 (event, data, target)。"""

    def __init__(self, status='ok', url='http://fake-dh:13080'):
        self.status = status
        self.url = url
        self.calls = []

    def notify_agent_detailed(self, event, data, target=None):
        self.calls.append((event, data, target))
        return self.status

    def resolve_target_url(self, target=None):
        return self.url


class _BoolOnlyWakeService:
    """旧实现：只有 notify_agent(event,data,target) 布尔返回（兼容性）。"""

    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def notify_agent(self, event, data, target=None):
        self.calls.append((event, data, target))
        return self.ok


class _RaisingWakeService:
    def notify_agent_detailed(self, event, data, target=None):
        raise RuntimeError('boom')


def _facade(wake=None, status='ok'):
    svc = _RecordingNotificationService()
    wake = wake if wake is not None else _FakeWakeService(status=status)
    facade = NotificationFacade(svc, agent_notification_service=wake)
    return facade, svc, wake


_BASE = dict(
    symbol='601600', name='中铝国际', price=26.57,
    condition={'type': 'price_break', 'params': {'direction': 'below', 'price': 26.88}},
    message='下破止损线 26.88', context='按宪法第 4 条清仓',
    intent='exit_stop', account='agent_brain',
)


# ── 1. L2 + target → 走 wake，payload 含 target ──────────────────────────────
def test_l2_with_target_wakes_and_payload_carries_target():
    facade, svc, wake = _facade()
    result = facade.send_watch_triggered(
        **_BASE, trigger_level='L2', target_agent='agent-ts', level='P0',
        action_hint={'action_on_trigger': 'sell'}, escalation_reason='宪法级',
        decision_audit_id='audit-1', scope='position', change_pct=-9.0, pnl_pct=-12.0,
        todo_id='t-123', todo={'id': 't-123', 'level': 'P0'},
    )

    assert len(wake.calls) == 1
    event, data, target = wake.calls[0]
    assert event == WAKE_EVENT_WATCH_L2
    assert target == 'agent-ts'                       # 实际落点按 target 解析
    assert data['target_agent'] == 'agent-ts'         # payload 也含 target
    assert data['trigger_level'] == 'L2'
    assert data['symbol'] == '601600' and data['account'] == 'agent_brain'
    assert data['message'] == '下破止损线 26.88'
    assert data['todo_id'] == 't-123' and data['todo']['id'] == 't-123'

    # wake 成功 → 不再走通用渠道层
    assert svc.sent == [] and svc.fallback == []
    assert result.success is True
    assert result.metadata['wake_target'] == 'agent-ts'
    assert result.metadata['wake_target_transport'] == TARGET_AGENT_TRANSPORT_WAKE
    assert result.metadata['wake_degraded'] is False
    assert 'unsupported' not in result.metadata['wake_target_transport']
    assert result.metadata['wake_target_url'] == 'http://fake-dh:13080'


# ── 2. wake 失败 → 降级飞书 + 响应标注降级 ───────────────────────────────────
@pytest.mark.parametrize('status', ['error', 'timeout', 'disabled', 'skipped'])
def test_l2_wake_failure_degrades_to_feishu_and_marks_degraded(status):
    facade, svc, wake = _facade(status=status)
    result = facade.send_watch_triggered(**_BASE, trigger_level='L2', target_agent='agent-dh')

    assert len(wake.calls) == 1 and wake.calls[0][2] == 'agent-dh'
    assert len(svc.sent) == 1 and svc.fallback == []
    assert svc.sent[0].preferred_channels == ['feishu']          # 真正降级飞书
    assert result.success is True                                # 飞书送达
    assert result.metadata['wake_degraded'] is True              # 但不假装 wake 成功
    assert result.metadata['wake_target_transport'] == TARGET_AGENT_TRANSPORT_WAKE_FALLBACK
    assert result.metadata['wake_status'] == status
    assert result.metadata['wake_target'] == 'agent-dh'
    assert result.metadata['wake_fallback_reason']


# ── 3. L1 直发 → 不走 wake（行为不变）───────────────────────────────────────
def test_l1_direct_path_does_not_use_wake():
    facade, svc, wake = _facade()
    result = facade.send_watch_triggered(**_BASE, trigger_level='L1')

    assert wake.calls == []
    assert svc.fallback == []
    assert len(svc.sent) == 1
    assert svc.sent[0].preferred_channels == ['feishu']
    # 非 L2 路径的 target 仍只作文本/元数据承载，如实标注渠道层不支持
    assert result.metadata['wake_target_transport'] == TARGET_AGENT_TRANSPORT


# ── 4. notify_mode=agent 但非 L2 → 仍走旧降级链（不误入 wake）────────────────
def test_notify_mode_agent_without_l2_keeps_legacy_path():
    facade, svc, wake = _facade()
    facade.send_watch_triggered(**_BASE, trigger_level='L1', notify_mode='agent')

    assert wake.calls == []
    assert svc.sent == []
    assert len(svc.fallback) == 1
    assert svc.fallback[0][1:] == ('agent', 'feishu')


# ── 5. target 为空 → 不抛错 + 落默认 agent ──────────────────────────────────
@pytest.mark.parametrize('kwargs', [
    {},                                   # 未给 target_agent（account 落到 agent-dh）
    {'target_agent': ''},                 # 显式空串
    {'target_agent': None, 'account': None},   # 无账户（数据缺陷场景）
])
def test_l2_empty_target_uses_default_agent_without_error(kwargs):
    facade, svc, wake = _facade()
    call = dict(_BASE)
    call.update(kwargs)
    result = facade.send_watch_triggered(**call, trigger_level='L2')

    assert len(wake.calls) == 1
    event, data, target = wake.calls[0]
    assert target == DEFAULT_AGENT          # 'agent-dh'（路由兜底，不抛错）
    assert data['target_agent'] == DEFAULT_AGENT
    assert result.success is True


# ── 6. 未注入 wake 通道 → 退回既有 agent→feishu，并如实标注 not_configured ──
def test_l2_without_wake_channel_keeps_legacy_path_and_annotates():
    svc = _RecordingNotificationService()
    facade = NotificationFacade(svc)          # 不注入 AgentNotificationService
    result = facade.send_watch_triggered(**_BASE, trigger_level='L2', target_agent='agent-ts')

    assert svc.sent == []
    assert len(svc.fallback) == 1
    assert svc.fallback[0][1:] == ('agent', 'feishu')
    assert result.metadata['wake_status'] == 'not_configured'
    assert result.metadata['wake_degraded'] is True
    assert result.metadata['wake_target_transport'] == TARGET_AGENT_TRANSPORT


# ── 7. 兼容性：只有 notify_agent 的旧实现也能走通 ───────────────────────────
def test_bool_only_notify_agent_implementation_supported():
    wake = _BoolOnlyWakeService(ok=True)
    svc = _RecordingNotificationService()
    facade = NotificationFacade(svc, agent_notification_service=wake)
    result = facade.send_watch_triggered(**_BASE, trigger_level='L2', target_agent='agent-ts')

    assert len(wake.calls) == 1 and wake.calls[0][2] == 'agent-ts'
    assert result.metadata['wake_target_transport'] == TARGET_AGENT_TRANSPORT_WAKE
    assert svc.sent == [] and svc.fallback == []


def test_bool_only_notify_agent_failure_degrades():
    wake = _BoolOnlyWakeService(ok=False)
    svc = _RecordingNotificationService()
    facade = NotificationFacade(svc, agent_notification_service=wake)
    result = facade.send_watch_triggered(**_BASE, trigger_level='L2', target_agent='agent-ts')

    assert len(svc.sent) == 1
    assert result.metadata['wake_degraded'] is True
    assert result.metadata['wake_status'] == 'error'


# ── 8. wake 抛异常 → 不冒泡，降级并记原因 ───────────────────────────────────
def test_wake_exception_degrades_without_raising():
    svc = _RecordingNotificationService()
    facade = NotificationFacade(svc, agent_notification_service=_RaisingWakeService())
    result = facade.send_watch_triggered(**_BASE, trigger_level='L2', target_agent='agent-dh')

    assert len(svc.sent) == 1
    assert result.metadata['wake_degraded'] is True
    assert result.metadata['wake_status'] == 'error'
    assert 'boom' in result.metadata['wake_fallback_reason']


# ── 9. 非盯盘通知不触碰 wake ────────────────────────────────────────────────
def test_non_watch_notification_does_not_touch_wake():
    facade, svc, wake = _facade()
    assert facade.send_text('hello') is True
    assert wake.calls == []
    assert len(svc.sent) == 1
