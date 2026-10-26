"""计划状态机与 spec 校验单元测试（t3 验收，纯逻辑不连库）"""
import pytest

from qs_plan.domain.plan import (
    STATUS_ACTIVE, STATUS_ARCHIVED, STATUS_CLOSED, STATUS_CLOSING, STATUS_DRAFT,
    STATUS_HOLDING, STATUS_PAUSED, evaluate_plan_transition, is_legal_transition,
    next_close_status, validate_plan_spec,
)

LEGAL_EDGES = [
    (STATUS_DRAFT, STATUS_ACTIVE),
    (STATUS_ACTIVE, STATUS_HOLDING),
    (STATUS_ACTIVE, STATUS_PAUSED),
    (STATUS_ACTIVE, STATUS_CLOSED),
    (STATUS_HOLDING, STATUS_CLOSING),
    (STATUS_HOLDING, STATUS_PAUSED),
    (STATUS_CLOSING, STATUS_CLOSED),
    (STATUS_CLOSING, STATUS_HOLDING),
    (STATUS_CLOSED, STATUS_ARCHIVED),
    (STATUS_PAUSED, STATUS_ACTIVE),
    (STATUS_PAUSED, STATUS_CLOSED),
]


class TestStateMachine:
    @pytest.mark.parametrize('frm,to', LEGAL_EDGES)
    def test_legal_edges_pass(self, frm, to):
        ok, reason = evaluate_plan_transition(frm, to)
        assert ok is True and reason is None
        assert is_legal_transition(frm, to)

    @pytest.mark.parametrize('frm,to', [
        (STATUS_DRAFT, STATUS_CLOSED),      # 草稿不能直接关
        (STATUS_DRAFT, STATUS_HOLDING),     # 未激活不能持仓
        (STATUS_CLOSED, STATUS_ACTIVE),     # 关闭不能重新激活
        (STATUS_ARCHIVED, STATUS_ACTIVE),   # 归档终态
        (STATUS_HOLDING, STATUS_CLOSED),    # 持仓必须经 closing
        (STATUS_ACTIVE, STATUS_ARCHIVED),   # 未关闭不能归档
    ])
    def test_illegal_edges_rejected_with_reason(self, frm, to):
        ok, reason = evaluate_plan_transition(frm, to)
        assert ok is False
        assert reason and isinstance(reason, str)

    def test_same_status_rejected(self):
        ok, reason = evaluate_plan_transition(STATUS_ACTIVE, STATUS_ACTIVE)
        assert ok is False and '状态未变化' in reason

    def test_close_with_position_requires_disposition(self):
        ok, reason = evaluate_plan_transition(
            STATUS_HOLDING, STATUS_CLOSING, has_position=True)
        assert ok is False and '处置方案' in reason
        ok, _ = evaluate_plan_transition(
            STATUS_HOLDING, STATUS_CLOSING, has_position=True, has_close_disposition=True)
        assert ok is True

    def test_archive_blocked_when_reflection_overdue(self):
        ok, reason = evaluate_plan_transition(
            STATUS_CLOSED, STATUS_ARCHIVED, review_overdue=3)
        assert ok is False and '反思' in reason

    def test_next_close_status(self):
        assert next_close_status(False) == STATUS_CLOSED
        assert next_close_status(True) == STATUS_CLOSING


BASE_SPEC = {
    'targets': [{'symbol': '600519.SH', 'budget_pct': 5, 'role': 'core'}],
    'entry': {'conditions': [{'type': 'price_break', 'params': {'price': 10}}],
              'combinator': 'all_of'},
    'exit': {'stop_loss': {'type': 'pct', 'value': 8}},
    'monitoring': {'news': True},
    'schedule': {'interval_sec': 30},
}


class TestSpecValidation:
    def test_valid_spec_passes(self):
        assert validate_plan_spec(BASE_SPEC) == []

    def test_missing_sections(self):
        problems = validate_plan_spec({})
        assert len(problems) == 5
        assert all('缺少必填段' in p for p in problems)

    def test_exit_requires_stop_or_reduce(self):
        import copy
        spec = copy.deepcopy(BASE_SPEC)
        spec['exit'] = {'invalidation': 'x'}
        assert any('stop_loss 或 reduce_plan' in p for p in validate_plan_spec(spec))

    def test_reduce_plan_ratio_bounds(self):
        import copy
        spec = copy.deepcopy(BASE_SPEC)
        spec['exit'] = {'reduce_plan': [{'at_pct': 8, 'sell_ratio': 1.5}]}
        assert any('sell_ratio' in p for p in validate_plan_spec(spec))

    def test_interval_must_be_positive_int(self):
        import copy
        spec = copy.deepcopy(BASE_SPEC)
        spec['schedule'] = {'interval_sec': 0}
        assert any('interval_sec' in p for p in validate_plan_spec(spec))

    def test_pending_entry_allows_empty_conditions(self):
        import copy
        spec = copy.deepcopy(BASE_SPEC)
        spec['entry'] = {'conditions': [], 'combinator': 'all_of', 'pending': True}
        assert validate_plan_spec(spec) == []

    def test_pending_entry_rejects_non_empty_conditions(self):
        import copy
        spec = copy.deepcopy(BASE_SPEC)
        spec['entry'] = {'conditions': [{'type': 'price_break'}], 'pending': True}
        assert any('pending=true 时' in p for p in validate_plan_spec(spec))

    def test_combinator_enum(self):
        import copy
        spec = copy.deepcopy(BASE_SPEC)
        spec['entry']['combinator'] = 'xor'
        assert any('combinator' in p for p in validate_plan_spec(spec))
