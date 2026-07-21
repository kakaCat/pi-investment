"""
测试批量回测端点
"""
import pytest
from datetime import datetime
from adapters.inbound.api.server import app


@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_strategy():
    """Sample strategy for testing"""
    return {
        'id': 1,
        'strategy_name': 'Test Strategy',
        'code_type': 'indicator',
        'code_content': '''
# Simple RSI strategy
df['rsi'] = ta.rsi(df['close'], length=14)
df['buy'] = df['rsi'] < 30
df['sell'] = df['rsi'] > 70
''',
        'parsed_params': [
            {'name': 'rsi_low', 'value': 30, 'type': 'int'},
            {'name': 'rsi_high', 'value': 70, 'type': 'int'}
        ],
        'validation_status': 'valid',
        'is_active': True
    }


def test_batch_backtest_success(client, sample_strategy):
    """测试批量回测成功场景"""
    payload = {
        "jobs": [
            {
                "strategy_id": sample_strategy['id'],
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "initial_capital": 100000
            },
            {
                "strategy_id": sample_strategy['id'],
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }
        ],
        "initial_capital": 1000000
    }

    response = client.post('/api/backtest/batch', json=payload)

    assert response.status_code == 200
    data = response.json
    assert data['success'] is True
    assert 'summary' in data['data']
    assert data['data']['summary']['total'] == 2
    assert len(data['data']['results']) <= 2
    assert 'best' in data['data']['summary']
    assert 'worst' in data['data']['summary']


def test_batch_backtest_empty_jobs(client):
    """测试空任务列表"""
    response = client.post('/api/backtest/batch', json={"jobs": []})
    assert response.status_code == 400
    assert 'jobs 不能为空' in response.json['error']


def test_batch_backtest_partial_failure(client, sample_strategy):
    """测试部分任务失败场景"""
    payload = {
        "jobs": [
            {
                "strategy_id": sample_strategy['id'],
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            },
            {
                "strategy_id": 99999,  # 不存在的策略
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }
        ]
    }

    response = client.post('/api/backtest/batch', json=payload)

    assert response.status_code == 200
    data = response.json
    assert data['success'] is True
    assert data['data']['summary']['total'] == 2
    assert data['data']['summary']['errors'] >= 1
    assert data['data']['errors'] is not None
    assert len(data['data']['errors']) >= 1


def test_batch_backtest_invalid_strategy(client):
    """测试不存在的策略"""
    payload = {
        "jobs": [{
            "strategy_id": 99999,
            "symbol": "000001",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31"
        }]
    }

    response = client.post('/api/backtest/batch', json=payload)

    assert response.status_code == 200
    data = response.json
    assert data['success'] is True
    assert data['data']['summary']['total'] == 1
    assert data['data']['summary']['errors'] == 1
    assert data['data']['errors'] is not None
    assert len(data['data']['errors']) == 1
    error_msg = data['data']['errors'][0]['error'].lower()
    assert '策略' in data['data']['errors'][0]['error'] or 'not found' in error_msg or 'strategy' in error_msg
