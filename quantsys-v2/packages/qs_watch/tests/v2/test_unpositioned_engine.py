"""t4 验收用例：非持仓类判定 unpositioned_engine（FR-5，architecture.md IF-5）

覆盖：
- 买入范围（entry）到买点价触发 / 未到不触发
- 观察（trend_observe）触发但标记 observe_only
- 持仓类 intent 不在本模块处理
"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2 import unpositioned_engine


def _rule(intent, price=10.0, direction='above', rid=1):
    cond = {'type': 'price_break', 'params': {'price': price, 'direction': direction}}
    return SimpleNamespace(
        id=rid,
        symbol='000999.SZ',
        intent=intent,
        conditions=[cond],
    )


def _quote(price):
    return SimpleNamespace(symbol='000999.SZ', price=price, prev_close=price, change_pct=0.0)


class TestEntry:
    def test_entry_triggers_at_buy_price(self):
        rule = _rule('entry', price=30.0, direction='above')
        j = unpositioned_engine.evaluate(rule, _quote(30.2))
        assert j.triggered is True
        assert j.intent == 'entry'
        assert j.observe_only is False
        assert len(j.hit_conditions) == 1

    def test_entry_not_triggered_below_buy_price(self):
        rule = _rule('entry', price=30.0, direction='above')
        j = unpositioned_engine.evaluate(rule, _quote(29.5))
        assert j.triggered is False
        assert j.reason == 'no_condition_hit'


class TestObserve:
    def test_observe_triggers_marked_observe_only(self):
        rule = _rule('trend_observe', price=10.0, direction='above')
        j = unpositioned_engine.evaluate(rule, _quote(10.5))
        assert j.triggered is True
        assert j.observe_only is True

    def test_observe_not_triggered(self):
        rule = _rule('trend_observe', price=10.0, direction='above')
        j = unpositioned_engine.evaluate(rule, _quote(9.0))
        assert j.triggered is False


class TestIntentRouting:
    def test_position_intent_not_handled_here(self):
        rule = _rule('exit_stop', price=9.0, direction='below')
        j = unpositioned_engine.evaluate(rule, _quote(8.5))
        assert j.triggered is False
        assert j.reason == 'not_unpositioned_intent'

    def test_add_position_not_handled_here(self):
        rule = _rule('add_position', price=9.0, direction='below')
        j = unpositioned_engine.evaluate(rule, _quote(8.5))
        assert j.triggered is False
        assert j.reason == 'not_unpositioned_intent'
