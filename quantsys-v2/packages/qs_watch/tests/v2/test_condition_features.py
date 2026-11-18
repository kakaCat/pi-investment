"""V2 放量条件与两段式伏击在持仓/非持仓中的共享行为。"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.rules.conditions import EvalContext
from qs_watch.application.services.watch_engine.v2 import (
    invalidation,
    position_engine,
    unpositioned_engine,
)
from qs_watch.application.services.watch_engine.v2.archive import TriggerArchive, reset_latch
from qs_watch.application.services.watch_engine.v2.engine import WatchEngineV2
from qs_watch.application.services.watch_engine.v2.evaluation_context import (
    EvaluationContextFactory,
)
from qs_watch.application.services.watch_engine.v2.staged_break_manager import (
    StagedBreakManager,
)

NOW = datetime(2026, 10, 23, 10, 0, 0)
NEXT_DAY = datetime(2026, 10, 26, 10, 0, 0)


@pytest.fixture(autouse=True)
def _clean_latch():
    reset_latch()
    yield
    reset_latch()


def make_rule(intent, conditions, rid=1):
    return SimpleNamespace(
        id=rid,
        symbol='300750.SZ',
        intent=intent,
        conditions=conditions,
        position_state='holding' if intent.startswith('exit_') else 'none',
        account='acct_A',
        cost_price=10.0,
        invalidation_threshold_pct=1000.0,
        trigger_channel='agent',
    )


def quote(price, volume=None):
    return SimpleNamespace(symbol='300750.SZ', price=price, prev_close=10.0, volume=volume)


def evaluate(rule, value, manager):
    if rule.position_state == 'holding':
        return position_engine.evaluate(
            rule, value, position='holding', now=NOW, ctx=EvalContext(),
            staged_manager=manager)
    return unpositioned_engine.evaluate(
        rule, value, now=NOW, ctx=EvalContext(), staged_manager=manager)


@pytest.mark.parametrize('intent', ['exit_stop', 'entry'])
def test_volume_surge_uses_protected_avg_volume_for_both_position_types(intent):
    class AvgVolume:
        def get_avg_volume(self, symbol, now):
            return 1000.0

    rule = make_rule(intent, [{'type': 'volume_surge', 'params': {'multiple': 2.0}}])
    value = quote(10.0, volume=250.0)
    factory = EvaluationContextFactory(avg_volume_evaluator=AvgVolume())
    factory.prepare({rule.symbol: value}, NOW)
    ctx = factory.build(rule, value, NOW)
    if intent == 'exit_stop':
        judgment = position_engine.evaluate(rule, value, position='holding', now=NOW, ctx=ctx)
    else:
        judgment = unpositioned_engine.evaluate(rule, value, now=NOW, ctx=ctx)

    assert ctx.elapsed_fraction == pytest.approx(0.125)
    assert judgment.triggered is True
    assert judgment.hit_conditions[0]['value'] == pytest.approx(2.0)
    assert judgment.degraded is False


@pytest.mark.parametrize('intent', ['exit_stop', 'entry'])
def test_volume_surge_without_avg_volume_is_degraded(intent):
    rule = make_rule(intent, [{'type': 'volume_surge', 'params': {'multiple': 2.0}}])
    value = quote(10.0, volume=250.0)
    judgment = evaluate(rule, value, StagedBreakManager())
    assert judgment.triggered is False
    assert judgment.degraded is True


def staged_condition(window_min=120):
    return {
        'type': 'staged_break',
        'params': {
            'touch': {'price': 10.0, 'direction': 'below'},
            'confirm': {'kind': 'reclaim'},
            'window_min': window_min,
        },
    }


@pytest.mark.parametrize('intent', ['exit_stop', 'entry'])
def test_staged_break_touch_then_reclaim_for_both_position_types(intent):
    rule = make_rule(intent, [staged_condition()])
    manager = StagedBreakManager()

    touched = evaluate(rule, quote(9.5), manager)
    confirmed = evaluate(rule, quote(10.5), manager)

    assert touched.triggered is False
    assert touched.degraded is False
    assert confirmed.triggered is True
    assert '伏击确认' in confirmed.hit_conditions[0]['message']
    assert manager.pending() == 0


def test_staged_break_hold_confirmation_uses_price_history():
    condition = {
        'type': 'staged_break',
        'params': {
            'touch': {'price': 10.0, 'direction': 'below'},
            'confirm': {'kind': 'hold', 'minutes': 30},
        },
    }
    rule = make_rule('entry', [condition])
    manager = StagedBreakManager()
    evaluate(rule, quote(9.5), manager)
    judgment = unpositioned_engine.evaluate(
        rule, quote(9.4), now=NOW + timedelta(minutes=31),
        ctx=EvalContext(price_history=((NOW, 9.5),)), staged_manager=manager)
    assert judgment.triggered is True
    assert '企稳成立' in judgment.hit_conditions[0]['message']


def test_staged_break_volume_confirmation_uses_avg_volume():
    condition = {
        'type': 'staged_break',
        'params': {
            'touch': {'price': 10.0, 'direction': 'below'},
            'confirm': {'kind': 'volume', 'multiple': 1.5},
        },
    }
    rule = make_rule('entry', [condition])
    manager = StagedBreakManager()
    evaluate(rule, quote(9.5), manager)
    judgment = unpositioned_engine.evaluate(
        rule, quote(9.4, volume=2000), now=NOW + timedelta(minutes=1),
        ctx=EvalContext(avg_volume_20d=1000), staged_manager=manager)
    assert judgment.triggered is True
    assert '放量确认' in judgment.hit_conditions[0]['message']


def test_staged_break_expiry_is_suppressed_not_triggered():
    rule = make_rule('entry', [staged_condition(window_min=1)])
    manager = StagedBreakManager()
    evaluate(rule, quote(9.5), manager)

    later = NOW + timedelta(minutes=1)
    judgment = unpositioned_engine.evaluate(
        rule, quote(9.8), now=later, ctx=EvalContext(), staged_manager=manager)

    assert judgment.triggered is False
    assert len(judgment.suppressed_conditions) == 1
    assert '观察窗到期' in judgment.suppressed_conditions[0]['message']


class CycleStore:
    def __init__(self):
        self.count = 0

    def get_cycle_count(self, rule_id):
        return self.count

    def set_cycle_count(self, rule_id, count):
        self.count = count


class TriggerRepo:
    def __init__(self):
        self.rows = []

    def record(self, **kwargs):
        self.rows.append(kwargs)
        return SimpleNamespace(id=len(self.rows))

    def mark_notified(self, trigger_id, notified):
        self.rows[trigger_id - 1]['notified'] = bool(notified)


def test_engine_confirmed_alone_enters_delivery_cycle():
    rule = make_rule('entry', [staged_condition()])
    store = CycleStore()
    triggers = TriggerRepo()
    agent_calls = []
    engine = WatchEngineV2(
        rule_repo=None,
        quote_service=None,
        cycle_store=store,
        agent_sender=lambda *args: agent_calls.append(args) or True,
    )

    first_archive = TriggerArchive(triggers, now=NOW)
    touched = engine.run_chain([rule], {rule.symbol: quote(9.5)},
                               archive=first_archive, now=NOW)
    first_archive.finish()
    assert touched == []
    assert triggers.rows == []
    assert store.count == 0

    second_archive = TriggerArchive(triggers, now=NOW)
    confirmed = engine.run_chain([rule], {rule.symbol: quote(10.5)},
                                 archive=second_archive, now=NOW)
    second_archive.finish()
    assert len(confirmed) == 1
    assert len(agent_calls) == 1
    assert store.count == 1
    assert len(triggers.rows) == 1
    assert triggers.rows[0]['notified'] is True


def test_engine_expiry_archives_without_delivery_or_cycle_count():
    rule = make_rule('entry', [staged_condition(window_min=1)])
    store = CycleStore()
    triggers = TriggerRepo()
    agent_calls = []
    engine = WatchEngineV2(
        rule_repo=None,
        quote_service=None,
        cycle_store=store,
        agent_sender=lambda *args: agent_calls.append(args) or True,
    )

    engine.run_chain([rule], {rule.symbol: quote(9.5)},
                     archive=TriggerArchive(triggers, now=NOW), now=NOW)
    later = NOW + timedelta(minutes=1)
    archive = TriggerArchive(triggers, now=later)
    outcomes = engine.run_chain([rule], {rule.symbol: quote(9.8)},
                                archive=archive, now=later)
    archive.finish()

    assert outcomes == []
    assert agent_calls == []
    assert store.count == 0
    assert len(triggers.rows) == 1
    assert triggers.rows[0]['suppressed'] is True
    assert triggers.rows[0]['notified'] is False


def test_engine_restores_staged_state_and_flushes_cross_day_reset():
    class Store:
        def __init__(self):
            self.saved = None

        def load_staged_states(self):
            return {'1:0': {
                'touch_at': NOW.isoformat(),
                'deadline': (NOW + timedelta(hours=2)).isoformat(),
                'touch_price': 9.5,
            }}

        def save_staged_states(self, states):
            self.saved = states

    store = Store()
    manager = StagedBreakManager(store=store)
    engine = WatchEngineV2(rule_repo=None, quote_service=None, staged_manager=manager)
    assert manager.pending() == 1

    engine.run_chain([], {}, now=NEXT_DAY)
    engine.flush_state()
    assert manager.pending() == 0
    assert store.saved == {}


def test_staged_invalidation_uses_touch_price():
    rule = make_rule('entry', [staged_condition()])
    rule.invalidation_threshold_pct = 10.0
    event = invalidation.check_invalidation(rule, quote(12.0))
    assert event is not None
    assert event.trigger_price == 10.0
