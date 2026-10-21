"""板块成分快照缓存 + manager 兜底接线测试（2026-10-21）。

锁三条纪律：
1. 只缓存成功且非空的结果（found=False / 空 stocks 不入缓存）；
2. 主源失败时用快照兜底，且如实标注 degraded='cache' + stale_age_sec；
3. 无快照时保持原来的失败返回（不凭空造数据）。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PACKAGES = Path(__file__).resolve().parents[2] / 'packages'
if _PACKAGES.is_dir():
    for _pkg in sorted(_PACKAGES.iterdir()):
        if _pkg.is_dir() and (_pkg / _pkg.name).is_dir() and str(_pkg) not in sys.path:
            sys.path.insert(0, str(_pkg))

from qs_market_data.adapters.outbound.datasources import manager as manager_mod  # noqa: E402
from qs_market_data.adapters.outbound.datasources.sector_constituent_cache import (  # noqa: E402
    SectorConstituentCache,
    set_sector_constituent_cache,
)
from qs_kernel.domain.models.market_data import MarketData  # noqa: E402


def _payload(stocks, found=True, sector='券商'):
    return SimpleNamespace(
        data_type='sector_stocks',
        data={'sector': sector, 'found': found, 'sector_code': 'BK0473',
              'stocks': stocks, 'count': len(stocks)},
        source='eastmoney',
    )


def _ok(stocks, sector='券商'):
    return {'success': True, 'data': _payload(stocks, True, sector),
            'source': 'eastmoney', 'attempted_sources': ['eastmoney']}


def _fail():
    return {'success': False, 'data': None, 'source': None,
            'error': 'All data providers failed',
            'attempted_sources': ['eastmoney'],
            'provider_errors': {'eastmoney': 'ConnectionError'}}


@pytest.fixture
def cache(tmp_path, monkeypatch):
    c = SectorConstituentCache(path=str(tmp_path / 'cache.json'))
    set_sector_constituent_cache(c)
    yield c
    set_sector_constituent_cache(None)


def test_cache_put_get_roundtrip(cache):
    assert cache.put('券商', [{'symbol': '600030', 'name': '中信证券'}], 'eastmoney')
    hit = cache.get('券商')
    assert hit['stocks'][0]['symbol'] == '600030'
    assert hit['source'] == 'eastmoney'
    assert hit['age_sec'] is not None and hit['age_sec'] >= 0


def test_cache_refuses_empty(cache):
    assert cache.put('券商', [], 'eastmoney') is False
    assert cache.get('券商') is None


def test_cache_corrupt_file_is_ignored(cache, tmp_path):
    Path(cache._path).write_text('{not json', encoding='utf-8')
    assert cache.get('券商') is None
    # 坏文件后仍能写入并生效
    assert cache.put('券商', [{'symbol': '600030'}], 'eastmoney')


def test_manager_caches_success_and_serves_on_failure(cache, monkeypatch):
    m = manager_mod.DataProviderManager.__new__(manager_mod.DataProviderManager)
    m.sector_providers = []
    calls = {'n': 0}

    def fake_try(providers, method, *args, **kwargs):
        calls['n'] += 1
        if calls['n'] == 1:
            return _ok([{'symbol': '600030', 'name': '中信证券'}])
        return _fail()

    monkeypatch.setattr(m, '_try_providers', fake_try)

    first = m.get_sector_stocks('券商')
    assert first['success'] and first.get('degraded') is None

    second = m.get_sector_stocks('券商')
    assert second['success'] is True
    assert second['degraded'] == 'cache'
    assert second['source'].startswith('cache:')
    assert second['data'].data['stocks'][0]['symbol'] == '600030'
    assert second['stale_age_sec'] is not None


def test_manager_without_cache_keeps_failure(cache, monkeypatch):
    m = manager_mod.DataProviderManager.__new__(manager_mod.DataProviderManager)
    m.sector_providers = []
    monkeypatch.setattr(m, '_try_providers', lambda *a, **k: _fail())
    result = m.get_sector_stocks('券商')
    assert result['success'] is False


def test_manager_does_not_cache_not_found(cache, monkeypatch):
    m = manager_mod.DataProviderManager.__new__(manager_mod.DataProviderManager)
    m.sector_providers = []
    monkeypatch.setattr(m, '_try_providers', lambda *a, **k: {
        'success': True, 'source': 'eastmoney', 'attempted_sources': ['eastmoney'],
        'data': _payload([], found=False),
    })
    m.get_sector_stocks('不存在板块')
    assert cache.get('不存在板块') is None
