"""缺指引 lint 与补全幂等（REQ-261016155500-4f2a，2026-10-16）

- rule_lint.is_missing_guidance：四要素判定的纯函数用例（含 action_hint 为 JSON 字符串）。
- GuidanceBackfillService.ensure_todos：内存 fake 验证幂等（第二次调用全部 skipped）。
- list_open_by_rule 端口语义：FakeTodoRepo 已随 test_todo_service 的签名比对覆盖。
"""
from datetime import datetime
from types import SimpleNamespace

from domain.watch.services.rule_lint import guidance_state, is_missing_guidance
from application.services.watch_engine.guidance_backfill_service import (
    GuidanceBackfillService,
)


def _rule(**over):
    base = dict(enabled=True, action_params=None, next_action_hint=None,
                intent=None, action_hint={})
    base.update(over)
    return SimpleNamespace(**base)


# ── 纯函数判定 ──────────────────────────────────────────────

def test_all_empty_is_missing():
    assert is_missing_guidance(_rule()) is True


def test_any_element_disqualifies():
    assert not is_missing_guidance(_rule(action_params={'action': 'sell'}))
    assert not is_missing_guidance(_rule(next_action_hint='跌破 41 评估建仓'))
    assert not is_missing_guidance(_rule(intent='entry'))
    assert not is_missing_guidance(_rule(action_hint={'action_on_trigger': 'sell'}))


def test_disabled_rule_not_linted():
    assert is_missing_guidance(_rule(enabled=False)) is False


def test_action_hint_json_string_parsed():
    rule = _rule(action_hint='{"action_on_trigger": "buy"}')
    assert is_missing_guidance(rule) is False


def test_empty_action_params_dict_counts_as_missing():
    assert is_missing_guidance(_rule(action_params={})) is True
    assert is_missing_guidance(_rule(action_params={'action': None})) is True


def test_guidance_state_reports_each_gap():
    st = guidance_state(_rule())
    assert all(st.values())
    st2 = guidance_state(_rule(intent='entry'))
    assert st2['missing_intent'] is False
    assert st2['missing_action_params'] is True


# ── 补全服务幂等 ────────────────────────────────────────────

class _FakeRuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_rules(self, enabled=True):
        return self._rules


class _FakeTodoService:
    """记录 create 调用 + 模拟未收敛补全待办查询（内存）"""

    def __init__(self):
        self.created = []

    def list_open_by_rule(self, rule_id, action_kind=None, trigger_id_null=False):
        return [SimpleNamespace(**t) for t in self.created
                if t['rule_id'] == rule_id and action_kind == 'rule_change']

    def create(self, symbol, *, level, sla_seconds, due_at, account=None,
               rule_id=None, trigger_id=None, action_kind=None):
        todo = {'id': 1000 + len(self.created), 'symbol': symbol, 'rule_id': rule_id,
                'level': level, 'action_kind': action_kind}
        self.created.append(todo)
        return SimpleNamespace(**todo)


def test_ensure_todos_idempotent():
    rules = [_rule(), _rule()]
    rules[0].id, rules[0].symbol, rules[0].account = 1, '600000', 'agent_brain'
    rules[1].id, rules[1].symbol, rules[1].account = 2, '000001', 'agent_brain'
    todo_svc = _FakeTodoService()
    svc = GuidanceBackfillService(rule_repo=_FakeRuleRepo(rules),
                                  todo_service=todo_svc)

    first = svc.ensure_todos(now=datetime(2026, 10, 16, 10, 0, 0))
    assert first['created_count'] == 2
    assert all(t['level'] == 'P2' and t['action_kind'] == 'rule_change'
               for t in todo_svc.created)

    second = svc.ensure_todos(now=datetime(2026, 10, 16, 10, 5, 0))
    assert second['created_count'] == 0
    assert second['skipped_count'] == 2
    assert len(todo_svc.created) == 2  # 没有重复建


def test_ensure_todos_skips_guided_rules():
    guided = _rule(intent='entry')
    guided.id, guided.symbol, guided.account = 9, '600519', 'agent_brain'
    todo_svc = _FakeTodoService()
    svc = GuidanceBackfillService(rule_repo=_FakeRuleRepo([guided]),
                                  todo_service=todo_svc)
    result = svc.ensure_todos(now=datetime(2026, 10, 16, 10, 0, 0))
    assert result['created_count'] == 0
    assert todo_svc.created == []
