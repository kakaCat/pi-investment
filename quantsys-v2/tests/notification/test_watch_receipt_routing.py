"""REQ-260924104605-ad0a t3 路由接线测试（FR-2/FR-3/FR-10）。

可失败性：
  · direct 分支 agent 优先、os_channel 直透（改回直飞书即红）；
  · Agent OS 不可达 → 降级飞书且 metadata 含 degraded 标注（漏标注即红）；
  · 回执 os_channel 映射：timeout/P0 → risk_stop，其余 → watch_symbol（映射错即红）；
  · 回执正文不再外露「频道：」（FR-12，回归即红）；
  · rule_id 随通知下发到 variables（断链即红）。
"""
from types import SimpleNamespace

import pytest

from application.notification.notification_facade import NotificationFacade
from application.services.watch_engine import watch_channels
from domain.notification.models.channel import ChannelResult
from domain.notification.models.notification import NotificationStatus


_BASE = dict(
    symbol='601600', name='中铝国际', price=26.57,
    condition={'type': 'price_break', 'params': {'direction': 'below', 'price': 26.88}},
    message='下破止损线 26.88', context='按宪法第 4 条清仓',
    intent='exit_stop', account='agent_brain',
)


class _RecordingService:
    """记录型假服务；mark_fallback=True 时模拟「主渠道失败、降级渠道成功」。"""

    def __init__(self, mark_fallback: bool = False):
        self.sent = []
        self.fallback = []
        self.mark_fallback = mark_fallback

    def send(self, notification):
        self.sent.append(notification)
        return ChannelResult.ok('fake 直发')

    def send_with_fallback(self, notification, primary, fallback):
        self.fallback.append((notification, primary, fallback))
        if self.mark_fallback:
            notification.mark_fallback()          # 模拟真实降级链的状态转换
        return ChannelResult.ok('fake 降级链')

    def get_available_channels(self):
        return ['fake']

    def healthcheck_all(self):
        return {'fake': True}


# ── FR-2：direct 走 agent 优先降级链 + 降级标注 ─────────────────────────────
def test_direct_branch_prefers_agent_with_os_channel_passthrough():
    svc = _RecordingService()
    NotificationFacade(svc).send_watch_triggered(**_BASE, trigger_level='L1')
    assert svc.sent == []                                  # 不再直飞书
    notification, primary, fallback = svc.fallback[-1]
    assert (primary, fallback) == ('agent', 'feishu')
    assert notification.variables['os_channel'] == 'risk_stop'   # exit_stop → 风控频道直透


def test_direct_branch_fallback_annotates_degraded_metadata():
    svc = _RecordingService(mark_fallback=True)
    result = NotificationFacade(svc).send_watch_triggered(**_BASE, trigger_level='L1')
    assert result.metadata['degraded'] is True
    assert result.metadata['degraded_reason'] == 'agent_os_unreachable'
    assert result.metadata['delivery'] == 'feishu_fallback'


def test_direct_branch_primary_success_no_degraded_mark():
    svc = _RecordingService(mark_fallback=False)
    result = NotificationFacade(svc).send_watch_triggered(**_BASE, trigger_level='L1')
    assert 'degraded' not in result.metadata


# ── FR-10：rule_id 随通知下发 ────────────────────────────────────────────────
def test_rule_id_carried_into_variables():
    svc = _RecordingService()
    NotificationFacade(svc).send_watch_triggered(**_BASE, trigger_level='L1', rule_id=119)
    assert svc.fallback[-1][0].variables['rule_id'] == 119


# ── FR-3：回执 os_channel 映射 + 去「频道：」─────────────────────────────────
class _FakeFacade:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def send_watch_receipt(self, title, content, *, os_channel, urgency='normal'):
        self.calls.append(dict(title=title, content=content,
                               os_channel=os_channel, urgency=urgency))
        return self.ok


@pytest.fixture
def fake_facade(monkeypatch):
    facade = _FakeFacade()
    monkeypatch.setattr('application.notification.get_notification_facade', lambda: facade)
    return facade


def test_receipt_timeout_routes_risk_stop(fake_facade):
    watch_channels.send_watch_receipt({'kind': 'timeout', 'channel': 'alerts',
                                       'message': 'm', 'level': 'P1'})
    call = fake_facade.calls[-1]
    assert call['os_channel'] == 'risk_stop'
    assert call['urgency'] == 'high'


def test_receipt_p0_routes_risk_stop(fake_facade):
    watch_channels.send_watch_receipt({'kind': 'escalate', 'channel': 'reports',
                                       'message': 'm', 'level': 'P0'})
    assert fake_facade.calls[-1]['os_channel'] == 'risk_stop'


def test_receipt_normal_routes_watch_symbol(fake_facade):
    watch_channels.send_watch_receipt({'kind': 'escalate', 'channel': 'reports',
                                       'message': 'm', 'level': 'P1'})
    call = fake_facade.calls[-1]
    assert call['os_channel'] == 'watch_symbol'
    assert call['urgency'] == 'normal'


def test_receipt_explicit_os_channel_wins(fake_facade):
    """聚合卡（t4）显式给出的 os_channel 优先。"""
    watch_channels.send_watch_receipt({'kind': 'timeout', 'message': 'm',
                                       'os_channel': 'watch_symbol'})
    assert fake_facade.calls[-1]['os_channel'] == 'watch_symbol'


def test_receipt_content_never_leaks_channel_label(fake_facade):
    """FR-12：回执正文不得出现「频道：」。"""
    watch_channels.send_watch_receipt({'kind': 'timeout', 'channel': 'alerts', 'message': 'm'})
    assert '频道：' not in fake_facade.calls[-1]['content']


def test_alert_routes_watch_symbol_with_high_urgency(fake_facade):
    watch_channels.send_watch_alert('心跳告警 | 引擎 5 分钟无心跳')
    call = fake_facade.calls[-1]
    assert call['os_channel'] == 'watch_symbol'
    assert call['urgency'] == 'high'
    assert call['title'] == '心跳告警'


def test_receipt_send_failure_raises_loudly(fake_facade):
    fake_facade.ok = False
    with pytest.raises(RuntimeError):
        watch_channels.send_watch_receipt({'kind': 'timeout', 'message': 'm'})
