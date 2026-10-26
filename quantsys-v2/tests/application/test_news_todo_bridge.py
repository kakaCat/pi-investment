"""消息 → P1 待办桥（REQ-261021194640-69b8 FR-3，卡 t-27e8c7）

判据：critical 建 1 条 P1 待办（action_kind=rule_change + evidence）、soft 不建、
同一标的未收敛消息待办存在时不重复建、单条失败不抛错。
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.news_todo_bridge import NewsTodoBridge

NOW = datetime(2026, 10, 21, 16, 30)


class FakeTodoService:
    def __init__(self, boom_on=None):
        self.creates = []
        self._boom_on = boom_on
        self._seq = 0

    def create(self, **kwargs):
        if self._boom_on and kwargs.get('symbol') == self._boom_on:
            raise RuntimeError('todo db down')
        self._seq += 1
        self.creates.append(kwargs)
        return SimpleNamespace(id=100 + self._seq, **kwargs)


class FakeTodoRepo:
    def __init__(self, rows):
        self.rows = rows

    def list_pending(self, **kwargs):
        return list(self.rows)


def _alert(**over):
    base = dict(tier='critical', symbol='600519.SH', account='agent_virtual',
                titles=['某公司被立案调查'], words=['立案'], alert_id=42,
                source='news')
    base.update(over)
    return base


def _bridge(service=None, repo=None):
    return NewsTodoBridge(service or FakeTodoService(), todo_repo=repo,
                          now_fn=lambda: NOW)


def test_critical_creates_one_p1_todo_with_evidence():
    svc = FakeTodoService()
    out = _bridge(svc).dispatch([_alert()])

    assert out['errors'] == [] and out['skipped'] == []
    assert len(out['created']) == 1 and len(svc.creates) == 1
    kwargs = svc.creates[0]
    assert kwargs['symbol'] == '600519.SH'
    assert kwargs['level'] == 'P1'
    assert kwargs['action_kind'] == 'rule_change'
    assert kwargs['account'] == 'agent_virtual'
    assert kwargs['sla_seconds'] == 1800
    assert kwargs['due_at'] == NOW.replace(hour=17, minute=0)
    ev = kwargs['evidence']
    assert ev['tier'] == 'critical' and ev['alert_id'] == 42
    assert ev['titles'] == ['某公司被立案调查'] and ev['words'] == ['立案']


def test_soft_does_not_create_todo():
    svc = FakeTodoService()
    out = _bridge(svc).dispatch([_alert(tier='soft')])

    assert out['created'] == []
    assert svc.creates == []
    assert out['skipped'] and 'critical' in out['skipped'][0]['reason']


def test_open_news_todo_dedupes_same_symbol():
    svc = FakeTodoService()
    repo = FakeTodoRepo([SimpleNamespace(symbol='600519', action_kind='rule_change',
                                         terminal=None)])
    out = _bridge(svc, repo).dispatch([_alert(), _alert(alert_id=43)])

    assert out['created'] == []
    assert svc.creates == []


def test_finished_todo_does_not_block_new_one():
    svc = FakeTodoService()
    repo = FakeTodoRepo([SimpleNamespace(symbol='600519', action_kind='rule_change',
                                         terminal='handled')])
    _bridge(svc, repo).dispatch([_alert()])
    assert len(svc.creates) == 1


def test_missing_symbol_is_skipped_not_guessed():
    svc = FakeTodoService()
    out = _bridge(svc).dispatch([_alert(symbol='')])
    assert svc.creates == [] and out['skipped']


def test_single_failure_does_not_raise():
    svc = FakeTodoService(boom_on='600519.SH')
    out = _bridge(svc).dispatch([_alert(), _alert(symbol='000001.SZ')])

    assert out['errors'] and out['errors'][0]['symbol'] == '600519.SH'
    assert len(out['created']) == 1  # 另一条照常建
