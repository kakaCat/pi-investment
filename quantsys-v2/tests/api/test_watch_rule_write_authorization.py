"""普通规则 CRUD/batch 的授权、审计与故障补偿（全内存，不写业务库）。"""
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes import watch_async
from qs_watch.application.services.watch_engine.watch_rule_write_service import (
    WatchRuleWriteService,
)

CONDITIONS = [{'type': 'price_break', 'params': {'direction': 'above', 'price': 10.0}}]
AGENT = {'reason': '按已审批方案调整规则', 'decision_audit_id': 'DA-write-1'}
USER = {'reason': '用户本人确认调整规则', 'operator': 'user'}


def make_rule(rule_id, account='agent_brain', *, intent='trend_observe', context='old'):
    now = datetime(2026, 11, 18, 19, 0, 0)
    return SimpleNamespace(
        id=rule_id, symbol=f'{rule_id:06d}.SZ', enabled=True,
        conditions=deepcopy(CONDITIONS), context=context, cost_price=None,
        active_window=None, expires_at=None, created_by='agent', account=account,
        linked_account=account, notify_mode=None, action_hint={}, escalation_policy={},
        created_at=now, updated_at=now, intent=intent, lifecycle_stage='tracking',
        scope='symbol', target=None, created_from=None, next_action_hint=None,
        action_params={}, ops_notes=[], position_state='none', interval_sec=None,
        watch_tier=30, plan_id=None, rule_state='active', invalid_reason=None,
        invalid_at=None, confirm_count=0, invalidation_threshold_pct=20.0,
        invalid_escalated_at=None, last_reviewed_at=None, review_interval_days=None,
        review_due_at=None,
    )


class FakeRuleRepo:
    def __init__(self, rules):
        self.rows = {row.id: row for row in rules}
        self.update_calls = 0
        self.fail_update_calls = set()

    def get_by_id(self, rule_id):
        return self.rows.get(int(rule_id))

    def list_rules(self, symbol=None, enabled=None, account=None, rule_state=None):
        rows = list(self.rows.values())
        if symbol is not None:
            rows = [row for row in rows if row.symbol == symbol]
        if enabled is not None:
            rows = [row for row in rows if row.enabled is enabled]
        if rule_state is not None:
            rows = [row for row in rows if row.rule_state == rule_state]
        return rows

    def create_rule(self, **fields):
        rule_id = max(self.rows, default=0) + 1
        template = make_rule(rule_id, fields.get('linked_account') or fields.get('account'),
                             intent=fields.get('intent') or 'trend_observe')
        for key, value in fields.items():
            setattr(template, key, value)
        template.context = fields.get('context') or 'new'
        self.rows[rule_id] = template
        return template

    def update_fields(self, rule_id, **fields):
        self.update_calls += 1
        if self.update_calls in self.fail_update_calls:
            raise RuntimeError(f'injected update failure #{self.update_calls}')
        rule = self.rows[int(rule_id)]
        for key, value in fields.items():
            setattr(rule, key, value)
        return rule

    def delete_by_id(self, rule_id):
        return self.rows.pop(int(rule_id), None) is not None


class FakeChangeRepo:
    def __init__(self):
        self.rows = []
        self.calls = 0
        self.fail_calls = set()

    def record(self, rule_id, changed_by, change_kind, before=None, after=None,
               reason=None, trigger_id=None, todo_id=None, decision_audit_id=None):
        self.calls += 1
        if self.calls in self.fail_calls:
            raise RuntimeError(f'injected audit failure #{self.calls}')
        row = SimpleNamespace(
            id=self.calls, rule_id=rule_id, changed_by=changed_by,
            change_kind=change_kind, before=deepcopy(before), after=deepcopy(after),
            reason=reason, trigger_id=trigger_id, todo_id=todo_id,
            decision_audit_id=decision_audit_id,
            created_at=datetime(2026, 11, 18, 19, 1, 0),
        )
        self.rows.append(row)
        return row


@pytest.fixture
def env(monkeypatch):
    rules = FakeRuleRepo([
        make_rule(1, 'agent_brain', context='own-old'),
        make_rule(2, 'user_main_simulation', context='user-old'),
        make_rule(3, None, context='global-old'),
        make_rule(4, 'agent_brain', context='second-old'),
    ])
    changes = FakeChangeRepo()
    service = WatchRuleWriteService(rules, changes)
    monkeypatch.setattr(watch_async, '_write_service', lambda: service)
    monkeypatch.setattr(watch_async, 'WatchRuleRepository', lambda: rules)
    app = FastAPI()
    app.include_router(watch_async.router)
    return SimpleNamespace(client=TestClient(app), rules=rules, changes=changes)


def test_agent_cannot_patch_user_account(env):
    resp = env.client.patch('/api/watch/rules/2', json={**AGENT, 'context': 'hijack'})
    assert resp.status_code == 403
    assert resp.json()['error'] == 'watch_rule_change_unauthorized'
    assert env.rules.rows[2].context == 'user-old'
    assert env.changes.rows == []


def test_agent_cannot_bypass_by_reassigning_rule_to_user_account(env):
    resp = env.client.patch('/api/watch/rules/1', json={
        **AGENT, 'account': 'user_main_simulation', 'linked_account': 'user_main_simulation'})
    assert resp.status_code == 403
    assert env.rules.rows[1].account == 'agent_brain'
    assert env.changes.rows == []


def test_agent_write_requires_decision_audit(env):
    resp = env.client.patch('/api/watch/rules/1', json={
        'reason': '缺审计号', 'context': 'must-not-write'})
    assert resp.status_code == 400
    assert resp.json()['error'] == 'watch_rule_change_missing_audit'
    assert env.rules.rows[1].context == 'own-old'
    assert env.changes.rows == []


def test_user_requires_reason_but_not_decision_audit(env):
    missing = env.client.patch('/api/watch/rules/2', json={
        'operator': 'user', 'context': 'must-not-write'})
    assert missing.status_code == 400
    assert missing.json()['error'] == 'watch_rule_change_missing_reason'

    resp = env.client.patch('/api/watch/rules/2', json={**USER, 'context': 'user-new'})
    assert resp.status_code == 200, resp.text
    change = env.changes.rows[-1]
    assert change.changed_by == 'user'
    assert change.decision_audit_id is None
    assert change.before == {'context': 'user-old'}
    assert change.after == {'context': 'user-new'}


def test_accountless_observation_create_allowed_with_audit_and_lineage(env):
    resp = env.client.post('/api/watch/rules', json={
        **AGENT, 'symbol': '000005.SZ', 'conditions': CONDITIONS,
        'intent': 'trend_observe', 'source_trigger_id': 71, 'todo_id': 8,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()['data']
    assert body['rule']['account'] is None
    change = env.changes.rows[-1]
    assert change.change_kind == 'create'
    assert change.before is None
    assert change.after['id'] == body['rule']['id']
    assert (change.trigger_id, change.todo_id, change.decision_audit_id) == (71, 8, 'DA-write-1')


def test_accountless_entry_create_rejected_even_for_user(env):
    before = set(env.rules.rows)
    resp = env.client.post('/api/watch/rules', json={
        **USER, 'symbol': '000006.SZ', 'conditions': CONDITIONS, 'intent': 'entry'})
    assert resp.status_code == 400
    assert set(env.rules.rows) == before
    assert env.changes.rows == []


def test_patch_audit_uses_persisted_before_after_and_lineage(env):
    resp = env.client.patch('/api/watch/rules/1', json={
        **AGENT, 'context': 'own-new', 'source_trigger_id': 72, 'todo_id': 9})
    assert resp.status_code == 200, resp.text
    change = env.changes.rows[-1]
    assert change.before == {'context': 'own-old'}
    assert change.after == {'context': 'own-new'}
    assert (change.trigger_id, change.todo_id) == (72, 9)
    assert resp.json()['data']['change']['after'] == {'context': 'own-new'}


def test_delete_is_soft_archive_and_preserves_rule(env):
    resp = env.client.request('DELETE', '/api/watch/rules/1', json=AGENT)
    assert resp.status_code == 200, resp.text
    rule = env.rules.rows[1]
    assert rule.enabled is False
    assert rule.rule_state == 'archived'
    change = env.changes.rows[-1]
    assert change.change_kind == 'retire'
    assert change.before['enabled'] is True
    assert change.after['enabled'] is False
    assert change.after['rule_state'] == 'archived'


def test_audit_failure_restores_single_update_and_returns_500(env):
    env.changes.fail_calls = {1}
    resp = env.client.patch('/api/watch/rules/1', json={**AGENT, 'context': 'temporary'})
    assert resp.status_code == 500
    assert resp.json()['success'] is False
    assert resp.json()['rolled_back'] is True
    assert resp.json()['rollback_errors'] == []
    assert env.rules.rows[1].context == 'own-old'
    assert env.changes.rows == []


def test_audit_failure_removes_unaudited_create(env):
    env.changes.fail_calls = {1}
    before = set(env.rules.rows)
    resp = env.client.post('/api/watch/rules', json={
        **AGENT, 'symbol': '000007.SZ', 'conditions': CONDITIONS, 'intent': 'trend_observe'})
    assert resp.status_code == 500
    assert resp.json()['success'] is False
    assert set(env.rules.rows) == before
    assert env.changes.rows == []


def test_batch_current_action_rollback_failure_is_visible(env):
    # 唯一动作：update#1 写值，audit#1 失败，update#2 自补偿也失败。
    env.rules.fail_update_calls = {2}
    env.changes.fail_calls = {1}
    resp = env.client.post('/api/watch/rules/batch', json={
        **AGENT, 'source_trigger_id': 87,
        'actions': [{'op': 'update', 'rule_id': 1, 'context': 'uncompensated'}],
    })
    assert resp.status_code == 500
    data = resp.json()['data']
    assert data['rollback_attempted'] is True
    assert data['rolled_back'] is False
    assert data['rollback_errors']
    assert env.rules.rows[1].context == 'uncompensated'


def test_batch_second_audit_failure_rolls_back_first_and_is_visible(env):
    env.changes.fail_calls = {2}
    resp = env.client.post('/api/watch/rules/batch', json={
        **AGENT, 'source_trigger_id': 88,
        'actions': [
            {'op': 'update', 'rule_id': 1, 'context': 'batch-new-1'},
            {'op': 'update', 'rule_id': 4, 'context': 'batch-new-4'},
        ],
    })
    assert resp.status_code == 500, resp.text
    body = resp.json()
    assert body['success'] is False
    assert body['data']['rolled_back'] is True
    assert body['data']['rollback_errors'] == []
    assert body['data']['ok'] == 0
    assert body['data']['results'][0]['rolled_back'] is True
    assert env.rules.rows[1].context == 'own-old'
    assert env.rules.rows[4].context == 'second-old'
    # 第一笔原审计保留 append-only 历史，第二笔失败无审计，第三笔是第一笔补偿审计。
    assert len(env.changes.rows) == 2
    assert env.changes.rows[-1].change_kind == 'update'
    assert '补偿' in env.changes.rows[-1].reason


def test_batch_rollback_failure_is_not_disguised(env):
    # update#1=第一笔，#2=第二笔，#3=第二笔审计失败后的自恢复，#4=第一笔反向补偿（故障）。
    env.rules.fail_update_calls = {4}
    env.changes.fail_calls = {2}
    resp = env.client.post('/api/watch/rules/batch', json={
        **AGENT, 'source_trigger_id': 89,
        'actions': [
            {'op': 'update', 'rule_id': 1, 'context': 'left-after-rollback-failure'},
            {'op': 'update', 'rule_id': 4, 'context': 'batch-new-4'},
        ],
    })
    assert resp.status_code == 500
    body = resp.json()
    assert body['success'] is False
    assert body['data']['rolled_back'] is False
    assert body['data']['rollback_errors']
    assert body['data']['results'][0]['rollback_failed'] is True
    assert env.rules.rows[1].context == 'left-after-rollback-failure'
    assert env.rules.rows[4].context == 'second-old'


def test_batch_success_writes_audits_and_soft_retire(env):
    resp = env.client.post('/api/watch/rules/batch', json={
        **AGENT, 'source_trigger_id': 90,
        'actions': [
            {'op': 'update', 'rule_id': 1, 'context': 'batch-ok'},
            {'op': 'retire', 'rule_id': 4, 'retire_note': '测试收摊'},
        ],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()['success'] is True
    assert resp.json()['data']['failed'] == 0
    assert env.rules.rows[4].enabled is False
    assert env.rules.rows[4].rule_state == 'archived'
    assert [row.change_kind for row in env.changes.rows] == ['update', 'retire']
    assert all(row.trigger_id == 90 for row in env.changes.rows)
