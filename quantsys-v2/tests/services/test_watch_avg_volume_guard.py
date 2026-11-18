"""V2 均量取数保护：缓存、超时、失败 TTL 与熔断。"""
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2.evaluation_context import (
    EvaluationContextFactory,
)
from qs_watch.application.services.watch_engine.v2.rule_evaluator import RuleEvaluator

NOW = datetime(2026, 9, 11, 10, 0)


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


def _evaluator(provider, monkeypatch, timeout='0.2', ttl='60', breaker='3'):
    monkeypatch.setenv('WATCH_AVG_VOLUME_TIMEOUT_SEC', timeout)
    monkeypatch.setenv('WATCH_AVG_VOLUME_FAIL_TTL_SEC', ttl)
    monkeypatch.setenv('WATCH_AVG_VOLUME_BREAKER_N', breaker)
    return RuleEvaluator(avg_volume_provider=provider)


def test_cache_avoids_repeated_calls(monkeypatch):
    provider = _CountingProvider()
    evaluator = _evaluator(provider, monkeypatch)
    assert evaluator.get_avg_volume('600519.SH', NOW) == 1_000_000
    assert evaluator.get_avg_volume('600519.SH', NOW) == 1_000_000
    assert provider.calls == 1


def test_cache_resets_on_new_day(monkeypatch):
    provider = _CountingProvider()
    evaluator = _evaluator(provider, monkeypatch)
    evaluator.get_avg_volume('600519.SH', NOW)
    evaluator.get_avg_volume('600519.SH', NOW + timedelta(days=1))
    assert provider.calls == 2


def test_slow_provider_does_not_stall_evaluation(monkeypatch):
    provider = _CountingProvider(delay=5.0)
    evaluator = _evaluator(provider, monkeypatch)
    started = time.monotonic()
    assert evaluator.get_avg_volume('600519.SH', NOW) is None
    assert time.monotonic() - started < 1.0


def test_failure_ttl_blocks_retry(monkeypatch):
    provider = _CountingProvider(boom=True)
    evaluator = _evaluator(provider, monkeypatch)
    assert evaluator.get_avg_volume('600519.SH', NOW) is None
    assert evaluator.get_avg_volume('600519.SH', NOW) is None
    assert provider.calls == 1


def test_breaker_trips_after_consecutive_failures(monkeypatch):
    provider = _CountingProvider(delay=5.0)
    evaluator = _evaluator(provider, monkeypatch, breaker='2')
    for symbol in ('600519.SH', '000001.SZ'):
        evaluator.get_avg_volume(symbol, NOW)
    calls_before = provider.calls
    assert evaluator.get_avg_volume('600036.SH', NOW) is None
    assert provider.calls == calls_before


def test_provider_none_returns_none():
    evaluator = RuleEvaluator(avg_volume_provider=None)
    assert evaluator.get_avg_volume('600519.SH', NOW) is None


def test_context_build_completes_fast_with_dead_provider(monkeypatch):
    provider = _CountingProvider(delay=5.0)
    evaluator = _evaluator(provider, monkeypatch)
    factory = EvaluationContextFactory(avg_volume_evaluator=evaluator)
    rule = SimpleNamespace(
        symbol='600519.SH', cost_price=100.0,
        conditions=[{'type': 'volume_surge', 'params': {'multiple': 1.5}}])
    started = time.monotonic()
    ctx = factory.build(rule, SimpleNamespace(price=99.0), NOW)
    assert ctx.avg_volume_20d is None
    assert time.monotonic() - started < 2.0
