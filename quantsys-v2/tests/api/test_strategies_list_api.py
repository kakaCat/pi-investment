"""
测试 GET /api/strategies/list?source=builtin API 端点
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


class TestStrategiesListAPI:
    """测试策略列表 API"""

    @patch('api.routes.strategies.strategy_service')
    def test_user_list_excludes_inactive_strategies(self, mock_strategy_service, client):
        """用户策略列表不返回已停用/删除的策略"""
        mock_strategy_service.list_strategies.return_value = [
            {
                'id': 1,
                'strategy_name': 'active strategy',
                'code_type': 'indicator',
                'is_active': True,
                'status': 'valid',
            },
            {
                'id': 2,
                'strategy_name': 'inactive strategy',
                'code_type': 'indicator',
                'is_active': False,
                'status': 'valid',
            },
        ]

        response = client.get('/api/strategies/list')

        assert response.status_code == 200
        data = response.get_json()
        items = data['data']['items']
        assert [item['id'] for item in items] == ['1']

    @patch('quantlib.engine.strategy_factory.StrategyFactory')
    def test_list_returns_all_builtin_strategies(self, mock_factory, client):
        """测试列表返回所有内置策略"""
        mock_factory._registry = {'ma_cross': object()}
        mock_factory.list_all.return_value = [
            'ma_cross', 'rsi_reversal', 'bollinger_breakout'
        ]
        mock_factory.get_info.side_effect = lambda name: {
            'class_name': f'{name}Strategy',
            'description': f'{name} strategy',
            'category': 'trend_following',
            'default_params': {},
            'param_schema': {}
        }

        response = client.get('/api/strategies/list?source=builtin')

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['total'] == 3
        strategies = data['data']['strategies']
        assert len(strategies) == 3
        assert strategies[0]['strategyType'] == 'ma_cross'
        assert strategies[0]['className'] == 'ma_crossStrategy'

    @patch('quantlib.engine.strategy_factory.StrategyFactory')
    def test_list_includes_metadata(self, mock_factory, client):
        """测试列表包含元数据"""
        mock_factory._registry = {'ma_cross': object()}
        mock_factory.list_all.return_value = ['ma_cross']
        mock_factory.get_info.return_value = {
            'class_name': 'MACrossStrategy',
            'description': 'Moving average crossover',
            'category': 'trend_following',
            'default_params': {'fast': 5, 'slow': 20},
            'param_schema': {'fast': 'int', 'slow': 'int'}
        }

        response = client.get('/api/strategies/list?source=builtin')

        data = response.get_json()
        strategy = data['data']['strategies'][0]
        assert strategy['strategyType'] == 'ma_cross'
        assert strategy['className'] == 'MACrossStrategy'
        assert strategy['description'] == 'Moving average crossover'
        assert strategy['category'] == 'trend_following'
        assert strategy['defaultParams'] == {'fast': 5, 'slow': 20}
        assert strategy['paramSchema'] == {'fast': 'int', 'slow': 'int'}

    @patch('quantlib.engine.strategy_factory.StrategyFactory')
    def test_list_returns_empty_when_no_strategies(self, mock_factory, client):
        """测试无策略时返回空列表"""
        mock_factory._registry = {}
        mock_factory.list_all.return_value = []

        response = client.get('/api/strategies/list?source=builtin')

        data = response.get_json()
        assert data['success'] is True
        assert data['data']['total'] == 0

    @patch('quantlib.engine.strategy_factory.StrategyFactory')
    def test_list_filters_by_category(self, mock_factory, client):
        """测试按分类过滤"""
        mock_factory._registry = {'ma_cross': object()}
        mock_factory.list_all.return_value = ['ma_cross', 'rsi_reversal']
        mock_factory.get_info.side_effect = lambda name: {
            'class_name': f'{name}Strategy',
            'description': f'{name} strategy',
            'category': 'trend_following' if name == 'ma_cross' else 'mean_reversion',
            'default_params': {},
            'param_schema': {}
        }

        response = client.get('/api/strategies/list?source=builtin&category=trend_following')

        data = response.get_json()
        strategies = data['data']['strategies']
        assert len(strategies) == 1
        assert strategies[0]['strategyType'] == 'ma_cross'
        assert strategies[0]['category'] == 'trend_following'
