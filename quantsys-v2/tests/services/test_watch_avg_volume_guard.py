"""均量取数保护（2026-09-11，w-aebfddcd）

外部 K 线降级链离线时单 tick 实测 127s（60s 的 tick 被拖成两分钟）。
现在：按日缓存 + 硬超时 + 失败熔断 + 在途去重，取不到就快速放弃、绝不拖住 tick。
"""
import time
from datetime import datetime, timedelta

from application.services.watch_engine.engine import WatchEngine
from tests.services.test_watch_engine import FakeNotifier, FakeQuoteService


class _Repo:
    def list_enabled(self):
        return []


class _CountingProvider:
    def __init__(self, value=1_000_000, delay=0.0, boom=False):
        self.value, self.delay, self.boom = value, delay, boom
        self.calls = 0

    def __call__(self, symbol):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.boom:
            raise RuntimeError('provider down')
        return self.value


NOW = datetime(2026, 9, 11, 10, 0)


def _engine(provider, monkeypatch, timeout='0.2', ttl='60', breaker='3'):
    monkeypatch.setenv('WATCH_AVG_VOLUME_TIMEOUT_SEC', timeout)
    monkeypatch.setenv('WATCH_AVG_VOLUME_FAIL_TTL_SEC', ttl)
    monkeypatch.setenv('WATCH_AVG_VOLUME_BREAKER_N', breaker)
    eng = WatchEngine(rule_repo=_Repo(), quote_service=FakeQuoteService({}),
                      notifier=FakeNotifier(), avg_volume_provider=provider)
    eng.now_fn = lambda: NOW
    return eng


def test_cache_avoids_repeated_calls(monkeypatch):
    p = _CountingProvider()
    eng = _engine(p, monkeypatch)
    assert eng._get_avg_volume('600519.SH') == 1_000_000
    assert eng._get_avg_volume('600519.SH') == 1_000_000
    assert p.calls == 1, '同日重复取数未命中缓存'


def test_cache_resets_on_new_day(monkeypatch):
    p = _CountingProvider()
    eng = _engine(p, monkeypatch)
    eng._get_avg_volume('600519.SH')
    eng.now_fn = lambda: NOW + timedelta(days=1)
    eng._get_avg_volume('600519.SH')
    assert p.calls == 2, '跨日缓存未失效'


def test_slow_provider_does_not_stall_tick(monkeypatch):
    p = _CountingProvider(delay=5.0)
    eng = _engine(p, monkeypatch)
    t0 = time.monotonic()
    assert eng._get_avg_volume('600519.SH') is None
    assert time.monotonic() - t0 < 1.0, '超时未生效：tick 会被外部源拖住'


def test_failure_ttl_blocks_retry(monkeypatch):
    p = _CountingProvider(boom=True)
    eng = _engine(p, monkeypatch)
    assert eng._get_avg_volume('600519.SH') is None
    assert eng._get_avg_volume('600519.SH') is None
    assert p.calls == 1, '失败后未进入 TTL 静默期，每 tick 都在撞同一堵墙'


def test_breaker_trips_after_consecutive_failures(monkeypatch):
    p = _CountingProvider(delay=5.0)
    eng = _engine(p, monkeypatch, breaker='2')
    for sym in ('600519.SH', '000001.SZ'):
        eng._get_avg_volume(sym)
    calls_before = p.calls
    assert eng._get_avg_volume('600036.SH') is None
    assert p.calls == calls_before, '熔断后仍去请求外部源'


def test_provider_none_returns_none(monkeypatch):
    eng = WatchEngine(rule_repo=_Repo(), quote_service=FakeQuoteService({}),
                      notifier=FakeNotifier(), avg_volume_provider=None)
    assert eng._get_avg_volume('600519.SH') is None


def test_tick_completes_fast_with_dead_provider(monkeypatch):
    """端到端护栏：供应商挂死时，整个 tick 仍在秒级内完成"""
    from tests.services.test_watch_engine import make_rule
    p = _CountingProvider(delay=5.0)
    monkeypatch.setenv('WATCH_AVG_VOLUME_TIMEOUT_SEC', '0.2')
    eng = WatchEngine(rule_repo=type('R', (), {'list_enabled': lambda self: [make_rule()]})(),
                      quote_service=FakeQuoteService({'600519.SH': 99.0}),
                      notifier=FakeNotifier(), avg_volume_provider=p)
    eng.now_fn = lambda: NOW
    t0 = time.monotonic()
    eng.tick()
    assert time.monotonic() - t0 < 2.0, 'tick 被均量取数拖慢'