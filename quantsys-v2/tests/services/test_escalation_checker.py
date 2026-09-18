"""EscalationChecker 测试（REQ-c9f899 t7 收敛后语义）

只认三条可信路径：规则显式声明 / 宪法级 / 异常波动。
历史五类（频率·价格偏差·核心区域·量能·共振）已删除——本文件用一条「旧策略全字段」
用例把它们钉死为不再生效。
"""
import pytest

from application.services.watch_engine.conditions import EvalResult
from domain.watch.models import (
    ActionHint, EscalationPolicy, MetricKind, QuoteData, TriggerLevel, WatchMetricContractViolation,
    WatchRule,
)
from domain.watch.services.escalation_checker import EscalationChecker


def _rule(**over):
    base = dict(
        id=1, symbol='600219', enabled=True,
        conditions=[{'type': 'price_break', 'params': {'price': 5.13, 'direction': 'above'}}],
        action_hint=ActionHint(trigger_level=TriggerLevel.L1_OBSERVATION,
                               action_on_trigger='observe', requires_agent=False),
        escalation_policy=EscalationPolicy.default(),
    )
    base.update(over)
    return WatchRule(**base)


LEGACY_POLICY = {
    'auto_escalate': True,
    'price_deviation_pct': 5.0,
    'core_zones': [{'low': 4.65, 'high': 5.13, 'reason': '平台震荡区'}],
    'volume_ratio_multiplier': 2.0,
    'max_triggers_per_window': {'count': 3, 'window_minutes': 10},
    'multi_rule_confluence': {'enabled': True, 'window_seconds': 60},
}


def _res(value=5.15, metric=MetricKind.PRICE):
    return EvalResult(triggered=True, value=value, distance_ratio=0.1,
                      message='x', metric=metric)


def test_policy_disabled_never_escalates():
    reason = EscalationChecker().should_escalate(
        _rule(escalation_policy=EscalationPolicy(auto_escalate=False)),
        {'type': 'price_break', 'params': {'price': 5.13, 'direction': 'above'}},
        QuoteData(symbol='600219', price=5.15, change_pct=1.2), _res())
    assert reason is None


def test_no_policy_and_normal_volatility_no_escalation():
    r = _rule(escalation_policy=None)
    reason = EscalationChecker().should_escalate(
        r, r.conditions[0], QuoteData(symbol='600219', price=5.15, change_pct=1.2), _res())
    assert reason is None


def test_explicit_declaration_escalates():
    r = _rule(action_hint=ActionHint(trigger_level=TriggerLevel.L1_OBSERVATION,
                                     action_on_trigger='observe', requires_agent=False))
    r.action_hint = {'trigger_level': 'L1', 'action_on_trigger': 'observe', 'escalate': True}
    reason = EscalationChecker().should_escalate(
        r, r.conditions[0], QuoteData(symbol='600219', price=5.15, change_pct=0.1), _res())
    assert reason is not None and '规则显式声明' in reason


def test_constitutional_intent_escalates_unconditionally():
    # WatchRule（领域模型）无 intent 字段——intent 由仓储映射层提供，判据按鸭子类型读取
    r = _rule()
    r.intent = 'exit_stop'
    reason = EscalationChecker().should_escalate(
        r, r.conditions[0], QuoteData(symbol='600219', price=5.15, change_pct=0.0), _res())
    assert reason is not None and '宪法级' in reason


def test_anomaly_volatility_escalates():
    r = _rule()
    reason = EscalationChecker().should_escalate(
        r, r.conditions[0], QuoteData(symbol='600219', price=5.5, change_pct=6.3), _res())
    assert reason is not None and '异常波动' in reason


def test_anomaly_volatility_below_threshold_not_escalated():
    r = _rule()
    reason = EscalationChecker().should_escalate(
        r, r.conditions[0], QuoteData(symbol='600219', price=5.5, change_pct=1.2), _res())
    assert reason is None


def test_anomaly_uses_pct_change_metric_when_condition_is_pct_change():
    cond = {'type': 'pct_change', 'params': {'pct': 5.0, 'direction': 'above'}}
    r = _rule(conditions=[cond])
    # quote.change_pct 很小，但判据给出的 metric 值是 6.0 → 应升级
    reason = EscalationChecker().should_escalate(
        r, cond, QuoteData(symbol='600219', price=5.5, change_pct=0.1),
        _res(value=6.0, metric=MetricKind.PCT_CHANGE))
    assert reason is not None and '异常波动' in reason


def test_anomaly_metric_violation_raises():
    """契约：pct_change 条件却给出非 pct_change 的 metric → 响亮抛错"""
    cond = {'type': 'pct_change', 'params': {'pct': 5.0, 'direction': 'above'}}
    r = _rule(conditions=[cond])
    with pytest.raises(WatchMetricContractViolation):
        EscalationChecker().should_escalate(
            r, cond, QuoteData(symbol='600219', price=5.5, change_pct=0.1),
            _res(value=6.0, metric=MetricKind.PRICE))


def test_legacy_five_paths_are_gone():
    """收敛证明：旧策略全字段齐备，也不再触发任何一条历史升级路径"""
    cond = {'type': 'price_break', 'params': {'price': 5.13, 'direction': 'above'}}
    r = _rule(conditions=[cond], escalation_policy=LEGACY_POLICY)

    # ① 旧「频率」：计数远超阈值
    assert EscalationChecker().should_escalate(
        r, cond, QuoteData(symbol='600219', price=5.15, change_pct=0.2), _res(),
        recent_trigger_count=99, concurrent_trigger_count=99) is None
    # ② 旧「价格偏差」：现价远离设定价 20%
    assert EscalationChecker().should_escalate(
        r, cond, QuoteData(symbol='600219', price=6.5, change_pct=0.2), _res()) is None
    # ③ 旧「核心区域」：价格落在区间内
    assert EscalationChecker().should_escalate(
        r, cond, QuoteData(symbol='600219', price=5.0, change_pct=0.2), _res()) is None
    # ④ 旧「量能异常」：把现价（388.5）当量比的反例（#162 同型）
    big = _rule(conditions=[{'type': 'price_break', 'params': {'price': 388.75, 'direction': 'below'}}],
                escalation_policy=LEGACY_POLICY)
    reason = EscalationChecker().should_escalate(
        big, big.conditions[0], QuoteData(symbol='002916', price=388.5, change_pct=0.1),
        _res(value=388.5, metric=MetricKind.PRICE))
    assert reason is None or '量能异常' not in reason
