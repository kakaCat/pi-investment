"""行情 TTL 缓存契约锁（2026-09-13，w-adb088f2）

动机（实测）：账户持仓看板整页只依赖一个 host 接口，而它内部每次请求都重新拉实时行情
（0.27s 里占 0.13-0.21s 主项）。看板 15 秒轮询 + 多标签并发 → 实测并发 5 次退化到每次
0.98-1.03s（单发 0.20-0.29s）。

契约：
  ① 同一标的在 TTL 内重复取 → **不再请求 provider**（看板轮询不该反复打外网）；
  ② 只把**未命中**的标的送去 provider（部分批量），命中部分不重取；
  ③ TTL 过期后必须重新取（不得把陈旧价当实时价，R-013）；
  ④ TTL=0 时缓存整体关闭（排查用）；
  ⑤ 空结果不入缓存（否则一次源故障会把"没有数据"缓存下来）。
"""
import time

import pytest

from application.services import realtime_quote_service as rq


class _Quote:
    def __init__(self, symbol, price):
        self.symbol = symbol
        self.price = price
        self.source = 'stub'


class _PM:
    def __init__(self):
        self.calls = []

    def get_quotes(self, symbols):
        self.calls.append(list(symbols))
        return {'success': True, 'data': {s: _Quote(s, 10.0) for s in symbols},
                'missing_symbols': [], 'source': 'stub'}


def _svc():
    svc = rq.RealtimeQuoteService.__new__(rq.RealtimeQuoteService)
    svc.provider_manager = _PM()
    return svc


@pytest.fixture(autouse=True)
def _clean_cache():
    rq.clear_quote_cache()
    yield
    rq.clear_quote_cache()


def test_TTL内重复取不再请求provider():
    svc = _svc()
    svc.get_realtime_quotes(['a', 'b'])
    svc.get_realtime_quotes(['a', 'b'])
    svc.get_realtime_quotes(['a', 'b'])
    assert len(svc.provider_manager.calls) == 1, f'TTL 内应只请求一次，实际 {svc.provider_manager.calls}'


def test_只把未命中的标的送去provider():
    svc = _svc()
    svc.get_realtime_quotes(['a'])
    out = svc.get_realtime_quotes(['a', 'b'])
    assert svc.provider_manager.calls == [['a'], ['b']], '命中部分不得重取，只补缺口'
    assert set(out.keys()) == {'a', 'b'}, '返回必须覆盖全部请求标的（缓存 + 新取）'


def test_过期后必须重新取():
    svc = _svc()
    svc.get_realtime_quotes(['a'])
    # 直接把缓存时间戳拨旧（等价于 TTL 过期），不 sleep
    quote, _ = rq._QUOTE_CACHE['a']
    rq._QUOTE_CACHE['a'] = (quote, time.monotonic() - (rq._QUOTE_CACHE_TTL + 1))
    svc.get_realtime_quotes(['a'])
    assert len(svc.provider_manager.calls) == 2, '过期后必须重取，禁止把陈旧价当实时价'


def test_TTL为0时关闭缓存(monkeypatch):
    monkeypatch.setattr(rq, '_QUOTE_CACHE_TTL', 0.0)
    svc = _svc()
    svc.get_realtime_quotes(['a'])
    svc.get_realtime_quotes(['a'])
    assert len(svc.provider_manager.calls) == 2, 'TTL=0 必须等价于无缓存'


def test_空结果不入缓存():
    svc = _svc()
    svc.provider_manager = _PM()
    svc.provider_manager.get_quotes = lambda symbols: {'success': True, 'data': {}, 'missing_symbols': list(symbols)}
    out = svc.get_realtime_quotes(['a'])
    assert out == {}
    assert rq.quote_cache_stats()['size'] == 0, '源没给数据的标的绝不能进缓存（否则故障被缓存下来）'


def test_缓存统计口径可观测():
    svc = _svc()
    svc.get_realtime_quotes(['a', 'b'])
    stats = rq.quote_cache_stats()
    assert stats['size'] == 2 and stats['fresh'] == 2 and stats['ttl_seconds'] == rq._QUOTE_CACHE_TTL
