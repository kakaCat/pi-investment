"""WatchTodoRepository 集成测试（使用 quant_test 库）

覆盖 2026-10-19 的两处行为变更：
  · close_open_by_rule —— 规则停用/删除时级联归档未收敛待办（静默、补审计标记、
    不动已终态行）；
  · list_overdue —— 联动过滤：所挂规则已停用/已删除的待办不命中（防御兜底）。
"""
import pytest
from datetime import datetime, timedelta, timezone

from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
from adapters.outbound.repositories.watch_todo_repository import (
    CASCADE_AUDIT_MARKER,
    WatchTodoRepository,
)

_PAST = datetime.now(timezone.utc) - timedelta(hours=1)


@pytest.mark.integration
class TestWatchTodoCascadeAndOverdueFilter:
    def setup_method(self):
        self.rule_repo = WatchRuleRepository()
        self.todo_repo = WatchTodoRepository()
        self._rule_ids = []
        self._todo_ids = []

    def teardown_method(self):
        for tid in self._todo_ids:
            self.todo_repo.delete_by_id(tid)
        for rid in self._rule_ids:
            self.rule_repo.delete_by_id(rid)

    def _make_rule(self, symbol='600519.SH'):
        rule = self.rule_repo.create_rule(
            symbol=symbol,
            conditions=[{'type': 'price_break',
                         'params': {'direction': 'above', 'price': 1800.0}}],
            context='级联测试规则', created_by='test')
        self._rule_ids.append(rule.id)
        return rule

    def _make_todo(self, rule_id=None, symbol='600519.SH', action_kind=None,
                   due_at=_PAST):
        todo = self.todo_repo.create(
            symbol, rule_id=rule_id, level='P2', flow_state='L1',
            owner_kind='agent', owner_ref='agent-test', autonomy='remind_only',
            sla_seconds=1800, due_at=due_at, action_kind=action_kind)
        self._todo_ids.append(todo.id)
        return todo

    # ── close_open_by_rule ─────────────────────────────────

    def test_cascade_closes_open_todos_and_marks_audit(self):
        rule = self._make_rule()
        t_plain = self._make_todo(rule.id)
        t_repair = self._make_todo(rule.id, action_kind='rule_change')

        archived = self.todo_repo.close_open_by_rule(rule.id)

        assert archived == 2
        plain = self.todo_repo.get(t_plain.id)
        repair = self.todo_repo.get(t_repair.id)
        assert plain.terminal == 'expired'
        assert plain.closed_at is not None
        assert '无需处理' in (plain.close_reason or '')
        # 无动作类别的待办不补审计标记
        assert plain.decision_audit_id is None
        # action_kind=rule_change 必须带审计号（CHECK）→ 级联补系统标记
        assert repair.terminal == 'expired'
        assert repair.decision_audit_id == CASCADE_AUDIT_MARKER

    def test_cascade_leaves_closed_and_other_rules_todos_alone(self):
        rule = self._make_rule()
        other = self._make_rule('000001.SZ')
        t_closed = self._make_todo(rule.id)
        self.todo_repo.close(t_closed.id, 'handled', close_reason='已人工处置')
        t_other = self._make_todo(other.id, symbol='000001.SZ')

        archived = self.todo_repo.close_open_by_rule(rule.id)

        assert archived == 0
        assert self.todo_repo.get(t_closed.id).terminal == 'handled'
        assert self.todo_repo.get(t_other.id).terminal is None

    # ── list_overdue 联动过滤 ──────────────────────────────

    def test_overdue_excludes_todos_on_disabled_rule(self):
        rule = self._make_rule()
        t_live = self._make_todo(rule.id)
        dead_rule = self._make_rule('000002.SZ')
        t_dead = self._make_todo(dead_rule.id, symbol='000002.SZ')
        self.rule_repo.update_fields(dead_rule.id, enabled=False)
        # 注：update_fields 的停用级联会把 t_dead 归档——为单独验证 list_overdue
        # 的兜底过滤，这里把它重开成未收敛（模拟级联缺位时的漏网死工单）。
        self._reopen(t_dead.id)

        ids = {t.id for t in self.todo_repo.list_overdue(limit=500)}

        assert t_live.id in ids
        assert t_dead.id not in ids

    def test_overdue_excludes_orphan_and_keeps_rule_less_todos(self):
        rule = self._make_rule()
        t_orphan = self._make_todo(rule.id)
        t_free = self._make_todo(None, symbol='000003.SZ')
        self.rule_repo.delete_by_id(rule.id)  # 硬删 → t_orphan 成孤儿

        ids = {t.id for t in self.todo_repo.list_overdue(limit=500)}

        assert t_orphan.id not in ids
        assert t_free.id in ids  # 不挂规则的待办照常可见

    # ── update_fields 停用级联（收口在规则仓储）─────────────

    def test_disable_rule_cascades_close(self):
        rule = self._make_rule()
        todo = self._make_todo(rule.id)

        self.rule_repo.update_fields(rule.id, enabled=False)

        closed = self.todo_repo.get(todo.id)
        assert closed.terminal == 'expired'
        assert closed.closed_at is not None

    def test_non_disable_update_does_not_cascade(self):
        rule = self._make_rule()
        todo = self._make_todo(rule.id)

        self.rule_repo.update_fields(rule.id, context='只改文案')

        assert self.todo_repo.get(todo.id).terminal is None

    def test_repeated_disable_does_not_double_close(self):
        rule = self._make_rule()
        todo = self._make_todo(rule.id)
        self.rule_repo.update_fields(rule.id, enabled=False)
        first_closed_at = self.todo_repo.get(todo.id).closed_at

        # 幂等重复停用（已是 False → 无跳变）不得二次改写终态行
        self.rule_repo.update_fields(rule.id, enabled=False, context='补充注记')

        after = self.todo_repo.get(todo.id)
        assert after.terminal == 'expired'
        assert after.closed_at == first_closed_at

    # ── 工具 ───────────────────────────────────────────────

    def _reopen(self, todo_id):
        """把待办重开成未收敛（仅测试用：绕过应用层纪律，直写库模拟漏网死工单）"""
        from sqlalchemy import update as sa_update
        from infrastructure.persistence.orm.models.watch_todo import WatchTodo
        session = self.todo_repo.session
        session.execute(
            sa_update(WatchTodo)
            .where(WatchTodo.id == todo_id)
            .values(terminal=None, closed_at=None, close_reason=None,
                    decision_audit_id=None)
            .execution_options(synchronize_session=False))
        session.commit()
