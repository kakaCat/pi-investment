"""从 V1 提取到 V2 的市场、持仓、窗口、调档和迟滞能力。"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.v2 import scheduled, tier
from qs_watch.application.services.watch_engine.v2.archive import reset_latch
from qs_watch.application.services.watch_engine.v2.engine import WatchEngineV2
from qs_watch.application.services.watch_engine.v2.evaluation_context import (
    EvaluationContextFactory,
)

NOW = datetime(2026, 10, 23, 10, 0, 0)


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    reset_latch()
    monkeypatch.setattr(scheduled, 'is_trading_day', lambda now=None: True)
    yield
    reset_latch()


class Repo:
    def __init__(self, rules):
        self.rules = list(rules)
        self.count = 0
        self.tiers = []

    def list_by_state(self, state):
        return list(self.rules)

    def get_cycle_count(self, rule_id):
        return self.count

    def set_cycle_count(self, rule_id, count):
        self.count = count

    def update_fields(self, rule_id, **fields):
        for key, value in fields.items():
            setattr(self.rules[0], key, value)
        if 'watch_tier' in fields:
            self.tiers.append(fields['watch_tier'])
        return self.rules[0]


class Triggers:
    def __init__(self):
        self.rows = []

    def record(self, **kwargs):
        self.rows.append(kwargs)
        return SimpleNamespace(id=len(self.rows))

    def mark_notified(self, trigger_id, notified):
        self.rows[trigger_id - 1]['notified'] = bool(notified)


class Quotes:
    def __init__(self, price, volume=None):
        self.price = price
        self.volume = volume
        self.calls = 0

    def get_realtime_quote(self, symbol):
        self.calls += 1
        if self.price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=self.price,
                               prev_close=10.0, volume=self.volume)


def make_rule(intent='entry', **overrides):
    values = dict(
        id=1, symbol='300750.SZ', intent=intent,
        conditions=[{'type': 'price_break', 'params': {'price': 10.0, 'direction': 'above'}}],
        position_state='holding' if intent.startswith('exit_') else 'none',
        account='acct_A', cost_price=10.0, invalidation_threshold_pct=1000.0,
        watch_tier=30, trigger_channel='direct', active_window=None, scope='symbol',
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_market_observation_uses_v2_direct_delivery():
    market_rule = make_rule(intent='trend_observe', id=2, scope='sector', trigger_channel='direct')
    candidate = {
        'rule': market_rule,
        'idx': 0,
        'cond': {'type': 'held_sector_pct', 'params': {'pct': -2.0, 'direction': 'below'}},
        'result': SimpleNamespace(triggered=True, value=-2.5, message='持仓板块跌 2.5%'),
        'quote': SimpleNamespace(symbol='HELD_SECTORS', price=-2.5),
    }

    class Market:
        def scan_market_rules(self, now):
            return {'scanned': 1, 'triggered': 1, 'degraded': [], 'evaluated': [candidate]}

    repo = Repo([])
    triggers = Triggers()
    sent = []
    engine = WatchEngineV2(
        rule_repo=repo, quote_service=None, cycle_store=repo,
        market_watch_service=Market(),
        feishu_sender=lambda title, body: sent.append((title, body)) or True,
    )
    result = scheduled.scan(30, now=NOW, rule_repo=repo,
                            quote_service=Quotes(None), trigger_repo=triggers, engine=engine)

    assert result['market_scanned'] == 1
    assert result['market_triggered'] == 1
    assert result['events'] == 1
    assert result['quotes'] == 0
    assert len(sent) == 1
    assert triggers.rows[0]['notified'] is True
    assert 'duration_ms' in result


def test_active_window_filters_before_quote():
    rule = make_rule(active_window=['09:30-10:00'])
    repo = Repo([rule])
    quotes = Quotes(11.0)
    engine = WatchEngineV2(rule_repo=repo, quote_service=None,
                           feishu_sender=lambda *args: True)
    result = scheduled.scan(30, now=NOW.replace(minute=1), rule_repo=repo,
                            quote_service=quotes, trigger_repo=Triggers(), engine=engine)
    assert result['scanned'] == 0
    assert quotes.calls == 0


def test_flat_stop_still_uses_position_engine_fail_open():
    rule = make_rule(intent='exit_stop', position_state='none', conditions=[
        {'type': 'price_break', 'params': {'price': 9.0, 'direction': 'below'}}])
    repo = Repo([rule])
    engine = WatchEngineV2(rule_repo=repo, quote_service=None, cycle_store=repo,
                           agent_sender=lambda *args: True)
    outcomes = engine.run_chain([rule], {rule.symbol: Quotes(8.8).get_realtime_quote(rule.symbol)})
    judgment = outcomes[0][2]
    assert judgment.triggered is True
    assert judgment.state_mismatch == 'stop_without_holding'


def test_unpriceable_condition_uses_evaluation_distance_for_tier():
    class Avg:
        def get_avg_volume(self, symbol, now):
            return 1000.0

    rule = make_rule(watch_tier=tier.TIER_SLOW, conditions=[
        {'type': 'volume_surge', 'params': {'multiple': 2.0}}])
    repo = Repo([rule])
    engine = WatchEngineV2(
        rule_repo=repo, quote_service=None,
        evaluation_context=EvaluationContextFactory(avg_volume_evaluator=Avg()))
    result = scheduled.scan(tier.TIER_SLOW, now=NOW, rule_repo=repo,
                            quote_service=Quotes(10.0, volume=248.0),
                            trigger_repo=Triggers(), engine=engine)
    assert result['tier_changed'] == 1
    assert rule.watch_tier == tier.TIER_FAST
    assert result['degraded'] == 0


def test_degraded_condition_keeps_current_tier():
    rule = make_rule(watch_tier=tier.TIER_MID, conditions=[
        {'type': 'volume_surge', 'params': {'multiple': 2.0}}])
    repo = Repo([rule])
    engine = WatchEngineV2(rule_repo=repo, quote_service=None)
    result = scheduled.scan(tier.TIER_MID, now=NOW, rule_repo=repo,
                            quote_service=Quotes(10.0, volume=248.0),
                            trigger_repo=Triggers(), engine=engine)
    assert result['tier_changed'] == 0
    assert result['degraded'] == 1
    assert rule.watch_tier == tier.TIER_MID


def test_hysteresis_prevents_rearm_until_leaving_band():
    rule = make_rule()
    repo = Repo([rule])
    triggers = Triggers()
    quotes = Quotes(11.0)
    engine = WatchEngineV2(rule_repo=repo, quote_service=None, cycle_store=repo,
                           feishu_sender=lambda *args: True)

    for price in (11.0, 9.98, 11.0, 9.9, 11.0):
        quotes.price = price
        scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                       quote_service=quotes, trigger_repo=triggers, engine=engine)

    assert len(triggers.rows) == 2


def test_noise_suppression_archives_once_without_delivery():
    rule = make_rule(noise_state='suppressed', suppress_until=NOW.replace(hour=11))
    repo = Repo([rule])
    triggers = Triggers()
    sent = []
    engine = WatchEngineV2(
        rule_repo=repo, quote_service=None, cycle_store=repo,
        agent_sender=lambda *args: sent.append(args) or True,
        feishu_sender=lambda *args: sent.append(args) or True,
    )
    quotes = Quotes(11.0)
    for _ in range(2):
        scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                       quote_service=quotes, trigger_repo=triggers, engine=engine)

    assert sent == []
    assert repo.count == 0
    assert len(triggers.rows) == 1
    assert triggers.rows[0]['suppressed'] is True
    assert triggers.rows[0]['detail']['kind'] == 'noise_suppressed'
