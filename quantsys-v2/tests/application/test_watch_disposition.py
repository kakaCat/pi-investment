"""介入判据单测（REQ-f08def P3，RFC 014 v3 §3，w-c8cae280）

守四件容易回归的事：
1) 趋势观察类**不得**唤醒 agent（用户硬约束：成本与利润一致）
2) 宪法动作（止损）无条件介入，且**可突破每日预算**（铁律⑤，v2 曾丢）
3) 元触发（一直响/一直不响）走轻门（不适用金额门/节点门）——v2 的硬冲突修正
4) 五道门的每一道都能单独把触发挡回 auto_observed
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from application.services.watch_engine.disposition import (
    DISPOSITION_AUTO_OBSERVED, DISPOSITION_ESCALATED, DISPOSITION_META_REVIEW,
    DISPOSITION_PENDING, GateContext, InterventionConfig, decide,
    dedup_key, evaluate_meta_trigger, is_resolved, normalize_symbol,
)


def _rule(intent=None, level=None, action=None, conds=None):
    ah = {}
    if level:
        ah['trigger_level'] = level
    if action:
        ah['action_on_trigger'] = action
    return SimpleNamespace(
        id=1, symbol='600150', intent=intent,
        conditions=conds or [{'type': 'price_break', 'params': {'price': 39.25, 'direction': 'below'}}],
        action_hint=ah or None,
    )


def _cond(direction=None):
    return {'type': 'price_break', 'params': {'price': 39.25, 'direction': direction or 'below'}}


def test_observe_is_mechanical_no_agent():
    d, _ = decide(_rule(intent='trend_observe', level='L1', action='observe'), _cond())
    assert d == DISPOSITION_AUTO_OBSERVED


def test_stop_loss_is_constitutional():
    d, r = decide(_rule(intent='exit_stop', level='L2', action='sell'), _cond())
    assert d == DISPOSITION_ESCALATED
    assert '宪法' in r


def test_constitutional_breaks_daily_budget():
    """止损必须执行：预算耗尽也得介入（铁律⑤，v2 曾丢的回归）"""
    d, _ = decide(_rule(intent='exit_stop', level='L2', action='sell'), _cond(),
                  gate=GateContext(daily_wake_count=99))
    assert d == DISPOSITION_ESCALATED


def test_budget_blocks_non_constitutional():
    """每日预算耗尽时，普通 L1 买入不再介入（§3.3）"""
    d, _ = decide(_rule(intent='entry', level='L1', action='buy'), _cond(),
                  gate=GateContext(daily_wake_count=8))
    assert d == DISPOSITION_AUTO_OBSERVED


def test_l2_rule_escalates():
    d, _ = decide(_rule(intent='entry', level='L2', action='buy'), _cond())
    assert d == DISPOSITION_ESCALATED


def test_escalation_flag_escalates():
    d, _ = decide(_rule(intent='trend_observe', level='L1', action='observe'), _cond(), escalated=True)
    assert d == DISPOSITION_ESCALATED


def test_sell_rule_without_intent_field_is_not_observation():
    """声明了 sell 但没写 intent 的规则不能被误归趋势观察（否则卖出触发永远到不了 agent）"""
    d, _ = decide(_rule(level='L1', action='sell'), _cond())
    assert d == DISPOSITION_ESCALATED


def test_amount_gate_blocks_tiny_actions():
    """动作影响 < 账户 1%（≈1050 元）不值得介入（用户硬约束）"""
    d, r = decide(_rule(intent='exit_reduce', level='L1', action='sell'), _cond(),
                  gate=GateContext(amount_yuan=300))
    assert d == DISPOSITION_AUTO_OBSERVED
    assert '金额门' in r


def test_increment_gate_cools_down_same_topic():
    d, _ = decide(_rule(intent='exit_take_profit', level='L1', action='sell'), _cond(),
                  gate=GateContext(amount_yuan=8000,
                                   last_intervention_at=datetime.now() - timedelta(hours=1)))
    assert d == DISPOSITION_AUTO_OBSERVED


def test_increment_gate_passes_after_cooldown():
    d, _ = decide(_rule(intent='exit_take_profit', level='L1', action='sell'), _cond(),
                  gate=GateContext(amount_yuan=8000,
                                   last_intervention_at=datetime.now() - timedelta(hours=5)))
    assert d == DISPOSITION_ESCALATED


def test_economic_gate_blocks_when_expected_value_too_low():
    d, r = decide(_rule(intent='exit_reduce', level='L1', action='sell'), _cond(),
                  gate=GateContext(amount_yuan=8000, expected_value_yuan=1.0))
    assert d == DISPOSITION_AUTO_OBSERVED
    assert '经济门' in r


def test_meta_trigger_uses_light_gate_not_five_gates():
    """元触发（一直不响）没有金额/节点，但必须能过轻门——否则铁律④无法执行（v2 硬冲突）"""
    d, r = decide(_rule(intent='trend_observe', level='L1', action='observe'), _cond(),
                  gate=GateContext(trigger_kind='meta'))
    assert d == DISPOSITION_META_REVIEW


def test_evaluate_meta_trigger():
    cfg = InterventionConfig()
    assert evaluate_meta_trigger('burst', burst_count=5, cfg=cfg)[0]
    assert evaluate_meta_trigger('burst', burst_count=4, cfg=cfg)[0] is False
    assert evaluate_meta_trigger('idle', idle_days=14, cfg=cfg)[0]
    assert evaluate_meta_trigger('idle', idle_days=13, cfg=cfg)[0] is False
    assert evaluate_meta_trigger('stage', stage_idle_days=7, cfg=cfg)[0]
    assert evaluate_meta_trigger('expiry', days_to_expiry=1, cfg=cfg)[0]


def test_meta_review_is_not_resolved():
    """meta_review 与 pending/escalated 一样属于未收敛，必须进未处置清单"""
    assert not is_resolved(DISPOSITION_META_REVIEW)
    assert not is_resolved(DISPOSITION_PENDING)
    assert not is_resolved(DISPOSITION_ESCALATED)
    assert is_resolved(DISPOSITION_AUTO_OBSERVED)


def test_dedup_key_unifies_symbol_forms():
    assert dedup_key(_rule(), _cond('below')) == dedup_key(
        SimpleNamespace(id=2, symbol='600150.SH', intent=None, conditions=[], action_hint=None), _cond('below'))
    assert dedup_key(_rule(), _cond('below')) != dedup_key(_rule(), _cond('above'))
