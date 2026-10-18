"""digest 积压可见（REQ-261016155500-4f2a wt:engine:4，2026-10-16）

验收锚点：有积压时 payload.backlog 计数正确、文本含积压行、最旧时间透出；
无积压时行为与现状一致（无积压行、count=0）。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.digest_service import WatchDigestService

NOW = datetime(2026, 10, 16, 10, 0, 0)
SINCE = NOW - timedelta(minutes=25)


def _trigger(tid, rid, at, disposition='pending'):
    return SimpleNamespace(
        id=tid, rule_id=rid, symbol='002007', condition={'type': 'price_break'},
        trigger_price=12.3, triggered_at=at, disposition=disposition,
        disposition_reason=None, todo_id=None)


def _rule(rid, account='agent_brain'):
    return SimpleNamespace(
        id=rid, symbol='002007', linked_account=account, action_hint={},
        context='预案', intent=None, scope=None, lifecycle_stage=None,
        next_action_hint=None)


class _TriggerRepo:
    """内存触发仓储：list_triggers + count_older_unresolved（新端口方法）。"""

    def __init__(self, rows, backlog):
        self._rows = rows
        self._backlog = backlog          # {'count': N, 'oldest_at': dt|None}
        self.counter_calls = []

    def list_triggers(self, dispositions=None, limit=200):
        return list(self._rows)

    def count_older_unresolved(self, since, dispositions):
        self.counter_calls.append((since, dispositions))
        return self._backlog


class _RuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_rules(self):
        return list(self._rules)


def _svc(rows, backlog):
    return WatchDigestService(trigger_repo=_TriggerRepo(rows, backlog),
                              rule_repo=_RuleRepo([_rule(1)]))


def test_backlog_counted_and_surfaced_in_text():
    new_row = _trigger(2, 1, SINCE + timedelta(minutes=1))     # 增量段内
    svc = _svc([new_row], {'count': 7, 'oldest_at': NOW - timedelta(days=3)})
    digest = svc.build_digest(since=SINCE)

    assert digest['backlog']['count'] == 7
    assert digest['backlog']['oldest_at'] == (NOW - timedelta(days=3)).isoformat()
    assert '⚠️ 积压：另有 7 条' in digest['text']
    assert '未入本摘要' in digest['text']
    # 增量段本身不受影响
    assert digest['count'] == 1
    assert '002007' in digest['text']


def test_no_backlog_keeps_current_behavior():
    svc = _svc([_trigger(2, 1, SINCE + timedelta(minutes=1))],
               {'count': 0, 'oldest_at': None})
    digest = svc.build_digest(since=SINCE)
    assert digest['backlog'] == {'count': 0, 'oldest_at': None}
    assert '积压' not in digest['text']


def test_counter_not_called_without_since():
    repo = _TriggerRepo([_trigger(2, 1, NOW)], {'count': 5, 'oldest_at': NOW})
    svc = WatchDigestService(trigger_repo=repo, rule_repo=_RuleRepo([_rule(1)]))
    digest = svc.build_digest()                       # 无 since = 全量口径，无积压概念
    assert digest['backlog']['count'] == 0
    assert repo.counter_calls == []


def test_counter_failure_does_not_break_digest():
    class _BoomRepo(_TriggerRepo):
        def count_older_unresolved(self, since, dispositions):
            raise RuntimeError('db down')

    svc = WatchDigestService(trigger_repo=_BoomRepo(
        [_trigger(2, 1, SINCE + timedelta(minutes=1))], {}),
        rule_repo=_RuleRepo([_rule(1)]))
    digest = svc.build_digest(since=SINCE)            # 降级：摘要照出，积压记 0
    assert digest['count'] == 1
    assert digest['backlog']['count'] == 0
