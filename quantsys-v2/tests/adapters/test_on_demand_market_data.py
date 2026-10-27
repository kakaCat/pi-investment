"""On-demand K-line backfill / factor refresh tests (no network, no DB)."""

import inspect
from datetime import date, datetime

import pytest

from adapters.shared import on_demand_market_data as lazy
from adapters.outbound.repositories.kline_repository import KlineORMRepository


class FakeKlineRepo:
    def __init__(self, latest='2026-10-26', save_dates=None):
        self.latest = latest
        self.saved = []
        self.save_dates = save_dates or []

    def get_latest_trade_date(self, _symbol):
        return self.latest

    def save_daily_klines(self, rows):
        self.saved.extend(rows)
        dates = self.save_dates or [
            row.get('trade_date') or row.get('date') for row in rows
        ]
        dates = [date.fromisoformat(str(d)[:10]) for d in dates if d]
        if dates:
            self.latest = max(dates).isoformat()
        return len(rows)


class FakeFetcher:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def fetch_klines(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        return self.rows


class FakeFactorRepo:
    def __init__(self, factor_date):
        self.factor_date = factor_date

    def get_latest_factors(self, _symbol):
        return [{'factor_name': 'rsi14', 'factor_date': self.factor_date, 'factor_value': 50}]


@pytest.fixture(autouse=True)
def trading_weekdays_only(monkeypatch):
    monkeypatch.setattr(lazy, '_safe_is_trading_day', lambda d: d.weekday() < 5)


def test_repository_latest_trade_date_accepts_optional_symbol():
    params = inspect.signature(KlineORMRepository.get_latest_trade_date).parameters
    assert 'symbol' in params
    assert params['symbol'].default is None


def test_completed_trading_day_uses_previous_day_before_close():
    assert lazy.completed_trading_day(datetime(2026, 10, 28, 10, 0)) == date(2026, 10, 27)
    assert lazy.completed_trading_day(datetime(2026, 10, 28, 16, 0)) == date(2026, 10, 28)
    assert lazy.completed_trading_day(datetime(2026, 11, 1, 10, 0)) == date(2026, 10, 30)


def test_fresh_symbol_does_not_fetch():
    repo = FakeKlineRepo(latest='2026-10-27')
    fetcher = FakeFetcher([{'trade_date': '2026-10-27'}])

    meta = lazy.ensure_daily_klines(
        '600519', '2026-09-01', '2026-10-28', kline_repo=repo,
        now=datetime(2026, 10, 28, 10, 0),
        fetcher_factory=lambda: fetcher,
    )

    assert meta['fresh'] is True
    assert meta['source'] == 'db_cache'
    assert fetcher.calls == []
    assert repo.saved == []


def test_stale_symbol_fetches_only_the_gap_and_persists():
    repo = FakeKlineRepo(latest='2026-10-26')
    fetcher = FakeFetcher([
        {'symbol': '600519', 'trade_date': '2026-10-27', 'close': 100},
    ])

    meta = lazy.ensure_daily_klines(
        '600519.SH', '2026-09-01', '2026-10-28', kline_repo=repo,
        now=datetime(2026, 10, 28, 10, 0),
        fetcher_factory=lambda: fetcher,
    )

    assert meta['fresh'] is True
    assert meta['source'] == 'lazy_fetch'
    assert meta['fetched_bars'] == 1
    assert fetcher.calls == [('600519', '2026-10-27', '2026-10-27')]
    assert len(repo.saved) == 1


def test_empty_upstream_returns_degraded_without_raising():
    repo = FakeKlineRepo(latest=None)
    fetcher = FakeFetcher([])

    meta = lazy.ensure_daily_klines(
        '000001', '2026-01-01', '2026-10-28', kline_repo=repo,
        now=datetime(2026, 10, 28, 10, 0),
        fetcher_factory=lambda: fetcher,
    )

    assert meta['fresh'] is False
    assert meta['degraded'] is True
    assert meta['source'] == 'upstream_empty'
    assert meta['reason'] == 'target_date_not_reached'


def test_disabled_lazy_fetch_returns_degraded_metadata():
    repo = FakeKlineRepo(latest='2026-10-26')

    meta = lazy.ensure_daily_klines(
        '000001', '2026-09-01', '2026-10-28', kline_repo=repo,
        now=datetime(2026, 10, 28, 10, 0), allow_fetch=False,
    )

    assert meta['fresh'] is False
    assert meta['degraded'] is True
    assert meta['source'] == 'disabled'


def test_factor_refresh_computes_when_factor_is_stale():
    kline_repo = FakeKlineRepo(latest='2026-10-27')
    factor_repo = FakeFactorRepo(factor_date='2026-10-26')
    calls = []

    def compute(params):
        calls.append(params)
        factor_repo.factor_date = '2026-10-27'
        return {'status': 'success', 'symbols_count': 1, 'factors_computed': 1}

    meta = lazy.ensure_factor_freshness(
        '600519', kline_repo=kline_repo, factor_repo=factor_repo,
        now=datetime(2026, 10, 28, 10, 0), compute_func=compute,
    )

    assert meta['fresh'] is True
    assert meta['source'] == 'lazy_compute'
    assert calls == [{'symbols': ['600519'], 'workers': 1}]


def test_factor_refresh_is_noop_when_already_fresh():
    kline_repo = FakeKlineRepo(latest='2026-10-27')
    factor_repo = FakeFactorRepo(factor_date='2026-10-27')
    calls = []

    meta = lazy.ensure_factor_freshness(
        '600519', kline_repo=kline_repo, factor_repo=factor_repo,
        now=datetime(2026, 10, 28, 10, 0),
        compute_func=lambda params: calls.append(params) or {},
    )

    assert meta['fresh'] is True
    assert meta['source'] == 'db_cache'
    assert calls == []
