"""判据 metric 契约测试（REQ-c9f899 t2）

覆盖三件事：
  1) 各条件 handler 必须显式产出正确的 metric；
  2) 消费侧读 value 前必须声明 metric——#162 回归：price_break 的现价不得被当量比；
  3) 契约违反必须响亮抛错（不静默兜底）。
"""
import types

import pytest

from application.services.watch_engine.conditions import EvalContext, EvalResult, evaluate
from domain.watch.models import (
    MetricKind, QuoteData, WatchMetricContractViolation, WatchRule,
)
from domain.watch.services.escalation_checker import EscalationChecker
from domain.watch.services.metric_contract import metric_matches, metric_of, require_metric


def _quote(price=100.0, prev_close=99.0, volume=None):
    return types.SimpleNamespace(price=price, prev_close=prev_close,
                                 change_pct=None, volume=volume, symbol='000000')


def test_price_break_metric_is_price():
    res = evaluate({'type': 'price_break', 'params': {'price': 99.0, 'direction': 'above'}},
                   _quote(price=100.0), EvalContext())
    assert res.metric is MetricKind.PRICE
    assert res.unit == '元'
    assert res.value == 100.0


def test_pct_change_metric():
    res = evaluate({'type': 'pct_change', 'params': {'pct': 0.5, 'direction': 'above'}},
                   _quote(price=100.0, prev_close=99.0), EvalContext())
    assert res.metric is MetricKind.PCT_CHANGE
    assert res.unit == '%'


def test_pnl_pct_metric():
    res = evaluate({'type': 'pnl_pct', 'params': {'pct': -8.0, 'direction': 'below'}},
                   _quote(price=90.0), EvalContext(cost_price=100.0))
    assert res.metric is MetricKind.PNL_PCT


def test_volume_surge_metric():
    res = evaluate({'type': 'volume_surge', 'params': {'multiple': 1.5}},
                   _quote(volume=300.0),
                   EvalContext(avg_volume_20d=100.0, elapsed_fraction=1.0))
    assert res.metric is MetricKind.VOLUME_RATIO
    assert res.value == pytest.approx(3.0)


def test_volume_surge_degraded_keeps_metric():
    res = evaluate({'type': 'volume_surge', 'params': {'multiple': 1.5}},
                   _quote(volume=None), EvalContext(avg_volume_20d=None))
    assert res.degraded is True
    assert res.metric is MetricKind.VOLUME_RATIO


def test_combined_metric_is_composite():
    res = evaluate({'type': 'combined', 'params': {
        'operator': 'AND',
        'conditions': [
            {'type': 'price_break', 'params': {'price': 99.0, 'direction': 'above'}},
            {'type': 'pct_change', 'params': {'pct': 0.5, 'direction': 'above'}},
        ]}}, _quote(price=100.0, prev_close=99.0), EvalContext())
    assert res.metric is MetricKind.COMPOSITE


def test_metric_matches_is_lenient():
    res = evaluate({'type': 'price_break', 'params': {'price': 99.0, 'direction': 'above'}},
                   _quote(price=100.0), EvalContext())
    assert metric_matches(res, {MetricKind.PRICE}) is True
    assert metric_matches(res, {MetricKind.VOLUME_RATIO}) is False
    assert metric_of(res) is MetricKind.PRICE


def test_require_metric_raises_on_mismatch():
    res = evaluate({'type': 'price_break', 'params': {'price': 99.0, 'direction': 'above'}},
                   _quote(price=100.0), EvalContext())
    with pytest.raises(WatchMetricContractViolation) as ei:
        require_metric(res, {MetricKind.VOLUME_RATIO}, '_check_volume_anomaly')
    assert '期望 metric' in str(ei.value)
    # 匹配时不抛
    assert require_metric(res, {MetricKind.PRICE}, 'ok') is res


def _rule_with_volume_policy(cond):
    return WatchRule(id=162, symbol='002916', enabled=True, conditions=[cond],
                     escalation_policy={
                         'auto_escalate': True,
                         'price_deviation_pct': 5.0,
                         'multi_rule_confluence': {'enabled': True, 'window_seconds': 60},
                         'max_triggers_per_window': {'count': 3, 'window_minutes': 10},
                         'volume_ratio_multiplier': 2.0,
                     })


def test_rule_162_regression_price_not_treated_as_volume():
    """#162 回归：price_break 触发时，不得产出「量能异常」（现价 388.5 不是量比）"""
    cond = {'type': 'price_break', 'params': {'price': 388.75, 'direction': 'below'}}
    rule = _rule_with_volume_policy(cond)
    result = evaluate(cond, _quote(price=388.5), EvalContext())
    assert result.metric is MetricKind.PRICE

    reason = EscalationChecker().should_escalate(
        rule=rule, condition=cond, quote=QuoteData(symbol='002916', price=388.5),
        result=result, recent_trigger_count=1, concurrent_trigger_count=1)

    assert reason is None or '量能异常' not in reason


def test_volume_escalation_path_removed_by_t7():
    """t7 收敛：量能异常升级路径已删除——高量比也不再自动升级

    历史原因：该路径不校验 metric，把 price_break 的现价当量比（线上 19 条假「量能异常」）。
    真放量应由 volume_surge 条件本身表达，或由规则显式声明 action_hint.escalate。
    """
    cond = {'type': 'volume_surge', 'params': {'multiple': 1.5}}
    rule = _rule_with_volume_policy(cond)
    res = evaluate(cond, _quote(volume=400.0),
                   EvalContext(avg_volume_20d=100.0, elapsed_fraction=1.0))
    assert res.value == pytest.approx(4.0)
    assert res.metric is MetricKind.VOLUME_RATIO
    assert EscalationChecker().should_escalate(
        rule=rule, condition=cond, quote=QuoteData(symbol='000001', price=10.0),
        result=res) is None


def test_contract_still_enforced_on_anomaly_path():
    """t7 之后 metric 契约仍被强制：pct_change 条件给错 metric → 响亮抛错"""
    cond = {'type': 'pct_change', 'params': {'pct': 5.0, 'direction': 'above'}}
    rule = WatchRule(id=1, symbol='000001', enabled=True, conditions=[cond],
                     escalation_policy={'auto_escalate': True})
    wrong = EvalResult(triggered=True, value=6.0, distance_ratio=0.0,
                       message='x', metric=MetricKind.PRICE)
    with pytest.raises(WatchMetricContractViolation):
        EscalationChecker().should_escalate(
            rule=rule, condition=cond, quote=QuoteData(symbol='000001', price=10.0), result=wrong)
