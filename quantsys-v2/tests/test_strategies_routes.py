"""Tests for strategies routes"""
import pytest
from unittest.mock import patch, Mock
from adapters.inbound.api.server import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_validate_strategies_endpoint(client):
    """Test POST /api/strategies/validate endpoint"""
    # Mock the validation service
    with patch('api.routes.strategies.validation_service') as mock_service:
        mock_service.validate_all_strategies.return_value = {
            'total': 2,
            'passed': 1,
            'failed': 1,
            'duration': 120,
            'details': [
                {
                    'strategy_id': 1,
                    'strategy_name': 'Strategy A',
                    'score': 68.5,
                    'status': 'passed',
                    'metrics': {
                        'annual_return': 0.15,
                        'sharpe_ratio': 1.5,
                        'max_drawdown': -0.20,
                        'win_rate': 0.60,
                        'profit_factor': 2.0
                    },
                    'backtest_count': 400,
                    'error_count': 5
                },
                {
                    'strategy_id': 2,
                    'strategy_name': 'Strategy B',
                    'score': 42.3,
                    'status': 'failed',
                    'metrics': {
                        'annual_return': -0.05,
                        'sharpe_ratio': 0.3,
                        'max_drawdown': -0.30,
                        'win_rate': 0.40,
                        'profit_factor': 0.8
                    },
                    'backtest_count': 395,
                    'error_count': 10
                }
            ]
        }

        # Act
        response = client.post('/api/strategies/validate', json={
            'startDate': '2024-05-27',
            'endDate': '2026-05-27',
            'threshold': 60,
            'dryRun': False
        })

        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['total'] == 2
        assert data['data']['passed'] == 1
        assert data['data']['failed'] == 1
