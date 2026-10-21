"""处置卡「不执行」→ 改规则联动（卡 `rule-change-linkage`，2026-10-21）验收测试。

卡陈述：处置卡动作项（调阈值/延期/停用/退役）落地为规则更新 + watch_rule_change
带 trigger_id 溯源（含该表加列迁移）。

三条判据逐条对应本文件的分组：

  0. **四动作 × 留痕 × 溯源 × guard 拦截**（`TestActionVocabulary` / 四个动作分组 /
     `TestTraceability` / `TestConstitutionalGuard`）：每个动作既改规则、又写一条
     带 trigger_id 的审计；宪法级止损的停用/退役无理由时**一行都不写**就被拒。
  1. 规则仓储与 rule_guard 既有测试全绿（另一条 pytest 命令，本文件只守新契约）；
  2. **宪法级止损停用必须随附理由**（`TestConstitutionalGuard`）。

可失败性（每条都能被改坏证伪）：
  · 只写审计不改规则 → 各动作的规则状态用例红；
  · 审计不带 trigger_id（或写 0）→ 溯源用例红；
  · 停用/退役绕过 guard → 宪法级用例红；
  · 调阈值只改顶层 price_break → 嵌套 combined / staged_break 用例红；
  · 延期给无到期时间的规则硬塞 expires_at → 用例红；
  · 仓储把 trigger_id=0 当合法值 → 仓储契约用例红。

全部用例用**假件**跑真实应用代码（不碰 DB、不碰引擎），因此任何环境都能红/绿。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from adapters.outbound.repositories.watch_rule_change_repository import (
    WatchRuleChangeRepository, change_to_dict,
)
from qs_watch.application.services.watch_engine.disposition_engine import (
    ACTION_LABELS, CHANGE_KIND_BY_ACTION, DEFAULT_POSTPONE_DAYS, LINKAGE_NOTE_SOURCE,
    RETIRED_LIFECYCLE_STAGE, RuleChangeAction, RuleChangeLinkage, RuleChangeOutcome,
)
from qs_watch.domain.watch.services.rule_guard import (
    DISPOSITION_ACTIONS, DISPOSITION_DISABLING_ACTIONS,
    ConstitutionalRuleSilentDisable, guard_disposition_action,
)

NOW = datetime(2026, 10, 21, 10, 30)      # 固定时钟（不读系统时间，跨时区可复现）

#: 四动作的合法参数（矩阵用例共用；参数缺失/非法在各自分组里单独证伪）
PARAMS_BY_ACTION = {
    RuleChangeAction.ADJUST_THRESHOLD: {'price': 25.5},
    RuleChangeAction.POSTPONE: {'days': 2},
    RuleChangeAction.DISABLE: None,
    RuleChangeAction.RETIRE: None,
}


# ── 假件（只替换仓储出口；规则更新语义与真实仓储一致）──────────────────────
class FakeRuleRepo:
    """IWatchRuleRepository 的写侧：update_fields 真正写回对象并留痕调用参数。"""

    def __init__(self, rule):
        self.rule = rule
        self.updates = []

    def get_by_id(self, rule_id):
        if self.rule is None:
            return None
        current_id = (self.rule.get('id') if isinstance(self.rule, dict)
                      else self.rule.id)
        return self.rule if current_id == rule_id else None

    def update_fields(self, rule_id, **fields):
        self.updates.append(dict(fields, rule_id=rule_id))
        if self.get_by_id(rule_id) is None:
            return None
        if isinstance(self.rule, dict):
            self.rule.update(fields)
        else:
            for key, value in fields.items():
                setattr(self.rule, key, value)
        return self.rule


class FakeChangeRepo:
    """IWatchRuleChangeRepository 的写侧：记录每一次 record 的完整参数。"""

    def __init__(self):
        self.rows = []

    def record(self, rule_id, changed_by, change_kind, before=None, after=None,
               reason='', trigger_id=None, todo_id=None, decision_audit_id=None):
        row = SimpleNamespace(
            id=len(self.rows) + 1, rule_id=rule_id, changed_by=changed_by,
            change_kind=change_kind, before=before, after=after, reason=reason,
            trigger_id=trigger_id, todo_id=todo_id,
            decision_audit_id=decision_audit_id)
        self.rows.append(row)
        return row


def _rule(**over):
    """完整规则对象：默认 P0 止损（宪法级）+ 有到期/复核时间 + 一条价格线。"""
    base = dict(
        id=119, symbol='600519.SH', enabled=True, intent='exit_stop',
        lifecycle_stage='holding', linked_account='agent_brain',
        account='agent_brain',
        conditions=[{'type': 'price_break',
                     'params': {'price': 26.88, 'direction': 'below'}}],
        expires_at=NOW + timedelta(days=5),
        review_due_at=NOW + timedelta(days=2),
        ops_notes=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _linkage(rule=None, **over):
    rule = rule if rule is not None else _rule()
    rule_repo = FakeRuleRepo(rule)
    change_repo = FakeChangeRepo()
    kwargs = dict(now_fn=lambda: NOW)
    kwargs.update(over)
    return RuleChangeLinkage(rule_repo, change_repo, **kwargs), rule_repo, change_repo


def _apply(action, rule=None, *, reason='处置卡：不执行止损，改为调阈值', trigger_id=77,
           todo_id=42, decision_audit_id='audit-1', params='default',
           changed_by='agent'):
    linkage, rule_repo, change_repo = _linkage(rule)
    if params == 'default':
        params = PARAMS_BY_ACTION[action]
    outcome = linkage.apply(
        rule_repo.rule, action, reason=reason, trigger_id=trigger_id,
        todo_id=todo_id, decision_audit_id=decision_audit_id, params=params,
        changed_by=changed_by)
    return outcome, rule_repo, change_repo


def _assert_nothing_written(rule_repo, change_repo):
    assert rule_repo.updates == [], '被拒绝的动作不得改动规则'
    assert change_repo.rows == [], '被拒绝的动作不得写审计'


# ═══════════════════════════════════════════════════════════════════════════
# 0-① 动作词汇表（四动作是枚举，不是自由文本；跨层契约同集）
# ═══════════════════════════════════════════════════════════════════════════
class TestActionVocabulary:
    def test_four_actions_are_the_disposition_card_actions(self):
        assert [a.value for a in RuleChangeAction] == [
            'adjust_threshold', 'postpone', 'disable', 'retire']
        assert set(ACTION_LABELS) == set(RuleChangeAction)

    def test_change_kind_mapping_is_total_and_stable(self):
        """动作 → change_kind 是唯一映射：阈值/退役复用既有词汇，停用/延期为新增。"""
        assert CHANGE_KIND_BY_ACTION == {
            RuleChangeAction.ADJUST_THRESHOLD: 'threshold',
            RuleChangeAction.POSTPONE: 'postpone',
            RuleChangeAction.DISABLE: 'disable',
            RuleChangeAction.RETIRE: 'retire',
        }
        # 四动作映射两两不同：审计里能区分「停用」与「退役」
        assert len(set(CHANGE_KIND_BY_ACTION.values())) == 4

    def test_guard_vocabulary_mirrors_engine_enum(self):
        """domain 守卫白名单与应用层枚举同集（字符串是唯一跨层契约）。"""
        assert set(DISPOSITION_ACTIONS) == {a.value for a in RuleChangeAction}
        assert set(DISPOSITION_DISABLING_ACTIONS) == {
            RuleChangeAction.DISABLE.value, RuleChangeAction.RETIRE.value}

    def test_unknown_action_rejected(self):
        with pytest.raises(ValueError, match='未知的处置卡规则动作'):
            _apply('delete_rule', params={})
        # 守卫本身也拒绝（即使绕过应用层枚举）
        with pytest.raises(ValueError, match='未知的处置卡规则动作'):
            guard_disposition_action(_rule(), 'delete_rule')


# ═══════════════════════════════════════════════════════════════════════════
# 0-② 调阈值（adjust_threshold → change_kind=threshold）
# ═══════════════════════════════════════════════════════════════════════════
class TestAdjustThreshold:
    def test_top_level_price_line_is_rewritten_and_audited(self):
        outcome, rule_repo, change_repo = _apply(
            RuleChangeAction.ADJUST_THRESHOLD, params={'price': 25.5})

        # ① 规则真更新
        cond = rule_repo.rule.conditions[0]
        assert cond['params']['price'] == 25.5
        assert cond['params']['direction'] == 'below'      # 未指定方向 → 保持原方向
        assert len(rule_repo.updates) == 1

        # ② 审计留痕（change_kind/before/after 只含涉及字段）
        assert len(change_repo.rows) == 1
        change = change_repo.rows[0]
        assert change.change_kind == 'threshold'
        assert change.before == {'conditions': [
            {'type': 'price_break', 'params': {'price': 26.88, 'direction': 'below'}}]}
        assert change.after['conditions'][0]['params']['price'] == 25.5
        assert outcome.change_kind == 'threshold'
        assert isinstance(outcome, RuleChangeOutcome)

    def test_direction_can_be_flipped_in_the_same_change(self):
        outcome, rule_repo, _ = _apply(
            RuleChangeAction.ADJUST_THRESHOLD,
            params={'price': 30.0, 'direction': 'above'})
        cond = rule_repo.rule.conditions[0]
        assert (cond['params']['price'], cond['params']['direction']) == (30.0, 'above')
        assert outcome.fields['conditions'][0]['params']['direction'] == 'above'

    def test_nested_combined_and_staged_break_are_rewritten(self):
        """combined 里的 price_break 与 staged_break 的触及线都要改——只改顶层=假修复。"""
        rule = _rule(conditions=[
            {'type': 'combined', 'params': {'operator': 'AND', 'conditions': [
                {'type': 'price_break', 'params': {'price': 26.88, 'direction': 'below'}},
                {'type': 'volume_surge', 'params': {'multiple': 1.5}},
            ]}},
            {'type': 'staged_break',
             'params': {'touch': {'price': 27.5, 'direction': 'below'},
                        'confirm': {'kind': 'hold', 'minutes': 30}}},
        ])
        _, rule_repo, _ = _apply(
            RuleChangeAction.ADJUST_THRESHOLD, rule=rule, params={'price': 20.0})

        nested = rule_repo.rule.conditions[0]['params']['conditions'][0]
        assert nested['params']['price'] == 20.0
        # 非价格条件原样保留（不误伤 volume_surge）
        assert rule_repo.rule.conditions[0]['params']['conditions'][1] == {
            'type': 'volume_surge', 'params': {'multiple': 1.5}}
        assert rule_repo.rule.conditions[1]['params']['touch']['price'] == 20.0
        assert rule_repo.rule.conditions[1]['params']['confirm'] == {
            'kind': 'hold', 'minutes': 30}

    @pytest.mark.parametrize('params', [
        None, {}, {'direction': 'below'}, {'price': 'abc'}, {'price': -1},
        {'price': 0}, {'price': 25.5, 'direction': 'sideways'},
    ])
    def test_invalid_params_are_rejected_before_any_write(self, params):
        with pytest.raises(ValueError):
            _apply(RuleChangeAction.ADJUST_THRESHOLD, params=params)

    def test_rule_without_price_condition_is_rejected(self):
        """没有可调阈值的价格条件 → 拒绝假动作（不是「改了个寂寞」）。"""
        rule = _rule(conditions=[{'type': 'volume_surge',
                                  'params': {'multiple': 2.0}}])
        with pytest.raises(ValueError, match='可调阈值'):
            _apply(RuleChangeAction.ADJUST_THRESHOLD, rule=rule,
                   params={'price': 25.5})

    def test_empty_conditions_is_rejected(self):
        with pytest.raises(ValueError, match='conditions'):
            _apply(RuleChangeAction.ADJUST_THRESHOLD,
                   rule=_rule(conditions=[]), params={'price': 25.5})


# ═══════════════════════════════════════════════════════════════════════════
# 0-② 延期（postpone → change_kind=postpone）
# ═══════════════════════════════════════════════════════════════════════════
class TestPostpone:
    def test_review_and_expiry_are_pushed_forward(self):
        rule = _rule(expires_at=NOW + timedelta(days=5),
                     review_due_at=NOW + timedelta(days=2))
        outcome, rule_repo, change_repo = _apply(
            RuleChangeAction.POSTPONE, rule=rule, params={'days': 3})

        assert rule_repo.rule.review_due_at == NOW + timedelta(days=3)
        assert rule_repo.rule.expires_at == NOW + timedelta(days=8)   # 5+3
        change = change_repo.rows[0]
        assert change.change_kind == 'postpone'
        assert change.before == {
            'expires_at': (NOW + timedelta(days=5)).isoformat(),
            'review_due_at': (NOW + timedelta(days=2)).isoformat()}
        assert change.after == {
            'expires_at': (NOW + timedelta(days=8)).isoformat(),
            'review_due_at': (NOW + timedelta(days=3)).isoformat()}
        assert outcome.fields['review_due_at'] == NOW + timedelta(days=3)

    def test_no_expiry_is_never_invented(self):
        """规则本来没有到期时间：延期只动复核时间，**不硬造** expires_at。"""
        _, rule_repo, change_repo = _apply(
            RuleChangeAction.POSTPONE, rule=_rule(expires_at=None),
            params={'days': 2})
        assert rule_repo.rule.expires_at is None
        assert 'expires_at' not in rule_repo.updates[0]
        assert change_repo.rows[0].after['expires_at'] is None
        assert rule_repo.rule.review_due_at == NOW + timedelta(days=2)

    def test_already_expired_rule_restarts_from_now(self):
        """已过期的规则顺延后不能仍是过去时间（从此刻起算）。"""
        _, rule_repo, _ = _apply(
            RuleChangeAction.POSTPONE,
            rule=_rule(expires_at=NOW - timedelta(days=2)), params={'days': 2})
        assert rule_repo.rule.expires_at == NOW + timedelta(days=2)

    def test_default_days_when_params_omitted(self):
        _, rule_repo, _ = _apply(
            RuleChangeAction.POSTPONE, rule=_rule(expires_at=None), params=None)
        assert rule_repo.rule.review_due_at == NOW + timedelta(
            days=DEFAULT_POSTPONE_DAYS)

    @pytest.mark.parametrize('days', [0, -1, 'x', True, None])
    def test_invalid_days_rejected(self, days):
        with pytest.raises(ValueError, match='params.days'):
            _apply(RuleChangeAction.POSTPONE, params={'days': days})


# ═══════════════════════════════════════════════════════════════════════════
# 0-② 停用 / 退役（disable / retire → change_kind=disable/retire）
# ═══════════════════════════════════════════════════════════════════════════
class TestDisable:
    def test_disable_turns_rule_off_but_keeps_lifecycle_stage(self):
        rule = _rule(intent='trend_observe', lifecycle_stage='tracking')
        outcome, rule_repo, change_repo = _apply(
            RuleChangeAction.DISABLE, rule=rule, reason='噪音规则，先停用观察')

        assert rule_repo.rule.enabled is False
        assert rule_repo.rule.lifecycle_stage == 'tracking'   # 停用 ≠ 退役
        change = change_repo.rows[0]
        assert change.change_kind == 'disable'
        assert change.before == {'enabled': True}
        assert change.after == {'enabled': False}
        assert outcome.change_kind == 'disable'

    def test_disable_persists_reason_into_rule_ops_notes(self):
        """理由同时写进规则本体（规则详情页可见），带来源与触发 id。"""
        _, rule_repo, change_repo = _apply(
            RuleChangeAction.DISABLE, reason='止损线失真，先停用等人复核')
        notes = rule_repo.rule.ops_notes
        assert isinstance(notes, list) and len(notes) == 1
        note = notes[0]
        assert note['by'] == LINKAGE_NOTE_SOURCE
        assert note['action'] == 'disable'
        assert note['trigger_id'] == 77
        assert '止损线失真' in note['text']
        assert change_repo.rows[0].reason == '止损线失真，先停用等人复核'

    def test_existing_ops_notes_are_appended_not_overwritten(self):
        old = [{'at': '2026-10-01T00:00:00', 'by': 'watch_engine/stop_retire',
                'text': '旧注记'}]
        _, rule_repo, _ = _apply(RuleChangeAction.DISABLE,
                                 rule=_rule(intent='trend_observe', ops_notes=old))
        assert rule_repo.rule.ops_notes[0] == old[0]
        assert len(rule_repo.rule.ops_notes) == 2


class TestRetire:
    def test_retire_turns_rule_off_and_closes_lifecycle(self):
        outcome, rule_repo, change_repo = _apply(RuleChangeAction.RETIRE)
        assert rule_repo.rule.enabled is False
        assert rule_repo.rule.lifecycle_stage == RETIRED_LIFECYCLE_STAGE == 'closed'
        change = change_repo.rows[0]
        assert change.change_kind == 'retire'
        assert change.before == {'enabled': True, 'lifecycle_stage': 'holding'}
        assert change.after == {'enabled': False, 'lifecycle_stage': 'closed'}
        assert outcome.change_kind == 'retire'


# ═══════════════════════════════════════════════════════════════════════════
# 0-③ 溯源（trigger_id 必填；todo/决策审计透传；四动作矩阵）
# ═══════════════════════════════════════════════════════════════════════════
class TestTraceability:
    @pytest.mark.parametrize('action', list(RuleChangeAction))
    def test_every_action_writes_exactly_one_traced_audit_row(self, action):
        _, rule_repo, change_repo = _apply(action)
        assert len(rule_repo.updates) == 1, '每个动作都必须真改规则'
        assert len(change_repo.rows) == 1, '每个动作都必须留一条审计'
        change = change_repo.rows[0]
        assert change.rule_id == 119
        assert change.trigger_id == 77                       # 溯源触发
        assert change.todo_id == 42                          # 处置卡血缘
        assert change.decision_audit_id == 'audit-1'
        assert change.changed_by == 'agent'
        assert change.reason.strip()
        assert change.change_kind == CHANGE_KIND_BY_ACTION[action]

    def test_missing_trigger_id_is_rejected_before_any_write(self):
        """没有触发来源的规则变更无法复盘：拒绝，且不写半条。"""
        with pytest.raises(ValueError, match='trigger_id'):
            _apply(RuleChangeAction.DISABLE, trigger_id=None)
        with pytest.raises(ValueError, match='trigger_id'):
            _apply(RuleChangeAction.ADJUST_THRESHOLD, trigger_id=0)
        with pytest.raises(ValueError, match='trigger_id'):
            _apply(RuleChangeAction.RETIRE, trigger_id=True)

    def test_missing_reason_is_rejected_for_all_four_actions(self):
        for action in RuleChangeAction:
            with pytest.raises(ValueError):
                _apply(action, reason='   ')

    def test_reason_is_required_even_for_audit_when_rule_already_disabled(self):
        with pytest.raises(ValueError, match='reason'):
            _apply(RuleChangeAction.DISABLE, rule=_rule(enabled=False), reason='')

    def test_unknown_rule_update_returns_none_is_rejected(self):
        linkage, rule_repo, change_repo = _linkage(_rule())
        rule_repo.rule = None                                # 仓储侧找不到该规则
        with pytest.raises(ValueError, match='不存在'):
            linkage.apply(_rule(), RuleChangeAction.DISABLE,
                          reason='停用', trigger_id=77)
        assert change_repo.rows == []

    def test_changed_by_is_forwarded(self):
        _, _, change_repo = _apply(RuleChangeAction.DISABLE, changed_by='user')
        assert change_repo.rows[0].changed_by == 'user'

    def test_rule_can_be_a_dict_projection(self):
        """规则 dict 投影（自愈仓储）同样可落地：id/字段读取不依赖 ORM。"""
        rule = {'id': 200, 'symbol': '000001.SZ', 'enabled': True,
                'intent': 'trend_observe', 'lifecycle_stage': 'tracking',
                'conditions': [{'type': 'price_break',
                                'params': {'price': 10.0, 'direction': 'above'}}],
                'expires_at': None, 'review_due_at': None, 'ops_notes': None}
        rule_repo = FakeRuleRepo(rule)                       # dict 投影同样支持写回
        change_repo = FakeChangeRepo()
        linkage = RuleChangeLinkage(rule_repo, change_repo, now_fn=lambda: NOW)
        outcome = linkage.apply(rule, RuleChangeAction.ADJUST_THRESHOLD,
                                reason='阈值失真', trigger_id=9,
                                params={'price': 9.5})
        assert outcome.rule_id == 200
        assert outcome.fields['conditions'][0]['params']['price'] == 9.5

    # ── 与执行指令（P0「不执行」态）的联动 ───────────────────────────
    def test_apply_for_decline_takes_trace_ids_from_directive(self):
        rule = _rule()
        rule_repo = FakeRuleRepo(rule)
        change_repo = FakeChangeRepo()
        linkage = RuleChangeLinkage(rule_repo, change_repo, now_fn=lambda: NOW)
        directive = SimpleNamespace(rule_id=rule.id, trigger_id=555, todo_id=88)

        outcome = linkage.apply_for_decline(
            directive, RuleChangeAction.DISABLE, reason='不执行止损，停用待复核',
            decision_audit_id='audit-9')

        assert outcome.trigger_id == 555
        assert outcome.todo_id == 88
        assert change_repo.rows[0].trigger_id == 555
        assert change_repo.rows[0].todo_id == 88
        assert change_repo.rows[0].decision_audit_id == 'audit-9'

    def test_apply_for_decline_rejects_directive_without_trigger(self):
        rule = _rule()
        linkage = RuleChangeLinkage(FakeRuleRepo(rule), FakeChangeRepo(),
                                    now_fn=lambda: NOW)
        directive = SimpleNamespace(rule_id=rule.id, trigger_id=None, todo_id=None)
        with pytest.raises(ValueError, match='trigger_id'):
            linkage.apply_for_decline(directive, RuleChangeAction.DISABLE,
                                      reason='停用')

    def test_apply_for_decline_rejects_unknown_rule(self):
        directive = SimpleNamespace(rule_id=404, trigger_id=5, todo_id=None)
        linkage = RuleChangeLinkage(FakeRuleRepo(None), FakeChangeRepo(),
                                    now_fn=lambda: NOW)
        with pytest.raises(ValueError, match='无可落地规则'):
            linkage.apply_for_decline(directive, RuleChangeAction.DISABLE,
                                      reason='停用')


# ═══════════════════════════════════════════════════════════════════════════
# 0-④ / 2 宪法级止损停用必须随附理由（guard 拦截）
# ═══════════════════════════════════════════════════════════════════════════
class TestConstitutionalGuard:
    @pytest.mark.parametrize('action', [RuleChangeAction.DISABLE, RuleChangeAction.RETIRE])
    def test_constitutional_stop_loss_without_reason_is_rejected_before_write(self, action):
        linkage, rule_repo, change_repo = _linkage(_rule(intent='exit_stop'))
        with pytest.raises(ConstitutionalRuleSilentDisable, match='无理由停用'):
            linkage.apply(rule_repo.rule, action, reason='', trigger_id=77,
                          todo_id=42)
        _assert_nothing_written(rule_repo, change_repo)
        assert rule_repo.rule.enabled is True, '拒绝后规则必须原样未动'

    @pytest.mark.parametrize('action', [RuleChangeAction.DISABLE, RuleChangeAction.RETIRE])
    def test_constitutional_stop_loss_with_reason_is_allowed(self, action):
        _, rule_repo, change_repo = _apply(
            action, reason='止损线需要重新标定，先停用一天并重建保护线')
        assert rule_repo.rule.enabled is False
        assert change_repo.rows[0].reason.startswith('止损线需要重新标定')

    def test_non_constitutional_action_disables_without_guard_error(self):
        """非宪法级规则不停用铁律挡——但审计理由仍然必填（R-020）。"""
        rule = _rule(intent='trend_observe')
        linkage, rule_repo, change_repo = _linkage(rule)
        with pytest.raises(ValueError, match='reason'):
            linkage.apply(rule, RuleChangeAction.DISABLE, reason='', trigger_id=77)
        _assert_nothing_written(rule_repo, change_repo)

    def test_threshold_adjust_on_stop_loss_does_not_need_disable_reason(self):
        """调阈值不关规则 → 不走停用铁律（理由仍写审计）。"""
        outcome, rule_repo, _ = _apply(RuleChangeAction.ADJUST_THRESHOLD,
                                       reason='下移到真实支撑位')
        assert rule_repo.rule.enabled is True
        assert outcome.change_kind == 'threshold'

    def test_guard_alone_rejects_dict_rule_too(self):
        """守卫对 dict 规则同判据（仓储两条轨都可能传投影）。"""
        rule = {'id': 1, 'symbol': '300677.SZ', 'enabled': True,
                'intent': 'exit_stop'}
        with pytest.raises(ConstitutionalRuleSilentDisable):
            guard_disposition_action(rule, 'disable', reason='')
        guard_disposition_action(rule, 'disable', reason='停用理由')


# ═══════════════════════════════════════════════════════════════════════════
# 仓储契约：trigger_id 溯源列在适配器层可用（不碰 DB）
# ═══════════════════════════════════════════════════════════════════════════
class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.order = []
        self.limit_value = None

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def order_by(self, *criteria):
        self.order.extend(criteria)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.rows


class _FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        obj.id = 1
        obj.created_at = NOW
        self.refreshed.append(obj)

    def rollback(self):
        pass


class _RepoWithFakeSession(WatchRuleChangeRepository):
    """把 scoped session 换成假件：只验适配器逻辑，不碰真库。"""

    def __init__(self, session):
        super().__init__()
        self._fake_session = session

    @property
    def session(self):
        return self._fake_session


class TestRepositoryTraceability:
    def test_change_to_dict_exposes_trace_ids(self):
        row = SimpleNamespace(
            id=9, rule_id=119, changed_by='agent', change_kind='disable',
            before={'enabled': True}, after={'enabled': False}, reason='停用',
            trigger_id=77, todo_id=42, decision_audit_id='audit-1',
            created_at=NOW)
        payload = change_to_dict(row)
        assert payload['trigger_id'] == 77
        assert payload['todo_id'] == 42
        assert payload['created_at'] == NOW.isoformat()

    def test_record_writes_trigger_id_and_todo_id(self):
        session = _FakeSession()
        repo = _RepoWithFakeSession(session)
        change = repo.record(
            rule_id=119, changed_by='agent', change_kind='Disable',
            before={'enabled': True}, after={'enabled': False},
            reason='停用', trigger_id=77, todo_id=42, decision_audit_id='audit-1')
        assert change.trigger_id == 77
        assert change.todo_id == 42
        assert change.change_kind == 'disable'          # 大小写归一
        assert session.added == [change] and session.commits == 1

    @pytest.mark.parametrize('trigger_id', [0, -1, True])
    def test_record_rejects_non_positive_trace_id_before_db(self, trigger_id):
        repo = _RepoWithFakeSession(_FakeSession())
        with pytest.raises(ValueError, match='trigger_id'):
            repo.record(rule_id=1, changed_by='agent', change_kind='disable',
                        reason='停用', trigger_id=trigger_id)

    def test_record_keeps_existing_validations(self):
        repo = _RepoWithFakeSession(_FakeSession())
        with pytest.raises(ValueError, match='reason'):
            repo.record(rule_id=1, changed_by='agent', change_kind='disable', reason='')
        with pytest.raises(ValueError, match='changed_by'):
            repo.record(rule_id=1, changed_by='robot', change_kind='disable', reason='x')
        with pytest.raises(ValueError, match='change_kind'):
            repo.record(rule_id=1, changed_by='agent', change_kind='', reason='x')

    def test_list_by_trigger_is_ordered_and_requires_trigger(self):
        rows = [SimpleNamespace(id=1, trigger_id=7), SimpleNamespace(id=2, trigger_id=7)]
        query = _FakeQuery(rows)
        session = _FakeSession()
        session.query = lambda model: query                  # 只读查询
        repo = _RepoWithFakeSession(session)

        assert repo.list_by_trigger(7) == rows
        assert len(query.filters) == 1
        assert len(query.order) == 2                          # created_at + id 正序
        assert query.limit_value == 50

        with pytest.raises(ValueError, match='trigger_id'):
            repo.list_by_trigger(None)
