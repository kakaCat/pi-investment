"""GET /api/market/heatmap FastAPI 路由契约测试（TestClient + mock service 层）"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _ok_payload():
    return {
        'success': True,
        'data': {
            'date': '2026-07-24', 'window': 5, 'actual_end_date': '2026-07-31',
            'partial': False, 'scope_degraded': False, 'excluded_count': 0,
            'industries': [{
                'name': '半导体', 'change_pct': 4.2, 'agent_stance': 'bullish',
                'stocks': [{'symbol': '688981', 'name': '中芯国际', 'change_pct': 8.2,
                            'market_cap': 4.5e11, 'in_scope': True,
                            'signals': [{'type': 'buy', 'date': '2026-07-23', 'strategy': 'v13'}]}],
            }],
        },
    }


class TestMarketHeatmapRoute:
    def test_success_data_contract(self, client):
        with patch('application.services.heatmap_service.heatmap_service') as mock_svc:
            mock_svc.get_heatmap.return_value = _ok_payload()
            resp = client.get('/api/market/heatmap', params={'date': '2026-07-24', 'window': 5})
        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        data = body['data']
        assert data['actual_end_date'] == '2026-07-31'
        assert data['scope_degraded'] is False
        assert data['excluded_count'] == 0
        stock = data['industries'][0]['stocks'][0]
        assert stock['change_pct'] == 8.2
        assert stock['market_cap'] == 4.5e11
        assert stock['in_scope'] is True
        assert data['industries'][0]['agent_stance'] == 'bullish'

    def test_default_params(self, client):
        with patch('application.services.heatmap_service.heatmap_service') as mock_svc:
            mock_svc.get_heatmap.return_value = _ok_payload()
            resp = client.get('/api/market/heatmap')
        assert resp.status_code == 200
        mock_svc.get_heatmap.assert_called_once_with(date=None, window=5)

    def test_service_error_returns_success_false(self, client):
        with patch('application.services.heatmap_service.heatmap_service') as mock_svc:
            mock_svc.get_heatmap.return_value = {'success': False, 'error': 'window must be one of (1, 5, 20)'}
            resp = client.get('/api/market/heatmap', params={'window': 7})
        assert resp.status_code == 200
        assert resp.json()['success'] is False
