"""quote FastAPI 路由诊断测试"""
import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.stock_async import (
    router,
    _quote_failure_suggestion,
)
from adapters.outbound.datasources.models import QuoteData


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestQuoteFailureSuggestion:
    def test_hk_5digit_bare_with_network_error(self):
        s = _quote_failure_suggestion('00836', {'sina': 'Read timed out. (read timeout=5)'})
        assert '港股' in s
        assert '00836.HK' in s
        assert '网络型失败' in s
        assert 'source=db' in s

    def test_hk_suffix(self):
        s = _quote_failure_suggestion('00700.HK', {})
        assert '港股' in s
        assert '00700.HK' in s
        assert 'source=db' in s

    def test_a_share_6digit(self):
        s = _quote_failure_suggestion('999999', {})
        assert '已上市/已退市' in s
        assert 'source=db' in s

    def test_unknown_format_fallback(self):
        s = _quote_failure_suggestion('ABC', {})
        assert '代码格式' in s
        assert 'source=db' in s


def _failed_manager_result():
    return {
        'success': False,
        'error': 'All data providers failed',
        'attempted_sources': ['tencent', 'sina', 'eastmoney', 'akshare'],
        'provider_errors': {
            'tencent': '腾讯无 sz00836 数据（代码不存在或该市场不支持）',
            'sina': 'Exception: 新浪财经查询失败: Read timed out. (read timeout=5)',
        },
    }


class TestQuoteRouteDiagnostics:
    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_realtime_failure_returns_diagnostics(self, mock_get_manager, client):
        mock_get_manager.return_value.get_quote.return_value = _failed_manager_result()

        resp = client.get('/api/stock/00836/quote')

        assert resp.status_code == 502
        body = resp.json()
        assert body['success'] is False
        assert 'tencent' in body['error']
        assert body['provider_errors']['tencent'].startswith('腾讯无 sz00836')
        assert '港股' in body['suggestion']
        assert '00836.HK' in body['suggestion']
        assert 'source=db' in body['suggestion']

    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_realtime_success_unchanged(self, mock_get_manager, client):
        quote = QuoteData(
            symbol='600519', name='贵州茅台', price=1294.97, open=1308.0,
            high=1308.0, low=1279.58, prev_close=1297.41, volume=2482400,
            amount=129190000.0, change=-2.44, change_pct=-0.19,
            source='tencent', timestamp='2026-07-27T13:49:39',
        )
        mock_get_manager.return_value.get_quote.return_value = {
            'success': True, 'data': quote, 'source': 'tencent',
        }

        resp = client.get('/api/stock/600519/quote')

        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        assert body['data']['price'] == 1294.97
        assert body['data']['source'] == 'tencent'

    @patch('adapters.inbound.fastapi_app.routes.stock_async._get_db_quote', return_value=None)
    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_auto_failure_after_db_fallback(self, mock_get_manager, mock_db, client):
        mock_get_manager.return_value.get_quote.return_value = _failed_manager_result()

        resp = client.get('/api/stock/00836/quote?source=auto')

        assert resp.status_code == 502
        body = resp.json()
        assert 'provider_errors' in body
        assert 'suggestion' in body
