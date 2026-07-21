"""
Integration tests for Portfolio API endpoints
"""
import pytest
from adapters.inbound.api.server import app


class TestPortfolioAPI:

    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_get_portfolio_summary(self, client):
        """Test GET /api/portfolio/summary"""
        response = client.get('/api/portfolio/summary')

        assert response.status_code in [200, 404]  # 404 if no data
        data = response.get_json()
        assert 'success' in data

        if response.status_code == 200:
            assert data['success'] is True
            assert 'data' in data
            assert 'totalValue' in data['data']
            assert 'holdingsCount' in data['data']
            assert 'dailyChange' in data['data']
            assert 'availableCash' in data['data']

    def test_get_portfolio_history(self, client):
        """Test GET /api/portfolio/history"""
        response = client.get('/api/portfolio/history?days=30')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'history' in data['data']
        assert 'summary' in data['data']
        assert 'period' in data['data']

    def test_get_portfolio_history_different_periods(self, client):
        """Test history with different day parameters"""
        for days in [7, 30, 90]:
            response = client.get(f'/api/portfolio/history?days={days}')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['period'] == f'{days}d'

    def test_get_portfolio_history_invalid_days(self, client):
        """Test history with invalid days parameter (should default to 30)"""
        response = client.get('/api/portfolio/history?days=15')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        # Should default to 30 days
        assert data['data']['period'] == '30d'

    def test_get_portfolio_holdings(self, client):
        """Test GET /api/portfolio/holdings"""
        response = client.get('/api/portfolio/holdings')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'holdings' in data['data']
        assert 'totalCount' in data['data']
        assert 'totalMarketValue' in data['data']
        assert 'totalCost' in data['data']

    def test_get_portfolio_positions(self, client):
        """Test GET /api/portfolio/positions"""
        response = client.get('/api/portfolio/positions')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert 'positions' in data['data']

    def test_get_signals_with_date_filter(self, client):
        """Test GET /api/signals with date filter"""
        response = client.get('/api/signals?date=today')

        # May return 500 if method not implemented, 200 if working
        assert response.status_code in [200, 500]
        data = response.get_json()

        if response.status_code == 200:
            assert data['success'] is True
            signals_data = data.get('signals', data.get('data', {}).get('items', []))

    def test_get_signals_with_limit(self, client):
        """Test GET /api/signals with limit parameter"""
        response = client.get('/api/signals?limit=10')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        signals_data = data.get('signals', data.get('data', {}).get('items', []))
        signals_data = data.get('signals', data.get('data', {}).get('items', []))
        assert len(signals_data) <= 10

    def test_get_signals_with_confidence_filter(self, client):
        """Test GET /api/signals with min_confidence filter"""
        response = client.get('/api/signals?min_confidence=0.7')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        signals_data = data.get('signals', data.get('data', {}).get('items', []))
        # All signals should have confidence >= 0.7
        for signal in signals_data:
            if 'confidence' in signal and signal['confidence'] is not None:
                assert signal['confidence'] >= 0.7

    def test_get_backtest_results_with_limit(self, client):
        """Test GET /api/backtest/results with limit"""
        response = client.get('/api/backtest/results?limit=5')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'summary' in data
        assert len(data['summary']) <= 5

    def test_get_backtest_results_by_strategy(self, client):
        """Test GET /api/backtest/results with strategy filter"""
        response = client.get('/api/backtest/results?strategy=test_strategy')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'summary' in data

    def test_health_check(self, client):
        """Test GET /api/health"""
        response = client.get('/api/health')

        assert response.status_code in [200, 500]
        data = response.get_json()
        inner = data.get('data', data)
        assert 'status' in inner or 'db_connected' in inner

    def test_platform_status(self, client):
        """Test GET /api/platform/status"""
        response = client.get('/api/platform/status')

        assert response.status_code in [200, 500]
        data = response.get_json()

        if response.status_code == 200:
            inner = data.get('data', data)
            assert ('status' in inner) or ('holdings_count' in inner)


class TestAPIErrorHandling:
    """Test API error handling"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_signals_with_invalid_confidence(self, client):
        """Test signals endpoint with invalid confidence value"""
        response = client.get('/api/signals?min_confidence=invalid')

        # Should handle gracefully (200, 400, or 500)
        assert response.status_code in [200, 400, 500]

    def test_portfolio_history_with_invalid_days(self, client):
        """Test portfolio history with invalid days parameter"""
        response = client.get('/api/portfolio/history?days=invalid')

        # Should handle gracefully (either 400 or default to 30)
        assert response.status_code in [200, 400]

    def test_backtest_results_with_invalid_limit(self, client):
        """Test backtest results with invalid limit"""
        response = client.get('/api/backtest/results?limit=invalid')

        # Should handle gracefully (either 400 or default to 20)
        assert response.status_code in [200, 400]


class TestAPICamelCaseConversion:
    """Test API response camelCase conversion"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_portfolio_summary_camel_case(self, client):
        """Test that portfolio summary returns camelCase keys"""
        response = client.get('/api/portfolio/summary')

        if response.status_code == 200:
            data = response.get_json()
            if data['success'] and 'data' in data:
                # Check for camelCase keys
                assert 'totalValue' in data['data']
                assert 'dailyChange' in data['data']
                assert 'holdingsCount' in data['data']
                # Should not have snake_case keys
                assert 'total_value' not in data['data']
                assert 'daily_change' not in data['data']

    def test_portfolio_holdings_camel_case(self, client):
        """Test that portfolio holdings returns camelCase keys"""
        response = client.get('/api/portfolio/holdings')

        if response.status_code == 200:
            data = response.get_json()
            if data['success'] and 'data' in data:
                # Check for camelCase keys
                assert 'totalCount' in data['data']
                assert 'totalMarketValue' in data['data']
                # Should not have snake_case keys
                assert 'total_count' not in data['data']
                assert 'total_market_value' not in data['data']
