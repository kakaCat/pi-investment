"""处置映射测试：Verdict → disposition（REQ-261007133807-eda6 t5 · FR-1）

守三件事：
1) **15 个受控码全部有映射**（漏一个就会落到兜底 pending，静默改变处置语义）；
2) 给定 verdict 时**不再重算**（调用方（引擎）已裁决，映射层不许各说各话）；
3) 兼容分支（`escalated=True` 无 verdict）顺序与文案不变：
   宪法级 → 预算 → escalated → L2 → 元触发 → 五道门。
"""
from types import SimpleNamespace

import pytest

from domain.watch.services.disposition import (
    DISPOSITION_AUTO_OBSERVED, DISPOSITION_DEDUPED, DISPOSITION_ESCALATED,
    DISPOSITION_META_REVIEW, DISPOSITION_PENDING, GateContext, InterventionConfig, decide,
)
from domain.watch.services.escalation_verdict import EscalationCode, Verdict

CFG = InterventionConfig()


def _rule(intent=None, level='L1', action=None):
    ah = {'trigger_level': level}
    if action:
        ah['action_on_trigger'] = action
    return SimpleNamespace(id=1, symbol='600150', intent=intent, action_hint=ah,
                           conditions=[{'type': 'price_break',
                                        'params': {'price': 39.25, 'direction': 'below'}}],
                           escalation_policy=None)


def _cond():
    return {'type': 'price_break', 'params': {'price': 39.25, 'direction': 'below'}}


EXPECTED = {
    EscalationCode.CONSTITUTIONAL_INTENT: DISPOSITION_ESCALATED,
    EscalationCode.RULE_EXPLICIT_ESCALATE: DISPOSITION_ESCALATED,
    EscalationCode.ANOMALY_CHANGE_PCT: DISPOSITION_ESCALATED,
    EscalationCode.RULE_LEVEL_L2: DISPOSITION_ESCALATED,
    EscalationCode.GATES_PASSED_ACTION: DISPOSITION_ESCALATED,
    EscalationCode.META_REVIEW: DISPOSITION_META_REVIEW,
    EscalationCode.BUDGET_EXHAUSTED: DISPOSITION_AUTO_OBSERVED,
    EscalationCode.OBSERVE_INTENT: DISPOSITION_AUTO_OBSERVED,
    EscalationCode.AMOUNT_BELOW_THRESHOLD: DISPOSITION_AUTO_OBSERVED,
    EscalationCode.SAME_TOPIC_COOLDOWN: DISPOSITION_AUTO_OBSERVED,
    EscalationCode.ECONOMIC_BELOW_K: DISPOSITION_AUTO_OBSERVED,
    EscalationCode.SUPPRESSED: DISPOSITION_AUTO_OBSERVED,
    EscalationCode.PENDING_NO_ACTION: DISPOSITION_PENDING,
    EscalationCode.DEDUPED: DISPOSITION_DEDUPED,
    EscalationCode.UNKNOWN: DISPOSITION_PENDING,
}


def test_every_code_has_a_mapping():
    """15 码全覆盖（与码表同源断言：码表新增一个码而这里没映射会立刻红）。"""
    assert set(EXPECTED) == set(EscalationCode.ALL)
    for code, want in EXPECTED.items():
        v = Verdict(EscalationCode.wakes(code), code, '理由-%s' % code)
        d, reason = decide(_rule(), _cond(), verdict=v, cfg=CFG)
        assert d == want, code
        assert reason == '理由-%s' % code  # 理由原样透出，不另造句


def test_given_verdict_is_not_recomputed():
    """给定 verdict 时映射层**不重算**：规则本该 GATES_PASSED_ACTION（叫），
    但调用方已裁决为 BUDGET_EXHAUSTED（不叫）→ 以裁决为准。"""
    rule = _rule(intent='entry', action='buy')
    recomputed, _ = decide(rule, _cond(), cfg=CFG)
    assert recomputed == DISPOSITION_ESCALATED  # 自算结果
    v = Verdict(False, EscalationCode.BUDGET_EXHAUSTED, '预算门：当日介入预算已耗尽')
    given, reason = decide(rule, _cond(), verdict=v, cfg=CFG)
    assert given == DISPOSITION_AUTO_OBSERVED
    assert '预算门' in reason


def test_legacy_escalated_branch_keeps_order_and_text():
    """兼容分支：宪法级/预算优先于 escalated；文案含「原始原因」逐字不变。"""
    # ① escalated 在宪法级之后：宪法级仍走自己的文案
    d, reason = decide(_rule(intent='exit_stop', action='sell'), _cond(), escalated=True,
                       escalation_reason='多规则共振', cfg=CFG)
    assert d == DISPOSITION_ESCALATED and '宪法' in reason
    # ② escalated 在预算门之后：预算耗尽 → 不叫（与收敛前一致）
    d, _ = decide(_rule(intent='entry', action='buy'), _cond(), escalated=True,
                  gate=GateContext(daily_wake_count=CFG.daily_budget), cfg=CFG)
    assert d == DISPOSITION_AUTO_OBSERVED
    # ③ 两者都没命中 → 走兼容文案
    d, reason = decide(_rule(intent='exit_take_profit'), _cond(), escalated=True,
                       escalation_reason='多规则共振（2 条规则近 60 秒内触发）', cfg=CFG)
    assert d == DISPOSITION_ESCALATED
    assert '升级策略命中（L1→L2）' in reason and '原始原因' in reason


def test_legacy_and_verdict_paths_agree_on_disposition():
    """同一输入：自算路径与给定 verdict 路径给出的 disposition 一致（无第二条口径）。"""
    cases = [(_rule(intent='exit_stop', action='sell'), GateContext()),
             (_rule(intent='entry', action='buy'), GateContext()),
             (_rule(intent='trend_observe', action='observe'), GateContext()),
             (_rule(intent='entry', action='buy'), GateContext(amount_yuan=1.0)),
             (_rule(intent='entry', action='buy'),
              GateContext(daily_wake_count=CFG.daily_budget))]
    for rule, gate in cases:
        auto, _ = decide(rule, _cond(), gate=gate, cfg=CFG)
        # 用同一 gate 造出的 verdict 再喂一次，结果必须一致
        from domain.watch.services.escalation_verdict import decide_escalation
        v = decide_escalation(rule, _cond(), None, None, gate=gate, cfg=CFG)
        given, _ = decide(rule, _cond(), gate=gate, verdict=v, cfg=CFG)
        assert auto == given, (rule.intent, rule.action_hint, gate)


def test_unknown_verdict_object_is_not_silently_dropped():
    """坏 verdict（无 code 字段）→ 落 pending 而不是抛错/静默归档。"""
    d, reason = decide(_rule(), _cond(), verdict=SimpleNamespace(reason='x'), cfg=CFG)
    assert d == DISPOSITION_PENDING
