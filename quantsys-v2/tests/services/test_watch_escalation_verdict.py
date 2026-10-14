"""升级裁决词表与结果契约测试（REQ-261007133807-eda6 t1）

本文件只钉**契约**（码表 / Verdict 不可变与派生规则），不含裁决逻辑
（裁决顺序表属 t2：tests/services/test_watch_escalation_verdict.py 的后续用例）。

用法：pytest tests/services/test_watch_escalation_verdict.py -q -k code_table
"""
import dataclasses

import pytest

from domain.watch.services.escalation_verdict import EscalationCode, Verdict


# ── 码表契约 ──────────────────────────────────────────────────────────
def test_code_table_has_exactly_fifteen_codes():
    """15 个受控码，且 ALL 由 PATH_LABEL 派生（不另行手写一份）。"""
    assert len(EscalationCode.ALL) == 15
    assert set(EscalationCode.PATH_LABEL) == set(EscalationCode.ALL)
    assert len(set(EscalationCode.ALL)) == 15  # 无重复


def test_code_table_labels_cover_every_code():
    """每个码都有非空路径标签 —— 卡面渲染依赖它，缺标签会让「升级原因」行退化。"""
    for code in EscalationCode.ALL:
        label = EscalationCode.PATH_LABEL[code]
        assert isinstance(label, str) and label.strip(), code
        assert EscalationCode.label_of(code) == label


def test_code_table_covers_both_sides_and_overrides():
    """叫 / 没叫 / 覆盖 三侧都在表内（缺"没叫"的码 = 成本控制回到黑盒）。"""
    for code in (EscalationCode.CONSTITUTIONAL_INTENT, EscalationCode.ANOMALY_CHANGE_PCT,
                 EscalationCode.RULE_LEVEL_L2):
        assert EscalationCode.wakes(code) is True
    for code in (EscalationCode.BUDGET_EXHAUSTED, EscalationCode.OBSERVE_INTENT,
                 EscalationCode.AMOUNT_BELOW_THRESHOLD, EscalationCode.SAME_TOPIC_COOLDOWN,
                 EscalationCode.ECONOMIC_BELOW_K, EscalationCode.PENDING_NO_ACTION,
                 EscalationCode.DEDUPED, EscalationCode.SUPPRESSED):
        assert EscalationCode.wakes(code) is False
    assert EscalationCode.WAKING <= set(EscalationCode.ALL)


def test_code_table_normalize_is_total_and_never_raises():
    """归一化是全函数：未收录码一律回落 UNKNOWN，不抛错、不臆造。"""
    assert EscalationCode.normalize('BUDGET_EXHAUSTED') == EscalationCode.BUDGET_EXHAUSTED
    assert EscalationCode.normalize(' budget_exhausted ') == EscalationCode.BUDGET_EXHAUSTED
    for bogus in ('', None, '   ', 'NOT_A_CODE', '频率异常'):
        assert EscalationCode.normalize(bogus) == EscalationCode.UNKNOWN
        assert EscalationCode.is_valid(bogus) is False
    assert EscalationCode.is_valid(EscalationCode.UNKNOWN) is True


# ── Verdict 契约 ──────────────────────────────────────────────────────
def _v(code=EscalationCode.ANOMALY_CHANGE_PCT, **over):
    base = dict(should_wake=True, code=code, reason='涨跌幅 -6.10% 达到阈值 5.0%')
    base.update(over)
    return Verdict(**base)


def test_verdict_is_immutable():
    """裁决一旦产生即事实：赋值必须抛 FrozenInstanceError（覆盖只能走 overridden）。"""
    v = _v()
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.code = EscalationCode.BUDGET_EXHAUSTED  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.should_wake = False  # type: ignore[misc]


def test_verdict_should_wake_is_derived_from_code():
    """should_wake 与码必须一致：调用方传反了也以码为准（不许自相矛盾的裁决）。"""
    assert _v(EscalationCode.ANOMALY_CHANGE_PCT, should_wake=False).should_wake is True
    assert _v(EscalationCode.BUDGET_EXHAUSTED, should_wake=True).should_wake is False


def test_verdict_derives_path_label_from_code():
    v = _v(EscalationCode.RULE_LEVEL_L2)
    assert v.path == EscalationCode.PATH_LABEL[EscalationCode.RULE_LEVEL_L2]
    assert Verdict(False, EscalationCode.DEDUPED, '去重合并', path='自定义路径').path == '自定义路径'


def test_verdict_unknown_code_keeps_raw_text_in_note():
    """未受控码：如实留存原文，且不据此臆造理由（code 归一为 UNKNOWN）。"""
    v = _v('NOT_A_CODE', reason='原始理由')
    assert v.code == EscalationCode.UNKNOWN
    assert v.should_wake is False
    assert 'NOT_A_CODE' in v.note
    assert v.reason == '原始理由'


def test_verdict_overridden_returns_new_instance_and_keeps_original():
    """覆盖（去重/抑噪）必须留原判 —— "本来会叫、被压掉"要可查。"""
    before = _v(EscalationCode.ANOMALY_CHANGE_PCT)
    after = before.overridden(EscalationCode.DEDUPED, '去重合并（同标的同向 60s 内）')
    assert after is not before
    assert after.code == EscalationCode.DEDUPED
    assert after.should_wake is False
    assert '原判' in after.reason and before.reason in after.reason
    assert before.code == EscalationCode.ANOMALY_CHANGE_PCT  # 原实例未被改动

# ── 裁决顺序表（15 条判据；REQ-261007133807-eda6 t2 · FR-1）──────────────
from datetime import datetime, timedelta  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from application.services.watch_engine.conditions import EvalResult  # noqa: E402
from domain.watch.models import EscalationPolicy, MetricKind, QuoteData  # noqa: E402
from domain.watch.services.disposition import GateContext, InterventionConfig  # noqa: E402
from domain.watch.services.escalation_verdict import (  # noqa: E402
    decide_escalation, decide_escalation_paths,
)

CFG = InterventionConfig()  # 默认口径：预算 8 / 金额门 1% / 冷却 4h / k=3


def _rule(intent='', level='L1', action='observe', escalate=None, policy=None):
    """规则替身：action_hint 用 **dict**（= ORM/JSONB 取回的真实形态）。"""
    ah = {'trigger_level': level, 'action_on_trigger': action}
    if escalate is not None:
        ah['escalate'] = escalate
    return SimpleNamespace(
        id=7, symbol='600219', intent=intent, action_hint=ah,
        conditions=[{'type': 'price_break', 'params': {'price': 5.13, 'direction': 'above'}}],
        escalation_policy=EscalationPolicy.default() if policy is None else policy,
    )


def _quote(price=5.20, change_pct=None):
    return QuoteData(symbol='600219', price=price, change_pct=change_pct)


def _res(value=5.15, metric=MetricKind.PRICE):
    return EvalResult(triggered=True, value=value, distance_ratio=0.1,
                      message='现价 %.2f 上破阈值' % value, metric=metric)


def _code(rule, quote=None, result=None, gate=None, condition=None):
    v = decide_escalation(rule, condition if condition is not None else rule.conditions[0],
                          quote or _quote(), result or _res(), gate=gate, cfg=CFG)
    return v.code, v.should_wake


def test_order_1_constitutional_intent_wins_over_budget():
    """宪法级不看预算：预算耗尽也照样叫（收敛前 decide 规则 0）。"""
    assert _code(_rule(intent='exit_stop', action='sell'),
                 gate=GateContext(intent='exit_stop', daily_wake_count=99)) == (
        EscalationCode.CONSTITUTIONAL_INTENT, True)


def test_order_2_budget_exhausted_stops_non_constitutional():
    assert _code(_rule(intent='entry', action='buy'),
                 gate=GateContext(daily_wake_count=CFG.daily_budget)) == (
        EscalationCode.BUDGET_EXHAUSTED, False)


def test_order_3_rule_explicit_escalate():
    assert _code(_rule(intent='entry', escalate=True)) == (
        EscalationCode.RULE_EXPLICIT_ESCALATE, True)


def test_order_4_anomaly_change_pct_and_rule_override():
    assert _code(_rule(intent='entry', action='buy'), quote=_quote(change_pct=6.1)) == (
        EscalationCode.ANOMALY_CHANGE_PCT, True)
    # 阈值可被规则覆写：6.1% 未达 8.0% → 不升级，落到后续判定
    assert _code(_rule(intent='entry', policy=EscalationPolicy(anomaly_change_pct=8.0)),
                 quote=_quote(change_pct=6.1), gate=GateContext(trigger_kind='meta')) == (
        EscalationCode.META_REVIEW, True)


def test_order_5_rule_level_l2():
    assert _code(_rule(level='L2', action='observe')) == (EscalationCode.RULE_LEVEL_L2, True)


def test_order_6_meta_review_and_its_cooldown():
    assert _code(_rule(intent='entry', action='buy'), gate=GateContext(trigger_kind='meta')) == (
        EscalationCode.META_REVIEW, True)
    assert _code(_rule(intent='entry', action='buy'), gate=GateContext(
        trigger_kind='meta', last_intervention_at=datetime.now() - timedelta(hours=1))) == (
        EscalationCode.SAME_TOPIC_COOLDOWN, False)


def test_order_7_observe_intent_gate():
    assert _code(_rule(intent='trend_observe', action='observe')) == (
        EscalationCode.OBSERVE_INTENT, False)


def test_order_8_amount_gate():
    assert _code(_rule(intent='entry', action='buy'),
                 gate=GateContext(amount_yuan=50.0)) == (
        EscalationCode.AMOUNT_BELOW_THRESHOLD, False)


def test_order_9_same_topic_cooldown():
    assert _code(_rule(intent='entry', action='buy'), gate=GateContext(
        last_intervention_at=datetime.now() - timedelta(hours=1))) == (
        EscalationCode.SAME_TOPIC_COOLDOWN, False)


def test_order_10_economic_gate():
    assert _code(_rule(intent='entry', action='buy'),
                 gate=GateContext(expected_value_yuan=1.0)) == (
        EscalationCode.ECONOMIC_BELOW_K, False)


def test_order_11_gates_passed_action_wakes():
    assert _code(_rule(intent='entry', action='buy')) == (
        EscalationCode.GATES_PASSED_ACTION, True)


def test_order_12_pending_when_no_action_declared():
    assert _code(_rule(intent='entry', action='alert')) == (
        EscalationCode.PENDING_NO_ACTION, False)


def test_order_13_14_dedup_and_suppressed_are_post_verdict_overrides():
    """去重/抑噪是**裁决之后的覆盖**：原判必须留在理由里（"本来会叫、被压掉"可查）。"""
    rule = _rule(intent='entry', action='buy')
    base = decide_escalation(rule, rule.conditions[0], _quote(change_pct=6.1), _res(),
                             gate=GateContext(), cfg=CFG)
    assert base.code == EscalationCode.ANOMALY_CHANGE_PCT
    for code in (EscalationCode.DEDUPED, EscalationCode.SUPPRESSED):
        after = base.overridden(code, '覆盖理由')
        assert (after.code, after.should_wake) == (code, False)
        assert '原判' in after.reason and base.reason in after.reason


def test_order_15_unknown_is_for_callers_without_verdict():
    """UNKNOWN 不是出口兜底（出口兜底是 PENDING_NO_ACTION），而是「未接入」的缺省。"""
    rule = _rule(intent='entry', action='buy')
    assert decide_escalation(rule, rule.conditions[0], _quote(), _res(),
                             gate=GateContext(), cfg=CFG).code != EscalationCode.UNKNOWN
    assert Verdict(False, '', '').code == EscalationCode.UNKNOWN


def test_auto_escalate_off_disables_only_three_paths():
    """auto_escalate=false 只关三条路径：宪法级与 L2 分级仍会叫（与收敛前一致）。"""
    off = EscalationPolicy(auto_escalate=False)
    rule = _rule(intent='entry', action='buy', policy=off)
    assert decide_escalation_paths(rule, rule.conditions[0], _quote(change_pct=9.9), _res()) is None
    assert _code(_rule(intent='entry', action='buy', policy=off), quote=_quote(change_pct=9.9),
                 gate=GateContext(trigger_kind='meta')) == (EscalationCode.META_REVIEW, True)
    assert _code(_rule(level='L2', policy=off)) == (EscalationCode.RULE_LEVEL_L2, True)
    assert _code(_rule(intent='exit_stop', action='sell', policy=off))[0] == (
        EscalationCode.CONSTITUTIONAL_INTENT)


def test_paths_and_full_verdict_agree_on_code_and_path():
    """跨入口一致（TC-2）：IF-1 与 IF-3 对同一输入给出相同的码与命中路径。"""
    cases = [
        (_rule(intent='entry', escalate=True), _quote()),
        (_rule(intent='entry', action='buy'), _quote(change_pct=6.1)),
        (_rule(intent='entry', action='buy'), _quote(change_pct=1.0)),
        (_rule(intent='exit_stop', action='sell'), _quote()),
        (_rule(level='L2'), _quote()),
    ]
    checked = 0
    for rule, quote in cases:
        cond = rule.conditions[0]
        full = decide_escalation(rule, cond, quote, _res(), gate=GateContext(), cfg=CFG)
        paths = decide_escalation_paths(rule, cond, quote, _res())
        if paths is not None:
            checked += 1
            assert (full.code, full.path) == (paths.code, paths.path), rule.action_hint
    assert checked >= 3  # 至少覆盖显式/异常/宪法三条路径


def test_metric_contract_violation_raises_instead_of_silent_no_escalation():
    """算不出涨跌幅时**响亮抛错**，绝不降级为"不升级"（沿用 require_metric）。"""
    rule = _rule(intent='entry', action='buy')
    cond = {'type': 'pct_change', 'params': {'pct': 5.0}}
    with pytest.raises(Exception):
        decide_escalation(rule, cond, _quote(), _res(value=5.15, metric=MetricKind.PRICE),
                          gate=GateContext(), cfg=CFG)
