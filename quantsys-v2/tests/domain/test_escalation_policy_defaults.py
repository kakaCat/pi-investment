"""规则侧显式化与人话说明测试（REQ-261007133807-eda6 t3 · FR-4）

守四件容易回归的事：
1) `EscalationPolicy.default()` **显式**给出阈值（不再留 None 让下游猜）；
2) `to_dict()` 只写被判定消费的字段（不把历史字段写回，避免"看着有策略其实不生效"）；
3) `explain_escalation` 对每种规则形态都给**非空且如实**的一句话；
4) 只有**真的偏离缺省**才说"规则覆写阈值"（default() 写的 5.0 与缺省同值，不算覆写）。
"""
from types import SimpleNamespace

from domain.watch.models import DEFAULT_ANOMALY_CHANGE_PCT, EscalationPolicy
from domain.watch.services.escalation_verdict import explain_escalation

LEGACY_FIELDS = ('max_triggers_per_window', 'price_deviation_pct', 'core_zones',
                 'volume_ratio_multiplier', 'multi_rule_confluence')


def _rule(policy=None, level='L1', action='buy', intent='entry', escalate=None):
    ah = {'trigger_level': level, 'action_on_trigger': action}
    if escalate is not None:
        ah['escalate'] = escalate
    return SimpleNamespace(intent=intent, action_hint=ah, escalation_policy=policy)


# ── 默认值显式化 ──────────────────────────────────────────────────────
def test_default_is_explicit_and_serializable():
    p = EscalationPolicy.default()
    assert p.auto_escalate is True
    assert p.anomaly_change_pct == DEFAULT_ANOMALY_CHANGE_PCT == 5.0
    assert p.to_dict() == {'auto_escalate': True, 'anomaly_change_pct': 5.0}


def test_to_dict_writeback_excludes_legacy_fields():
    """历史字段不写回：它们已不被任何判定消费，写回等于把旧坑重新埋上。"""
    d = EscalationPolicy.default().to_dict()
    assert set(d) == {'auto_escalate', 'anomaly_change_pct'}
    for f in LEGACY_FIELDS:
        assert f not in d


def test_to_dict_fills_default_threshold_when_field_is_none():
    """裸构造（anomaly_change_pct=None）序列化时也落**显式**缺省值，不留 None。"""
    assert EscalationPolicy().to_dict() == {'auto_escalate': True,
                                            'anomaly_change_pct': DEFAULT_ANOMALY_CHANGE_PCT}
    assert EscalationPolicy(auto_escalate=False).to_dict()['auto_escalate'] is False


# ── 人话说明 ──────────────────────────────────────────────────────────
def test_explain_undeclared_policy_is_explicit_about_being_undeclared():
    text = explain_escalation(_rule(policy=None))
    assert text.strip()
    assert '未声明' in text
    assert '叫我' in text  # FR-4 判据：说明必须回答"会不会叫我"


def test_explain_l2_is_unconditional():
    text = explain_escalation(_rule(policy=None, level='L2'))
    assert 'L2' in text and '无条件叫我' in text


def test_explain_auto_escalate_off_states_what_still_wakes():
    text = explain_escalation(_rule(policy=EscalationPolicy(auto_escalate=False)))
    assert '已关闭自动升级' in text
    assert 'L2' in text and '止损' in text  # 说明"仍会叫我"的两条路


def test_explain_explicit_escalate_declaration():
    text = explain_escalation(_rule(policy=EscalationPolicy.default(), escalate=True))
    assert '规则显式声明' in text and '不看阈值' in text


def test_explain_threshold_override_only_when_it_really_differs():
    """default() 的 5.0 == 缺省 → 说「按缺省阈值」；8.0 → 才说「规则覆写阈值」。"""
    same = explain_escalation(_rule(policy=EscalationPolicy.default()))
    assert '按缺省阈值' in same and '覆写' not in same
    diff = explain_escalation(_rule(policy=EscalationPolicy(anomaly_change_pct=8.0)))
    assert '规则覆写阈值' in diff and '8.0' in diff
    # dict 形态（= 库表 JSONB 取回）同样认
    from_dict = explain_escalation(_rule(policy={'auto_escalate': True,
                                                 'anomaly_change_pct': 3.5}))
    assert '规则覆写阈值' in from_dict and '3.5' in from_dict


def test_explain_observe_rule_states_it_will_not_wake_for_action():
    text = explain_escalation(_rule(policy=EscalationPolicy.default(), intent='trend_observe'))
    assert '观察类' in text


def test_explain_is_never_empty_for_any_rule_shape():
    """任何形态都必须给一句非空说明 —— 空串会让规则侧"看不见"退化成静默。"""
    shapes = [_rule(policy=None), _rule(policy=EscalationPolicy.default()),
              _rule(policy=EscalationPolicy(auto_escalate=False)),
              _rule(policy={}), _rule(policy=EscalationPolicy(anomaly_change_pct=2.0)),
              _rule(policy=None, level='L0', action='observe', intent='trend_observe'),
              _rule(policy=None, level='L2', intent='exit_stop', action='sell')]
    for r in shapes:
        text = explain_escalation(r)
        assert isinstance(text, str) and text.strip(), r.action_hint
