"""t3 验收用例：持仓类判定 position_engine（FR-4，architecture.md IF-4）

覆盖：
- 四操作（增仓/止盈/止损/减仓）在持仓状态触发时各自产出 triggered
- 止损 fail-open：确认空仓仍判定且留 state_mismatch（不漏真止损）
- 非持仓类 intent 不在此模块处理
- 空仓时增仓/止盈/减仓不判
"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2 import position_engine


def _rule(intent, price=10.0, direction='above', state='holding', rid=1, cost=None):
    cond = {'type': 'price_break', 'params': {'price': price, 'direction': direction}}
    rule = SimpleNamespace(
        id=rid,
        symbol='300750.SZ',
        intent=intent,
        conditions=[cond],
        position_state=state,
        cost_price=cost,
    )
    return rule


def _quote(price):
    return SimpleNamespace(symbol='300750.SZ', price=price, prev_close=price, change_pct=0.0)


def _ctx(rule):
    from qs_watch.application.services.watch_engine.rules.conditions import EvalContext
    return EvalContext(cost_price=getattr(rule, 'cost_price', None))


class TestPositionIntents:
    def test_add_position_triggers_when_holding(self):
        rule = _rule('add_position', price=9.5, direction='below')
        j = position_engine.evaluate(rule, _quote(9.4), ctx=_ctx(rule))
        assert j.triggered is True
        assert j.intent == 'add_position'
        assert len(j.hit_conditions) == 1

    def test_exit_take_profit_triggers(self):
        rule = _rule('exit_take_profit', price=12.0, direction='above')
        j = position_engine.evaluate(rule, _quote(12.5), ctx=_ctx(rule))
        assert j.triggered is True
        assert j.intent == 'exit_take_profit'

    def test_exit_stop_triggers(self):
        rule = _rule('exit_stop', price=9.0, direction='below')
        j = position_engine.evaluate(rule, _quote(8.8), ctx=_ctx(rule))
        assert j.triggered is True
        assert j.intent == 'exit_stop'

    def test_exit_reduce_triggers(self):
        rule = _rule('exit_reduce', price=11.0, direction='above')
        j = position_engine.evaluate(rule, _quote(11.2), ctx=_ctx(rule))
        assert j.triggered is True
        assert j.intent == 'exit_reduce'


class TestStopLossFailOpen:
    def test_stop_loss_triggers_even_when_flat(self):
        """止损 + 确认空仓：持仓状态可能滞后 → fail-open 照常判定 + 留痕。"""
        rule = _rule('exit_stop', price=9.0, direction='below', state='none')
        j = position_engine.evaluate(rule, _quote(8.5), ctx=_ctx(rule))
        assert j.triggered is True
        assert j.state_mismatch == position_engine.MISMATCH_STOP_WITHOUT_HOLDING

    def test_stop_loss_triggers_when_state_unknown(self):
        rule = _rule('exit_stop', price=9.0, direction='below', state=None)
        j = position_engine.evaluate(rule, _quote(8.5), ctx=_ctx(rule))
        assert j.triggered is True
        assert j.state_mismatch == position_engine.MISMATCH_UNREADABLE

    def test_stop_loss_not_triggered_no_mismatch_event(self):
        """未触发时即便状态不一致也不标记（避免每拍刷事件淹没真异常）。"""
        rule = _rule('exit_stop', price=9.0, direction='below', state='none')
        j = position_engine.evaluate(rule, _quote(9.9), ctx=_ctx(rule))
        assert j.triggered is False
        # state_mismatch 仅在真触发时有意义（调用方据此留痕）
        assert j.reason == 'no_condition_hit'


class TestNonPositionHandling:
    def test_non_position_intent_ignored(self):
        rule = _rule('entry', price=10.0, direction='above')
        j = position_engine.evaluate(rule, _quote(10.5), ctx=_ctx(rule))
        assert j.triggered is False
        assert j.reason == 'not_position_intent'

    def test_add_position_skipped_when_flat(self):
        rule = _rule('add_position', price=9.5, direction='below', state='none')
        j = position_engine.evaluate(rule, _quote(9.4), ctx=_ctx(rule))
        assert j.triggered is False
        assert j.reason == 'not_holding'

    def test_take_profit_skipped_when_flat(self):
        rule = _rule('exit_take_profit', price=12.0, direction='above', state='none')
        j = position_engine.evaluate(rule, _quote(12.5), ctx=_ctx(rule))
        assert j.triggered is False
        assert j.reason == 'not_holding'

    def test_reduce_skipped_when_flat(self):
        rule = _rule('exit_reduce', price=11.0, direction='above', state='none')
        j = position_engine.evaluate(rule, _quote(11.2), ctx=_ctx(rule))
        assert j.triggered is False
        assert j.reason == 'not_holding'
