"""分红端点 symbol 格式校验（2026-09-13，w-32314d00，看板事件 a80adf91 / f089ee31 / 5f0ac25a）。

背景：GET /api/stock/INVALID/dividends 原先不做任何校验 → 扇出到全部数据源 → 每个源各报一次错，
产生 ERROR 级日志并被采集为错误事件（实测 9 次/日、连续 3 天），而响应还是 HTTP 200。
本组用例锁定：非 A 股代码在入口被拒（400），且不触达数据源管理器。
"""
import pytest
from fastapi.responses import JSONResponse

from adapters.inbound.fastapi_app.routes import dividends_async


@pytest.mark.parametrize("raw,expected", [
    ('600519', '600519'),
    ('600519.SH', '600519'),
    ('000001.sz', '000001'),
    ('300750', '300750'),
])
def test_valid_a_share_codes_normalized(raw, expected):
    assert dividends_async._normalize_a_symbol(raw) == expected


@pytest.mark.parametrize("raw", [
    'INVALID', '', '60051', '6005199', 'ABCDEF', 'sh600519', '600519.XX', None,
])
def test_invalid_symbols_rejected(raw):
    assert dividends_async._normalize_a_symbol(raw) is None


def test_route_rejects_invalid_symbol_without_calling_providers(monkeypatch):
    def _boom():
        raise AssertionError('非法 symbol 不应触达数据源管理器（否则又刷 ERROR 日志）')

    monkeypatch.setattr(dividends_async, 'get_data_provider_manager', _boom)
    resp = dividends_async.get_dividends('INVALID', years=3)
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 400


def test_route_accepts_valid_symbol_and_passes_normalized_code(monkeypatch):
    seen = {}

    class _Mgr:
        def get_dividends(self, symbol, years=5):
            seen["symbol"] = symbol
            seen["years"] = years
            return {'success': True}

    monkeypatch.setattr(dividends_async, 'get_data_provider_manager', lambda: _Mgr())
    out = dividends_async.get_dividends('600519.SH', years=7)
    assert out == {'success': True}
    assert seen == {'symbol': '600519', 'years': 7}
