"""MarketStateProvider 跨请求缓存契约。

计划/盯盘各自构造 provider；若缓存只在实例上，每个请求都会重复拉全市场快照，
线上 /api/plans/today 因而超过 15 秒工具时限。
"""
import pytest

from qs_market_data.adapters.outbound.datasources import market_state_provider as module
from qs_market_data.adapters.outbound.datasources.market_state_provider import (
    MarketStateProvider,
)


class _StubProvider(MarketStateProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = 0

    def _indices(self, degraded):
        return {"000300.SH": {"change_pct": 0.5}}

    def _sentiment(self, degraded):
        self.calls += 1
        return {"score": 50.0, "fear_greed": 50.0, "ad_ratio": 1.0, "volume_ratio": 1.0}

    def _limit_up(self, degraded):
        return {"count": 10, "max_streak": 2}

    def _sectors(self, degraded):
        return {"半导体": 1.5}


@pytest.fixture(autouse=True)
def _clear_shared_cache():
    MarketStateProvider._shared_cache.clear()
    yield
    MarketStateProvider._shared_cache.clear()


def test_cache_is_shared_across_provider_instances(monkeypatch):
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    first = _StubProvider(cache_ttl_sec=60)
    second = _StubProvider(cache_ttl_sec=60)

    state1 = first.get_state()
    state2 = second.get_state()

    assert state2 is state1
    assert first.calls == 1
    assert second.calls == 0


def test_force_and_ttl_refresh_shared_cache(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    first = _StubProvider(cache_ttl_sec=60)

    state1 = first.get_state()
    state2 = first.get_state(force=True)
    assert state2 is not state1
    assert first.calls == 2

    clock[0] = 1059.9
    assert first.get_state() is state2
    assert first.calls == 2

    clock[0] = 1060.1
    state3 = first.get_state()
    assert state3 is not state2
    assert first.calls == 3


def test_different_index_universes_do_not_share_state(monkeypatch):
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    first = _StubProvider(index_codes=("000300.SH",), cache_ttl_sec=60)
    second = _StubProvider(index_codes=("000001.SH",), cache_ttl_sec=60)

    first.get_state()
    second.get_state()

    assert first.calls == 1
    assert second.calls == 1
