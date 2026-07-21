"""
测试策略参数优化端点
"""
import pytest
from unittest.mock import patch, MagicMock
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
        'strategy_name': 'RSI Strategy',
        'code_type': 'indicator',
        'code_content': '''
# RSI strategy with configurable thresholds
df['rsi'] = ta.rsi(df['close'], length=14)
df['buy'] = df['rsi'] < rsi_low
df['sell'] = df['rsi'] > rsi_high
''',
        'parsed_params': [
            {'name': 'rsi_low', 'value': 30, 'type': 'int'},
            {'name': 'rsi_high', 'value': 70, 'type': 'int'}
        ],
        'validation_status': 'valid',
        'is_active': True
    }


def test_optimize_success(client, sample_strategy):
    """测试参数优化成功"""
    # Mock the backtest service to return consistent results
    with patch('services.strategy_code_service.StrategyCodeService.backtest_strategy') as mock_backtest:
        # Return different results for different parameter combinations
        def backtest_side_effect(strategy_id, symbol, start_date, end_date, initial_cash, params_override):
            rsi_low = params_override.get('rsi_low', 30)
            rsi_high = params_override.get('rsi_high', 70)
            # Simulate better performance for rsi_low=30, rsi_high=70
            base_score = 1.5
            if rsi_low == 30 and rsi_high == 70:
                base_score = 2.15
            elif rsi_low == 25 and rsi_high == 75:
                base_score = 1.8

            return {
                'total_return': base_score * 0.1,
                'sharpe_ratio': base_score,
                'max_drawdown': -0.08,
                'win_rate': 0.62,
                'profit_factor': 1.5
            }

        mock_backtest.side_effect = backtest_side_effect

        payload = {
            "strategy_id": sample_strategy['id'],
            "symbol": "000001",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "metric": "sharpe",
            "param_grid": {
                "rsi_low": [25, 30],
                "rsi_high": [70, 75]
            }
        }

        response = client.post('/api/portfolio/strategy-optimize', json=payload)

        assert response.status_code == 200
        data = response.json['data']
        assert data['totalCombinations'] == 4  # 2 * 2
        assert data['successful'] == 4
        assert 'best' in data
        assert 'params' in data['best']
        assert 'score' in data['best']
        assert 'top10' in data
        assert len(data['top10']) <= 10

        # Verify best params (camelCase in response)
        assert data['best']['params']['rsiLow'] == 30
        assert data['best']['params']['rsiHigh'] == 70
        assert data['best']['score'] == 2.15


def test_optimize_combinations_limit(client, sample_strategy):
    """测试组合数限制"""
    payload = {
        "strategy_id": sample_strategy['id'],
        "symbol": "000001",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {
            "param1": list(range(10)),
            "param2": list(range(10)),
            "param3": list(range(10))  # 10*10*10 = 1000 > 50
        },
        "max_combinations": 50
    }

    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 400
    assert '组合过多' in response.json['error']


def test_optimize_missing_strategy_id(client):
    """测试缺少 strategy_id"""
    payload = {
        "symbol": "000001",
        "param_grid": {"rsi_low": [25, 30]}
    }

    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 400
    assert 'strategy_id' in response.json['error']


def test_optimize_missing_symbol(client):
    """测试缺少 symbol"""
    payload = {
        "strategy_id": 1,
        "param_grid": {"rsi_low": [25, 30]}
    }

    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 400
    assert 'symbol' in response.json['error']


def test_optimize_missing_param_grid(client):
    """测试缺少 param_grid"""
    payload = {
        "strategy_id": 1,
        "symbol": "000001"
    }

    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 400
    assert 'param_grid' in response.json['error']


def test_optimize_different_metrics(client, sample_strategy):
    """测试不同的优化指标"""
    with patch('services.strategy_code_service.StrategyCodeService.backtest_strategy') as mock_backtest:
        mock_backtest.return_value = {
            'total_return': 0.25,
            'sharpe_ratio': 1.8,
            'max_drawdown': -0.10,
            'win_rate': 0.65,
            'profit_factor': 1.6,
            'calmar_ratio': 2.5
        }

        for metric in ['sharpe', 'return', 'win_rate', 'calmar']:
            payload = {
                "strategy_id": sample_strategy['id'],
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "metric": metric,
                "param_grid": {
                    "rsi_low": [30],
                    "rsi_high": [70]
                }
            }

            response = client.post('/api/portfolio/strategy-optimize', json=payload)
            assert response.status_code == 200
            data = response.json['data']
            assert data['metric'] == metric
            assert 'best' in data


def test_optimize_all_failures(client, sample_strategy):
    """测试所有组合都失败的情况"""
    with patch('services.strategy_code_service.StrategyCodeService.backtest_strategy') as mock_backtest:
        mock_backtest.side_effect = Exception("Backtest failed")

        payload = {
            "strategy_id": sample_strategy['id'],
            "symbol": "000001",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "metric": "sharpe",
            "param_grid": {
                "rsi_low": [25, 30],
                "rsi_high": [70, 75]
            }
        }

        response = client.post('/api/portfolio/strategy-optimize', json=payload)
        assert response.status_code == 500
        assert '所有参数组合回测均失败' in response.json['error']


def test_optimize_strategy_not_found(client):
    """测试策略不存在"""
    payload = {
        "strategy_id": 99999,
        "symbol": "000001",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {"rsi_low": [25, 30]}
    }

    response = client.post('/api/portfolio/strategy-optimize', json=payload)
    assert response.status_code == 500
    # When strategy doesn't exist, all backtests fail, so we get the "all failed" error
    assert '所有参数组合回测均失败' in response.json['error']
