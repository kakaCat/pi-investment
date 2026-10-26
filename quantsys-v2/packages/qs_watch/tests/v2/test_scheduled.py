"""定时任务编排层（scheduled.py）单测：门、本档过滤、归档闩锁、档位回写。"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.v2 import scheduled, tier

TRADING_AM = datetime(2026, 10, 23, 10, 0, 0)     # 周五盘中
LUNCH = datetime(2026, 10, 23, 12, 0, 0)
SATURDAY = datetime(2026, 10, 24, 10, 0, 0)


@pytest.fixture(autouse=True)
def _reset_latch():
    scheduled.reset_latch()
    yield
    scheduled.reset_latch()


@pytest.fixture
def trading_day(monkeypatch):
    monkeypatch.setattr(scheduled, 'is_trading_day', lambda now=None: True)


def make_rule(rid, tier_sec, price=23.8, symbol=None):
    return SimpleNamespace(
        id=rid, symbol=symbol or f'60000{rid}', watch_tier=tier_sec,
        conditions=[{'type': 'price_break', 'params': {'price': price, 'direction': 'above'}}],
        cost_price=None,
    )


class FakeRepo:
    def __init__(self, rules):
        self.rules = rules
        self.list_calls = []
        self.updated = []

    def list_by_state(self, state):
        self.list_calls.append(state)
        return list(self.rules)

    def update_fields(self, rule_id, **fields):
        self.updated.append((rule_id, fields))
        return None


class FakeQuote:
    def __init__(self, price, prev_close=None):
        self.price = price
        self.prev_close = prev_close


class FakeQuoteService:
    def __init__(self, prices=None):
        self.prices = prices or {}
        self.calls = 0

    def get_realtime_quote(self, symbol):
        self.calls += 1
        return self.prices.get(symbol)


class FakeEngine:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or []
        self.chain_calls = []

    def run_chain(self, rules, quotes):
        self.chain_calls.append((list(rules), dict(quotes)))
        return list(self.outcomes)


class FakeTriggerRepo:
    def __init__(self):
        self.records = []

    def record(self, **kwargs):
        self.records.append(kwargs)
        return SimpleNamespace(id=len(self.records))


# ── 时段门 ─────────────────────────────────────────────────────────────

def test_weekend_is_outside_window():
    assert scheduled.in_watch_window(SATURDAY) is False


def test_lunch_break_is_outside_window(trading_day):
    assert scheduled.in_watch_window(LUNCH) is False


def test_morning_session_is_inside_window(trading_day):
    assert scheduled.in_watch_window(TRADING_AM) is True


def test_scan_outside_session_returns_empty_and_touches_nothing(trading_day):
    repo = FakeRepo([make_rule(1, tier.TIER_FAST)])
    quotes = FakeQuoteService({'600001': FakeQuote(23.8)})
    result = scheduled.scan(tier.TIER_FAST, now=LUNCH, rule_repo=repo,
                            quote_service=quotes, engine=FakeEngine())
    assert result == {'events': [], 'skipped': 'outside_session'}
    assert repo.list_calls == [] and quotes.calls == 0


def test_open_scan_skips_non_trading_day(monkeypatch):
    monkeypatch.setattr(scheduled, 'is_trading_day', lambda now=None: False)
    repo = FakeRepo([make_rule(1, tier.TIER_FAST)])
    quotes = FakeQuoteService({})
    result = scheduled.open_scan(now=SATURDAY, rule_repo=repo, quote_service=quotes)
    assert result == {'events': [], 'skipped': 'not_trading_day'}
    assert repo.list_calls == [] and quotes.calls == 0


# ── 本档过滤 / 档位回写 ────────────────────────────────────────────────

def test_scan_only_queries_own_tier(trading_day):
    fast = make_rule(1, tier.TIER_FAST)
    slow = make_rule(2, tier.TIER_SLOW)
    repo = FakeRepo([fast, slow])
    engine = FakeEngine()
    quotes = FakeQuoteService({'600001': FakeQuote(23.8), '600002': FakeQuote(10.0)})

    result = scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                            quote_service=quotes, engine=engine,
                            trigger_repo=FakeTriggerRepo())

    assert result['scanned'] == 1
    assert [r.id for r in engine.chain_calls[0][0]] == [1]


def test_scan_updates_tier_when_distance_changes(trading_day):
    rule = make_rule(1, tier.TIER_FAST, price=10.0)
    repo = FakeRepo([rule])
    # 现价 10 → 距离 0% → 仍是 30s，不写库
    scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                   quote_service=FakeQuoteService({'600001': FakeQuote(10.0)}),
                   engine=FakeEngine(), trigger_repo=FakeTriggerRepo())
    assert repo.updated == []

    # 现价 20 → 距离 100% → 应改为 1800
    scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                   quote_service=FakeQuoteService({'600001': FakeQuote(20.0)}),
                   engine=FakeEngine(), trigger_repo=FakeTriggerRepo())
    assert repo.updated == [(1, {'watch_tier': tier.TIER_SLOW})]


def test_scan_keeps_tier_when_price_unavailable(trading_day):
    rule = make_rule(1, tier.TIER_FAST)
    repo = FakeRepo([rule])
    scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                   quote_service=FakeQuoteService({}), engine=FakeEngine(),
                   trigger_repo=FakeTriggerRepo())
    assert repo.updated == []


# ── 归档闩锁（持续为真只落一次，回落再武装）──────────────────────────────

def _outcome(rule):
    judgment = SimpleNamespace(
        intent='entry',
        hit_conditions=[{'condition': rule.conditions[0], 'value': 23.9,
                         'message': '上破 23.8'}],
    )
    return ('trigger', rule, judgment, None, None)


def test_archive_is_edge_triggered(trading_day):
    rule = make_rule(1, tier.TIER_FAST)
    repo = FakeRepo([rule])
    trig = FakeTriggerRepo()
    engine = FakeEngine([_outcome(rule)])
    quotes = FakeQuoteService({'600001': FakeQuote(23.9)})

    scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                   quote_service=quotes, engine=engine, trigger_repo=trig)
    scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                   quote_service=quotes, engine=engine, trigger_repo=trig)
    assert len(trig.records) == 1, '条件持续为真，不能每 30 秒写一行'

    engine.outcomes = []                      # 回落 → 解除闩锁
    scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                   quote_service=quotes, engine=engine, trigger_repo=trig)
    engine.outcomes = [_outcome(rule)]        # 再次命中 → 再归档一次
    scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                   quote_service=quotes, engine=engine, trigger_repo=trig)
    assert len(trig.records) == 2


# ── 任务装配 ───────────────────────────────────────────────────────────

def test_build_watch_v2_jobs_names():
    jobs = scheduled.build_watch_v2_jobs()
    assert [j.name for j in jobs] == [
        'watch_open_am', 'watch_open_pm',
        'watch_scan_30s', 'watch_scan_10m', 'watch_scan_30m',
    ]


def test_scan_rejects_invalid_tier():
    with pytest.raises(ValueError):
        scheduled.scan(45)


# ── 心跳（V1 停用后由 V2 宿主维持）──────────────────────────────────────

def test_write_heartbeat_calls_store():
    class Store:
        def __init__(self):
            self.calls = []

        def save_meta(self, **kwargs):
            self.calls.append(kwargs)

    store = Store()
    now = datetime(2026, 10, 23, 10, 0, 0)
    assert scheduled.write_heartbeat(now=now, store=store) is True
    assert store.calls == [{'heartbeat_at': now, 'state_date': now.date()}]


def test_write_heartbeat_failure_is_swallowed():
    class Broken:
        def save_meta(self, **kwargs):
            raise RuntimeError('db down')

    assert scheduled.write_heartbeat(store=Broken()) is False
