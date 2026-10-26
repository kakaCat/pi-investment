"""sidecar 盘中/盘后分段（REQ-261021194640-69b8 FR-4，卡 t-3ef50b）

判据：交易日 16:30 → 盘后段跑消息扫描与日报；盘中 → 只跑盘中段（不触发日报）；
非交易日 → 一段都不跑；盘后段不重复执行回填/生命周期等日频任务。
"""
from datetime import datetime

from qs_watch.application.services.watch_engine.engine import WatchEngine

WED = datetime(2026, 10, 21)   # 周三
SUNDAY = datetime(2026, 10, 25)


class FakeNews:
    def __init__(self):
        self.calls = []

    def scan(self, now):
        self.calls.append(now)
        return {'scanned': True, 'reported': 1, 'details': []}


class FakeBackfill:
    def __init__(self):
        self.calls = 0

    def backfill(self, now):
        self.calls += 1
        return {'filled': 1, 'failed': 0}


def _engine(news, backfill=None, review_calls=None):
    eng = object.__new__(WatchEngine)
    eng.news_watch_service = news
    eng.outcome_backfill_service = backfill
    eng.digest_service = None
    eng.meta_review_service = None
    eng.position_lifecycle_service = None
    eng.market_watch_service = None
    eng.pool_watch_service = None
    eng._last_meta_scan_date = None
    eng._last_lifecycle_date = None
    eng._last_held_map_date = None
    eng._last_outcome_backfill_date = None
    eng._last_pool_sync_date = None
    eng._last_review_sent_date = None
    eng._send_daily_review = lambda now: (review_calls.append(now) if review_calls is not None else None)
    return eng


def test_after_close_runs_news_and_daily_review():
    news, reviews = FakeNews(), []
    eng = _engine(news, review_calls=reviews)
    eng._run_sidecar(WED.replace(hour=16, minute=30))

    assert len(news.calls) == 1, '盘后必须扫消息'
    assert len(reviews) == 1, '盘后日报一日一次'


def test_intraday_does_not_send_daily_review():
    news, reviews = FakeNews(), []
    eng = _engine(news, review_calls=reviews)
    eng._run_sidecar(WED.replace(hour=10, minute=0))

    assert len(news.calls) == 1
    assert reviews == [], '盘中不发收盘日报'


def test_non_trading_day_does_nothing():
    news, reviews = FakeNews(), []
    eng = _engine(news, review_calls=reviews)
    eng._run_sidecar(SUNDAY.replace(hour=16, minute=30))

    assert news.calls == []
    assert reviews == []


def test_offhours_does_not_run_daily_backfill():
    news, reviews = FakeNews(), []
    backfill = FakeBackfill()
    eng = _engine(news, backfill, reviews)
    eng._run_sidecar(WED.replace(hour=16, minute=30))

    assert backfill.calls == 0, '盘后段不改动其它日频任务节奏'


def test_daily_review_once_per_day():
    news, reviews = FakeNews(), []
    eng = _engine(news, review_calls=reviews)
    eng._run_sidecar(WED.replace(hour=16, minute=30))
    eng._run_sidecar(WED.replace(hour=17, minute=0))

    assert len(reviews) == 1
