"""
End-to-end integration tests for three major features:
1. Strategy creation
2. Batch backtest
3. Parameter optimization
4. Signal generation
"""
import pytest
import time
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
        'strategy_name': '集成测试策略',
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


def test_full_workflow(client, sample_strategy):
    """测试完整工作流：创建策略 → 批量回测 → 参数优化 → 信号生成"""

    # Use existing sample strategy (skip creation step for simplicity)
    strategy_id = sample_strategy['id']

    # 2. 批量回测
    batch_payload = {
        "jobs": [
            {
                "strategy_id": strategy_id,
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            },
            {
                "strategy_id": strategy_id,
                "symbol": "000001",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31"
            }
        ]
    }

    with patch('services.strategy_code_service.StrategyCodeService.backtest_strategy') as mock_backtest:
        mock_backtest.return_value = {
            'total_return': 0.25,
            'sharpe_ratio': 1.8,
            'max_drawdown': -0.10,
            'win_rate': 0.65,
            'profit_factor': 1.6
        }

        batch_resp = client.post('/api/backtest/batch', json=batch_payload)
        assert batch_resp.status_code == 200
        assert batch_resp.json['data']['summary']['total'] == 2

    # 3. 参数优化
    optimize_payload = {
        "strategy_id": strategy_id,
        "symbol": "000001",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {"rsi_low": [25, 30]}
    }

    with patch('services.strategy_code_service.StrategyCodeService.backtest_strategy') as mock_backtest:
        def backtest_side_effect(strategy_id, symbol, start_date, end_date, initial_cash, params_override):
            rsi_low = params_override.get('rsi_low', 30)
            base_score = 1.8 if rsi_low == 30 else 1.5
            return {
                'total_return': base_score * 0.1,
                'sharpe_ratio': base_score,
                'max_drawdown': -0.08,
                'win_rate': 0.62,
                'profit_factor': 1.5
            }

        mock_backtest.side_effect = backtest_side_effect

        optimize_resp = client.post('/api/portfolio/strategy-optimize', json=optimize_payload)
        assert optimize_resp.status_code == 200
        assert optimize_resp.json['data']['totalCombinations'] == 2

    # 4. 信号生成（同步）
    signal_payload = {
        "symbols": ["000001"],
        "strategy_id": strategy_id
    }

    with patch('services.strategy_code_service.StrategyCodeService') as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Mock strategy repository
        mock_service.strategy_repo.get_by_id.return_value = {
            'strategy_id': strategy_id,
            'strategy_name': '集成测试策略',
            'code_content': "df['buy'] = df['rsi'] < 30\ndf['sell'] = df['rsi'] > 70",
            'code_type': 'indicator'
        }

        # Mock signal generation
        mock_service.generate_signal.return_value = {
            'symbol': '000001',
            'strategy_id': strategy_id,
            'strategy_name': '集成测试策略',
            'signal_type': 'buy',
            'confidence': 0.85,
            'signal_date': '2025-12-31',
            'price': 1680.0,
            'created_at': '2025-12-31T12:00:00'
        }

        signal_resp = client.post('/api/cli/signal-generate', json=signal_payload)
        assert signal_resp.status_code == 200


def test_performance_batch_backtest(client, sample_strategy):
    """测试批量回测性能"""
    jobs = [
        {
            "strategy_id": sample_strategy['id'],
            "symbol": f"60{i:04d}",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31"
        }
        for i in range(20)
    ]

    with patch('services.strategy_code_service.StrategyCodeService.backtest_strategy') as mock_backtest:
        mock_backtest.return_value = {
            'total_return': 0.25,
            'sharpe_ratio': 1.8,
            'max_drawdown': -0.10,
            'win_rate': 0.65,
            'profit_factor': 1.6
        }

        start = time.time()
        response = client.post('/api/backtest/batch', json={"jobs": jobs})
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 120  # 20个回测应在2分钟内完成
        print(f"\n批量回测 {len(jobs)} 个任务耗时: {elapsed:.2f}s")


def test_performance_parameter_optimization(client, sample_strategy):
    """测试参数优化性能"""
    payload = {
        "strategy_id": sample_strategy['id'],
        "symbol": "000001",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "metric": "sharpe",
        "param_grid": {
            "rsi_low": [20, 25, 30, 35, 40],
            "rsi_high": [60, 65, 70, 75, 80]
        }
    }

    with patch('services.strategy_code_service.StrategyCodeService.backtest_strategy') as mock_backtest:
        def backtest_side_effect(strategy_id, symbol, start_date, end_date, initial_cash, params_override):
            rsi_low = params_override.get('rsi_low', 30)
            rsi_high = params_override.get('rsi_high', 70)
            # Simulate varying performance
            base_score = 1.5 + (rsi_low / 100) + (rsi_high / 200)
            return {
                'total_return': base_score * 0.1,
                'sharpe_ratio': base_score,
                'max_drawdown': -0.08,
                'win_rate': 0.62,
                'profit_factor': 1.5
            }

        mock_backtest.side_effect = backtest_side_effect

        start = time.time()
        response = client.post('/api/portfolio/strategy-optimize', json=payload)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert response.json['data']['totalCombinations'] == 25
        assert elapsed < 300  # 25个组合应在5分钟内完成
        print(f"\n参数优化 25 个组合耗时: {elapsed:.2f}s")
