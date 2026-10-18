"""待办 → owner agent 唤醒通道单测（2026-10-16，补「待办 → agent」缺环）

可失败性（每条对应一个真实事故面）：
  · 派单/催办载荷必须带 todo_id + instruction（agent 拿不到 ID 就没法 close → 工单继续挂）；
  · wake 未送达**绝不假装已发**（返回 False 让回执记 failed）；
  · P0/P1 wake 未送达时必须退回盯盘群卡片（与 L2 目标路由同一纪律：绝不静默丢事件）；
  · P2/P3 不退回卡片（级别策略：只落台账不打扰用户）。

为什么不打真网络：本模块只做"谁的载荷、往哪投、投不到怎么办"的编排；真实 HTTP 由
AgentNotificationService 负责（其单测另有覆盖），这里用假 facade 精确断言调用面。
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from application.services.watch_engine import watch_channels

NOW = datetime(2026, 10, 16, 18, 5, 58, tzinfo=timezone.utc)


class _FakeFacade:
    """记录型假门面：wake_agent 返回预设状态；send_watch_receipt 返回预设布尔"""

    def __init__(self, wake_status='ok', card_ok=True):
        self.wake_status = wake_status
        self.card_ok = card_ok
        self.wakes = []
        self.cards = []

    def wake_agent(self, event, data, target_agent=None):
        self.wakes.append({'event': event, 'data': data, 'target': target_agent})
        return self.wake_status

    def send_watch_receipt(self, title=None, content=None, os_channel=None, urgency=None):
        self.cards.append({'title': title, 'content': content, 'os_channel': os_channel})
        return self.card_ok


def _todo(**over):
    base = dict(id=91, symbol='300253', level='P1', flow_state='L3', action_kind='rule_change',
                rule_id=255, account=None, owner_kind='agent', owner_ref='agent-dh',
                autonomy='remind_only', escalate_count=1, due_at=NOW,
                created_at=NOW)
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def facade(monkeypatch):
    fake = _FakeFacade()
    # watch_channels 在函数体内 `from qs_notification.application import get_notification_facade`，
    # 故 patch 包属性（sys.modules 查得到）而不是 watch_channels 的模块属性。
    import qs_notification.application as notification_pkg
    monkeypatch.setattr(notification_pkg, 'get_notification_facade', lambda: fake)
    return fake


# ── 派单 ────────────────────────────────────────────────────

def test_assignment_wakes_owner_and_carries_close_guide(facade):
    todo = _todo()

    assert watch_channels.wake_todo_assignment(todo) is True

    assert len(facade.wakes) == 1
    call = facade.wakes[0]
    assert call['event'] == watch_channels.WAKE_EVENT_TODO_ASSIGNED
    assert call['target'] == 'agent-dh'                     # 按 owner_ref 投递
    data = call['data']
    assert data['todo_id'] == 91                            # 没 ID 就没法 close
    assert data['rule_id'] == 255 and data['symbol'] == '300253'
    assert '/api/watch/todos/91/close' in data['instruction']
    assert 'next_condition' in data['instruction']          # ignored 的必填项要在指引里


def test_assignment_returns_false_when_wake_not_delivered(facade):
    facade.wake_status = 'error'
    assert watch_channels.wake_todo_assignment(_todo()) is False


# ── 超时催办 ────────────────────────────────────────────────

def test_timeout_wake_delivers_to_owner_without_user_card(facade):
    todo = _todo(escalate_count=3)

    assert watch_channels.wake_todo_owner(todo, {'kind': 'timeout', 'channel': 'risk_stop',
                                                 'message': '待办#91 超时'}) is True

    assert [w['event'] for w in facade.wakes] == [watch_channels.WAKE_EVENT_TODO_TIMEOUT]
    assert facade.wakes[0]['data']['message'] == '待办#91 超时'
    assert facade.cards == []                               # 送达了就不打扰用户


def test_timeout_wake_falls_back_to_group_card_for_p0_p1(facade):
    """wake 未送达 + P1 → 退回盯盘群卡片（绝不静默丢事件）"""
    facade.wake_status = 'error'

    assert watch_channels.wake_todo_owner(_todo(level='P1'),
                                          {'kind': 'timeout', 'channel': 'risk_stop',
                                           'message': '待办#91 超时'}) is True

    assert len(facade.cards) == 1
    assert '超时回执' in facade.cards[0]['title']
    assert facade.cards[0]['os_channel'] == 'risk_stop'


def test_timeout_wake_does_not_fall_back_for_p2(facade):
    """P2 超时本就"只落台账不打扰用户"：wake 未送达也不退回卡片，如实记失败"""
    facade.wake_status = 'error'

    assert watch_channels.wake_todo_owner(_todo(level='P2'),
                                          {'kind': 'timeout', 'channel': 'risk_stop',
                                           'message': '待办#91 超时'}) is False
    assert facade.cards == []


def test_timeout_wake_fallback_failure_returns_false(facade):
    """退回卡片也失败 → False（回执如实记 failed，与 send_watch_receipt 抛错同义）"""
    facade.wake_status = 'error'
    facade.card_ok = False

    assert watch_channels.wake_todo_owner(_todo(), {'kind': 'timeout',
                                                    'message': 'x'}) is False
