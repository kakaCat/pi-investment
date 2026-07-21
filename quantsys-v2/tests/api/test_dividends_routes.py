"""
分红数据 API 路由测试
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from adapters.inbound.api.server import create_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestDividendsRoutes:
    @patch('api.routes.dividends.service')
    def test_get_dividends_success(self, mock_service, client):
        """Test GET /api/stock/{symbol}/dividends"""
        # Mock service response
        mock_service.get_stock_dividends.return_value = {
            "success": True,
            "symbol": "000001.SH",
            "dividends": [
                {"year": 2025, "dividend": 10.5, "yield": 3.2}
            ]
        }

        response = client.get('/api/stock/000001.SH/dividends?years=5')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["symbol"] == "000001.SH"
        assert "dividends" in data
        mock_service.get_stock_dividends.assert_called_once_with("000001.SH", 5)

    @patch('api.routes.dividends.service')
    def test_get_dividends_default_years(self, mock_service, client):
        """Test default years parameter"""
        # Mock service response
        mock_service.get_stock_dividends.return_value = {
            "success": True,
            "symbol": "000001.SH",
            "dividends": []
        }

        response = client.get('/api/stock/000001.SH/dividends')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        mock_service.get_stock_dividends.assert_called_once_with("000001.SH", 10)

    @patch('api.routes.dividends.service')
    def test_screen_dividends_success(self, mock_service, client):
        """Test POST /api/dividends/screen"""
        # Mock service response
        mock_service.screen_dividend_stocks.return_value = {
            "success": True,
            "stocks": [
                {"symbol": "000001.SH", "name": "浦发银行", "yield": 3.5}
            ]
        }

        payload = {
            "min_yield": 3.0,
            "min_years": 3,
            "limit": 10
        }
        response = client.post(
            '/api/dividends/screen',
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "stocks" in data
        mock_service.screen_dividend_stocks.assert_called_once_with(payload)

    @patch('api.routes.dividends.service')
    def test_dividend_calendar_success(self, mock_service, client):
        """Test GET /api/dividends/calendar"""
        # Mock service response
        mock_service.get_dividend_calendar.return_value = {
            "success": True,
            "event_type": "除权除息日",
            "events": []
        }

        response = client.get(
            '/api/dividends/calendar?start_date=2026-06-01&end_date=2026-06-30&event=ex_dividend'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["event_type"] == "除权除息日"
        mock_service.get_dividend_calendar.assert_called_once_with(
            "2026-06-01", "2026-06-30", "ex_dividend"
        )

    def test_dividend_calendar_missing_params(self, client):
        """Test calendar with missing required params"""
        response = client.get('/api/dividends/calendar')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data
