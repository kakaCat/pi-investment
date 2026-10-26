"""「不执行 → 改规则」联动接线（REQ-261021194640-69b8 FR-5，卡 t-e95a2a）

验收判据三条：
  1. `ignored + rule_change` → 规则字段真变化 + 一条带 trigger_id 的审计；
  2. 联动失败时**待办保持未收敛**（不留「待办已关、规则没改」的半成品）；
  3. 重复 close → `WatchTodoAlreadyClosed`（409 语义）。

全部用例用假件跑真实 `TodoService` / `RuleChangeLinkage` 代码（不碰 DB）。
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.disposition_engine import (
    RuleChangeLinkage,
)
from qs_watch.application.services.watch_engine.todo_service import TodoService
from qs_watch.domain.watch.ports import (
    WatchTodoAlreadyClosed,
    WatchTodoRuleChangeFailed,
)

NOW = datetime(2026, 10, 21, 10, 30)


class FakeTodoRepo:
    def __init__(self, todo):
        self.todo = todo
        self.close_calls = 0
        self.closed_args = []

    def get(self, todo_id):
        if self.todo is None or self.todo.id != todo_id:
            return None
        return self.todo

    def close(self, todo_id, terminal, **kwargs):
        self.close_calls += 1
        self.closed_args.append({'todo_id': todo_id, 'terminal': terminal, **kwargs})
        if self.todo.terminal:
            return None
        self.todo.terminal = terminal
        self.todo.closed_at = NOW
        return self.todo


class FakeRuleRepo:
    def __init__(self, rule):
        self.rule = rule
        self.updates = []

    def get_by_id(self, rule_id):
        if self.rule is None or self.rule.id != rule_id:
            return None
        return self.rule

    def update_fields(self, rule_id, **fields):
        self.updates.append(dict(fields, rule_id=rule_id))
        for key, value in fields.items():
            setattr(self.rule, key, value)
        return self.rule


class FakeChangeRepo:
    def __init__(self):
        self.records = []

    def record(self, rule_id, **kwargs):
        self.records.append(dict(kwargs, rule_id=rule_id))
        return SimpleNamespace(id=len(self.records), rule_id=rule_id, **kwargs)


def _todo(**overrides):
    base = dict(id=7, symbol='600519.SH', rule_id=11, trigger_id=99,
                level='P1', flow_state='L3', terminal=None, closed_at=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def _rule(**overrides):
    base = dict(id=11, symbol='600519.SH', enabled=True, intent='exit_stop',
                lifecycle_stage='holding', expires_at=None, action_hint={},
                conditions=[{'type': 'price_break',
                             'params': {'price': 100.0, 'direction': 'below'}}])
    base.update(overrides)
    return SimpleNamespace(**base)


def _linkage(rule):
    rule_repo, change_repo = FakeRuleRepo(rule), FakeChangeRepo()
    return RuleChangeLinkage(rule_repo, change_repo, now_fn=lambda: NOW), rule_repo, change_repo


def test_ignored_with_rule_change_updates_rule_and_writes_audit():
    rule = _rule()
    linkage, rule_repo, change_repo = _linkage(rule)
    todo = _todo()
    svc = TodoService(FakeTodoRepo(todo), rule_change_linkage=linkage)

    closed = svc.close(
        7, 'ignored', next_condition='跌破 90 且缩量再看',
        close_reason='噪音带内，暂不执行', action_kind='rule_change',
        decision_audit_id='DEC-1', closed_by='agent',
        rule_change={'change_kind': 'adjust_threshold',
                     'params': {'price': 95.5}, 'reason': '把线调出噪音带'})

    assert rule.conditions[0]['params']['price'] == 95.5, '规则字段必须真变化'
    assert len(rule_repo.updates) == 1
    assert len(change_repo.records) == 1, '必须写一条规则变更审计'
    audit = change_repo.records[0]
    assert audit['trigger_id'] == 99, '审计必须带触发溯源'
    assert audit['todo_id'] == 7 and audit['rule_id'] == 11
    assert audit['change_kind'] == 'threshold'
    assert closed.terminal == 'ignored'
    assert closed.rule_change_summary['change_kind'] == 'adjust_threshold'
    assert closed.rule_change_summary['applied'] is True


def test_ignored_without_rule_change_keeps_old_behavior():
    rule = _rule()
    linkage, _rule_repo, change_repo = _linkage(rule)
    todo = _todo()
    svc = TodoService(FakeTodoRepo(todo), rule_change_linkage=linkage)

    closed = svc.close(7, 'ignored', next_condition='下次再说')

    assert closed.terminal == 'ignored'
    assert change_repo.records == [], '不传结构化动作时不得写审计'
    assert not hasattr(closed, 'rule_change_summary')


def test_rule_change_only_applies_to_ignored():
    rule = _rule()
    linkage, _rule_repo, _change_repo = _linkage(rule)
    repo = FakeTodoRepo(_todo())
    svc = TodoService(repo, rule_change_linkage=linkage)

    with pytest.raises(WatchTodoRuleChangeFailed):
        svc.close(7, 'handled', action_kind='trade', decision_audit_id='DEC-2',
                  rule_change={'change_kind': 'disable', 'reason': 'x'})

    assert repo.close_calls == 0, '被拒时不得收敛待办'


def test_linkage_failure_leaves_todo_open():
    rule = _rule()
    linkage, _rule_repo, change_repo = _linkage(rule)
    repo = FakeTodoRepo(_todo())
    svc = TodoService(repo, rule_change_linkage=linkage)

    # 调阈值缺 params.price → 联动抛错（真实链路校验）
    with pytest.raises(WatchTodoRuleChangeFailed):
        svc.close(7, 'ignored', next_condition='再看', action_kind='rule_change',
                  decision_audit_id='DEC-3',
                  rule_change={'change_kind': 'adjust_threshold', 'reason': '缺目标值'})

    assert repo.close_calls == 0, '联动失败时待办必须保持未收敛'
    assert change_repo.records == [], '失败时不得留半条审计'
    assert repo.todo.terminal is None


def test_missing_trigger_trace_rejected():
    rule = _rule()
    linkage, _rule_repo, _change_repo = _linkage(rule)
    repo = FakeTodoRepo(_todo(trigger_id=None))
    svc = TodoService(repo, rule_change_linkage=linkage)

    with pytest.raises(WatchTodoRuleChangeFailed):
        svc.close(7, 'ignored', next_condition='再看', action_kind='rule_change',
                  decision_audit_id='DEC-4',
                  rule_change={'change_kind': 'disable', 'reason': '不再需要'})
    assert repo.close_calls == 0


def test_missing_linkage_rejected_not_silently_dropped():
    repo = FakeTodoRepo(_todo())
    svc = TodoService(repo)  # 未注入联动

    with pytest.raises(WatchTodoRuleChangeFailed):
        svc.close(7, 'ignored', next_condition='再看', action_kind='rule_change',
                  decision_audit_id='DEC-5',
                  rule_change={'change_kind': 'disable', 'reason': 'x'})
    assert repo.close_calls == 0


def test_missing_reason_rejected():
    rule = _rule()
    linkage, _rule_repo, _change_repo = _linkage(rule)
    repo = FakeTodoRepo(_todo())
    svc = TodoService(repo, rule_change_linkage=linkage)

    with pytest.raises(WatchTodoRuleChangeFailed):
        svc.close(7, 'ignored', next_condition='再看', action_kind='rule_change',
                  decision_audit_id='DEC-6',
                  rule_change={'change_kind': 'disable'})
    assert repo.close_calls == 0


def test_repeated_close_is_rejected():
    rule = _rule()
    linkage, _rule_repo, _change_repo = _linkage(rule)
    todo = _todo()
    svc = TodoService(FakeTodoRepo(todo), rule_change_linkage=linkage)

    svc.close(7, 'ignored', next_condition='再看')
    with pytest.raises(WatchTodoAlreadyClosed):
        svc.close(7, 'ignored', next_condition='再看')
