"""
市场风格检测 API 路由测试
"""
import pytest
from datetime import date
from unittest.mock import Mock, patch
from adapters.inbound.api.server import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestMarketStyleRoutes:
    """市场风格检测路由测试"""

    def test_get_market_style(self, client):
        """测试获取市场风格 - 200 OK"""
        mock_result = {
            'trade_date': date(2026, 6, 1),
            'style': 'momentum',
            'confidence': 0.75,
            'metrics': {
                'avg_rsi': 65.5,
                'avg_volume_ratio': 1.8
            },
            'scores': {
                'momentum': 0.75,
                'oscillation': 0.15,
                'low_volatility': 0.05,
                'value': 0.05
            }
        }

        with patch('api.routes.market_style.market_style_detector') as mock_detector:
            # Mock DB check - not found
            mock_detector.market_style_repo.get_by_date.return_value = None
            # Mock detection
            mock_detector.detect.return_value = mock_result
            # Mock save
            mock_detector.market_style_repo.save.return_value = mock_result

            response = client.get('/api/market/style?trade_date=2026-06-01')

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['style'] == 'momentum'
            assert data['data']['confidence'] == 0.75
            assert 'metrics' in data['data']
            assert 'scores' in data['data']

    def test_get_market_style_from_cache(self, client):
        """测试从缓存获取市场风格"""
        cached_result = {
            'trade_date': date(2026, 6, 1),
            'style': 'oscillation',
            'confidence': 0.68,
            'metrics': {},
            'scores': {}
        }

        with patch('api.routes.market_style.market_style_detector') as mock_detector:
            # Mock DB check - found
            mock_detector.market_style_repo.get_by_date.return_value = cached_result

            response = client.get('/api/market/style?trade_date=2026-06-01')

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['style'] == 'oscillation'
            # Should not call detect when cached
            mock_detector.detect.assert_not_called()

    def test_get_strategy_weight(self, client):
        """测试获取策略权重 - 200 OK"""
        mock_weight = 1.2

        with patch('api.routes.market_style.strategy_weight_repo') as mock_repo:
            mock_repo.get_static_weight.return_value = mock_weight

            response = client.get(
                '/api/strategies/trend_following/weight?market_style=momentum&strategy_type=trend_following'
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['strategyName'] == 'trend_following'
            assert data['data']['marketStyle'] == 'momentum'
            assert data['data']['strategyType'] == 'trend_following'
            assert data['data']['weight'] == 1.2

    def test_get_strategy_weight_auto_lookup(self, client):
        """测试自动查询 strategy_type"""
        mock_strategy = {
            'id': 1,
            'strategy_name': 'my_strategy',
            'strategy_type': 'mean_reversion'
        }
        mock_weight = 0.8

        with patch('api.routes.market_style.strategy_repo') as mock_strategy_repo, \
             patch('api.routes.market_style.strategy_weight_repo') as mock_weight_repo:

            mock_strategy_repo.get_by_name.return_value = mock_strategy
            mock_weight_repo.get_static_weight.return_value = mock_weight

            response = client.get(
                '/api/strategies/my_strategy/weight?market_style=oscillation'
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['strategyType'] == 'mean_reversion'
            assert data['data']['weight'] == 0.8

    def test_get_strategy_weight_missing_param(self, client):
        """测试缺少必需参数 - 400 error"""
        response = client.get('/api/strategies/trend_following/weight')

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'market_style' in data['error']

    def test_get_strategy_weight_strategy_not_found(self, client):
        """测试策略不存在 - 404 error"""
        with patch('api.routes.market_style.strategy_repo') as mock_repo:
            mock_repo.get_by_name.return_value = None

            response = client.get(
                '/api/strategies/nonexistent/weight?market_style=momentum'
            )

            assert response.status_code == 404
            data = response.get_json()
            assert data['success'] is False
            assert '策略不存在' in data['error']

    def test_get_market_style_default_date(self, client):
        """测试默认使用今天日期"""
        mock_result = {
            'trade_date': date.today(),
            'style': 'momentum',
            'confidence': 0.75,
            'metrics': {},
            'scores': {}
        }

        with patch('api.routes.market_style.market_style_detector') as mock_detector:
            mock_detector.market_style_repo.get_by_date.return_value = None
            mock_detector.detect.return_value = mock_result
            mock_detector.market_style_repo.save.return_value = mock_result

            response = client.get('/api/market/style')

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            # Should use today's date
            mock_detector.detect.assert_called_once()
