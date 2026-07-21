"""
Tests for GET /api/stock/<symbol>/data-health
"""
import json
from unittest.mock import patch
import pytest

from adapters.inbound.api.server import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestDataHealthAPI:
    def test_data_health_valid_symbol(self, client):
        with patch('application.services.stock_code_validator.StockCodeValidator') as MockValidator:
            MockValidator.return_value.validate.return_value = {
                'valid': True,
                'exists': True,
                'has_recent_data': True,
                'data_summary': {
                    'first_date': '2020-01-02',
                    'last_date': '2026-07-18',
                    'total_records': 1200,
                    'days_since_update': 1
                },
                'suggestions': [],
                'similar_codes': []
            }

            response = client.get('/api/stock/600519/data-health')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['data']['valid'] is True
            assert data['data']['exists'] is True
            assert data['data']['has_recent_data'] is True
            assert data['data']['data_summary']['total_records'] == 1200

    def test_data_health_invalid_symbol(self, client):
        with patch('application.services.stock_code_validator.StockCodeValidator') as MockValidator:
            MockValidator.return_value.validate.return_value = {
                'valid': False,
                'exists': False,
                'has_recent_data': False,
                'data_summary': {
                    'first_date': None,
                    'last_date': None,
                    'total_records': 0,
                    'days_since_update': 999
                },
                'suggestions': ['该股票代码不存在或尚未录入数据'],
                'similar_codes': []
            }

            response = client.get('/api/stock/999999/data-health')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['data']['valid'] is False
            assert data['data']['exists'] is False
