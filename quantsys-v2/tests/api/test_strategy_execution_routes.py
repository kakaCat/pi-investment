"""Tests for strategy execution API routes"""
import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create test client"""
    from adapters.inbound.api.server import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_service():
    """Mock StrategyExecutionService"""
    with patch('api.routes.strategy_execution.service') as mock:
        yield mock


def test_execute_single_strategy_api(client, mock_service):
    """测试单股执行 API"""
    mock_service.execute_single.return_value = {
        'signal_id': 'sig_test_123',
        'symbol': '000001.SH',
        'signal_type': 'BUY',
        'confidence': 0.85,
        'entry_price': 1850.0
    }

    response = client.post('/api/strategies/execute',
        json={
            'symbol': '000001.SH',
            'strategy_name': 'turtle',
            'persist': True
        },
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'signal_id' in data['data']
    assert data['data']['symbol'] == '000001.SH'


def test_execute_batch_strategies_api(client, mock_service):
    """测试批量执行 API（NDJSON 流式）"""
    # Mock generator response
    def mock_batch_generator():
        yield {'type': 'signal', 'data': {'symbol': '000001.SH', 'signal_type': 'BUY', 'confidence': 0.85}}
        yield {'type': 'signal', 'data': {'symbol': '000001.SZ', 'signal_type': 'HOLD', 'confidence': 0.55}}
        yield {'type': 'summary', 'data': {'total': 2, 'success': 2, 'failed': 0}}

    mock_service.execute_batch.return_value = mock_batch_generator()

    response = client.post('/api/strategies/batch-execute',
        json={
            'symbols': ['000001.SH', '000001.SZ'],
            'strategy_name': 'turtle'
        },
        content_type='application/json'
    )

    assert response.status_code == 200
    assert response.content_type == 'application/x-ndjson'

    # Parse NDJSON
    lines = response.data.decode('utf-8').strip().split('\n')
    assert len(lines) >= 3  # At least 2 signals + 1 summary

    summary = json.loads(lines[-1])
    assert summary['type'] == 'summary'
    assert summary['data']['total'] == 2


def test_execute_pipeline_api(client, mock_service):
    """测试完整流程 API"""
    mock_service.execute_pipeline.return_value = {
        'execution_date': '2026-05-29',
        'duration_ms': 5800,
        'signals_generated': 48,
        'signals_approved': 35,
        'signals_rejected': 13,
        'orders_created': 35,
        'rejection_reasons': {'仓位超限': 8},
        'orders': []
    }

    response = client.post('/api/strategies/pipeline-execute',
        json={
            'symbols': ['000001.SH'],
            'strategy_name': 'turtle',
            'create_orders': True
        },
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'signals_generated' in data['data']
    assert 'orders_created' in data['data']
