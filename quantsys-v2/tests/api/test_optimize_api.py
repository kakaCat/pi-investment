"""
测试 /api/strategies/optimize API 端点
"""
import pytest
from unittest.mock import Mock, patch
from adapters.inbound.api.routes.strategies import strategies_bp
from flask import Flask


@pytest.fixture
def client():
    """创建测试客户端"""
    app = Flask(__name__)
    app.register_blueprint(strategies_bp)
    app.config['TESTING'] = True
    return app.test_client()


class TestOptimizeAPI:
    """测试策略优化 API"""

    @patch('api.routes.strategies.strategy_service')
    @patch('api.routes.strategies.StrategyOptimizer')
    def test_optimize_returns_sorted_results(self, mock_optimizer_class, mock_service, client):
        """测试优化返回排序结果"""
        # Mock optimizer
        mock_optimizer = Mock()
        mock_optimizer.optimize.return_value = [
            {
                'params': {'fast': 10, 'slow': 30},
                'sharpe_ratio': 2.0,
                'total_return': 0.15,
                'max_drawdown': -0.08,
                'win_rate': 0.65
            },
            {
                'params': {'fast': 5, 'slow': 20},
                'sharpe_ratio': 1.5,
                'total_return': 0.10,
                'max_drawdown': -0.05,
                'win_rate': 0.60
            }
        ]
        mock_optimizer_class.return_value = mock_optimizer

        response = client.post('/api/strategies/optimize', json={
            'strategyId': 1,
            'symbol': '000001.SH',
            'startDate': '2024-01-01',
            'endDate': '2024-12-31',
            'paramRanges': {
                'fast': [5, 10],
                'slow': [20, 30]
            }
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert len(data['results']) == 2
        assert data['results'][0]['params'] == {'fast': 10, 'slow': 30}
        assert data['results'][0]['sharpeRatio'] == 2.0

    @patch('api.routes.strategies.strategy_service')
    @patch('api.routes.strategies.StrategyOptimizer')
    def test_optimize_with_missing_fields_returns_error(self, mock_optimizer_class, mock_service, client):
        """测试缺少必需字段返回错误"""
        response = client.post('/api/strategies/optimize', json={
            'strategyId': 1,
            'symbol': '000001.SH'
            # 缺少 startDate, endDate, paramRanges
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    @patch('api.routes.strategies.strategy_service')
    @patch('api.routes.strategies.StrategyOptimizer')
    def test_optimize_with_empty_param_ranges_returns_error(self, mock_optimizer_class, mock_service, client):
        """测试空参数范围返回错误"""
        response = client.post('/api/strategies/optimize', json={
            'strategyId': 1,
            'symbol': '000001.SH',
            'startDate': '2024-01-01',
            'endDate': '2024-12-31',
            'paramRanges': {}
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    @patch('api.routes.strategies.strategy_service')
    @patch('api.routes.strategies.StrategyOptimizer')
    def test_optimize_handles_optimizer_exception(self, mock_optimizer_class, mock_service, client):
        """测试优化器异常处理"""
        mock_optimizer = Mock()
        mock_optimizer.optimize.side_effect = ValueError("策略不存在")
        mock_optimizer_class.return_value = mock_optimizer

        response = client.post('/api/strategies/optimize', json={
            'strategyId': 999,
            'symbol': '000001.SH',
            'startDate': '2024-01-01',
            'endDate': '2024-12-31',
            'paramRanges': {'fast': [5, 10]}
        })

        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data
