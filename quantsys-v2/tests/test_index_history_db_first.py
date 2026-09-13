"""指数历史取数 DB-first 回归（2026-09-13，w-32314d00，错误事件 222154a8）

事故：2026-09-13 10:59 一次机器级 DNS 抖动（Failed to resolve "finance.sina.com.cn"，
同一分钟 qt.gtimg.cn 亦失败）→ akshare get_index_daily 抛异常 →
"基准指数获取失败: 暂无指数 sh000300 的历史数据" → alpha/beta 基准整段不可用。
而 quant.index_daily 里 000300.SH 的数据当时是好的（且由采集通道每日刷新）。

根因：MarketDataService.get_index_history 只有 provider（外网）一条路，从不读本地库。
修复：加 DB-first 路径（符号经 utils.symbol_classifier.resolve_index_symbol 规范化），
本地有数就不再打外网；本地无数据/规范化失败/读库异常一律回退 provider（行为不变）。
本文件锁定：符号规范化、返回键与 provider 路径一致（date/open/...）、DB 优先、回退。
"""
import logging
from types import SimpleNamespace

import pytest

from application.services.market_data_service import MarketDataService


def _svc() -> MarketDataService:
    """绕过 __init__（避免构造 provider 链），只被测方法需要的 logger。"""
    svc = MarketDataService.__new__(MarketDataService)
    svc.logger = logging.getLogger('test.index_history')
    return svc


class _FakeRepo:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_index_daily_klines(self, index_symbol, start_date, end_date, fields=None):
        self.calls.append((index_symbol, start_date, end_date))
        return self.rows


@pytest.fixture
def patch_repo(monkeypatch):
    def _install(rows):
        repo = _FakeRepo(rows)
        import adapters.outbound.repositories.kline_repository as kr
        monkeypatch.setattr(kr, 'KlineORMRepository', lambda *a, **k: repo)
        return repo
    return _install


def test_sina_style_symbol_is_normalized(patch_repo):
    repo = patch_repo([{"trade_date": "2026-09-11", "open": 1.0, "high": 2.0, "low": 0.5,
                       "close": 1.5, "volume": 100, "amount": 200}])
    rows = _svc()._index_daily_from_db('sh000300', '2026-08-26', '2026-09-11')
    assert repo.calls == [('000300.SH', '2026-08-26', '2026-09-11')]
    assert rows == [{'date': '2026-09-11', 'open': 1.0, 'high': 2.0, 'low': 0.5,
                    'close': 1.5, 'volume': 100, 'amount': 200}]


def test_zero_amount_is_omitted(patch_repo):
    """指数表里 amount=0 表示源未提供（新浪指数接口无成交额列）——不能照搬成“成交额 0”。"""
    patch_repo([{"trade_date": "2026-09-11", "close": 1.5, "volume": 100, "amount": 0.0}])
    rows = _svc()._index_daily_from_db('sh000300', '2026-09-01', '2026-09-11')
    assert 'amount' not in rows[0] and rows[0]['close'] == 1.5


def test_empty_range_defaults_are_wide(patch_repo):
    repo = patch_repo([])
    assert _svc()._index_daily_from_db('000300.SH', '', '') == []
    assert repo.calls == [('000300.SH', '1990-01-01', '2999-12-31')]


def test_non_index_symbol_skips_db(monkeypatch, patch_repo):
    """与指数同码的深市个股 → resolve_index_symbol 返回 None → 不读库、交回 provider 语义。"""
    import utils.symbol_classifier as sc
    monkeypatch.setattr(sc, "resolve_index_symbol", lambda s: None)
    repo = patch_repo([{"trade_date": "2026-09-11", "close": 1.0}])
    assert _svc()._index_daily_from_db('000001', '2026-01-01', '2026-12-31') == []
    assert repo.calls == []


def test_repo_exception_degrades_to_empty(monkeypatch):
    """本地库异常不能阻断取数——返回 [] 让调用方回退 provider。"""
    import adapters.outbound.repositories.kline_repository as kr
    class _Boom:
        def get_index_daily_klines(self, *a, **k):
            raise RuntimeError('db down')
    monkeypatch.setattr(kr, 'KlineORMRepository', lambda *a, **k: _Boom())
    assert _svc()._index_daily_from_db('sh000300', '2026-01-01', '2026-12-31') == []


def test_get_index_history_prefers_db_and_never_calls_provider(monkeypatch):
    svc = _svc()
    db_rows = [{"date": "2026-09-11", "close": 4510.155}]
    monkeypatch.setattr(svc, "_index_daily_from_db", lambda *a, **k: db_rows)
    class _BoomProvider:
        def get_index_daily(self, *a, **k):
            raise AssertionError('DB 有数据时不得打外网')
    svc.provider_manager = _BoomProvider()
    res = svc.get_index_history('sh000300', '2026-08-26', '2026-09-11')
    assert res['success'] is True
    assert res['data']['klines'] == db_rows
    assert res['data']['source'] == 'db:quant.index_daily'


def test_get_index_history_falls_back_to_provider(monkeypatch):
    svc = _svc()
    monkeypatch.setattr(svc, "_index_daily_from_db", lambda *a, **k: [])
    calls = []
    class _Provider:
        def get_index_daily(self, symbol):
            calls.append(symbol)
            return {'success': True, 'data': SimpleNamespace(
                data={'records': [{'date': '2026-09-11', 'close': 1.0}], 'total': 1})}
    svc.provider_manager = _Provider()
    res = svc.get_index_history('sh000300', '2026-08-26', '2026-09-11')
    assert res['success'] is True and calls == ['sh000300']
    assert 'source' not in res['data']      # provider 路径不带 DB 标记，契约保持
