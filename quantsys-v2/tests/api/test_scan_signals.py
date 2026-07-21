"""
测试 /api/signals/scan 端点
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add quantsys-v2 to path
v2_root = Path(__file__).resolve().parents[2]
if str(v2_root) not in sys.path:
    sys.path.insert(0, str(v2_root))


@pytest.fixture
def client():
    """创建Flask测试客户端"""
    from adapters.inbound.api.server import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_services():
    """Mock服务层"""
    with patch('api.routes.signals.stock_pool_service') as mock_pool, \
         patch('api.routes.signals.scoring_service') as mock_scoring:
        yield {
            'pool': mock_pool,
            'scoring': mock_scoring
        }


class TestScanSignalsEndpoint:
    """测试机会雷达扫描端点"""

    def test_scan_basic_no_filters(self, client, mock_services):
        """测试基本扫描 - 无筛选条件"""
        # Mock返回数据
        mock_services['pool'].get_hot_stocks.return_value = [
            '000001.SH', '600036.SH', '000001.SZ'
        ]
        mock_services['scoring'].score_stocks.return_value = [
            {
                'symbol': '000001.SH',
                'name': '浦发银行',
                'score': 85.5,
                'technical_score': 80.0,
                'fundamental_score': 90.0,
                'capital_score': 86.0,
                'confidence': 0.85,
                'risk_level': 'low',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            },
            {
                'symbol': '600036.SH',
                'name': '招商银行',
                'score': 75.0,
                'technical_score': 70.0,
                'fundamental_score': 80.0,
                'capital_score': 75.0,
                'confidence': 0.75,
                'risk_level': 'medium',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            }
        ]

        # 发送请求
        response = client.post('/api/signals/scan', json={})

        # 验证响应
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'opportunities' in data
        assert len(data['opportunities']) == 2
        assert data['total'] == 2
        assert data['scanned'] >= 2  # At least the opportunities returned

        # 验证服务调用
        mock_services['pool'].get_hot_stocks.assert_called_once()
        mock_services['scoring'].score_stocks.assert_called_once()

    def test_scan_with_watchlist(self, client, mock_services):
        """测试扫描 - 指定自选股"""
        mock_services['pool'].get_hot_stocks.return_value = [
            '000001.SH', '600036.SH'
        ]
        mock_services['scoring'].score_stocks.return_value = [
            {
                'symbol': '000001.SZ',
                'name': '平安银行',
                'score': 70.0,
                'technical_score': 65.0,
                'fundamental_score': 75.0,
                'capital_score': 70.0,
                'confidence': 0.70,
                'risk_level': 'medium',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            }
        ]

        # 发送请求 - 指定stocks参数
        response = client.post('/api/signals/scan', json={
            'stocks': ['000001.SZ', '000002.SZ']
        })

        # 验证响应
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 验证使用了指定的股票列表，而不是热门股票池
        call_args = mock_services['scoring'].score_stocks.call_args
        assert '000001.SZ' in call_args[1]['symbols']
        assert '000002.SZ' in call_args[1]['symbols']

    def test_scan_with_technical_filters(self, client, mock_services):
        """测试扫描 - 技术指标筛选"""
        mock_services['pool'].get_hot_stocks.return_value = ['000001.SH']
        mock_services['scoring'].score_stocks.return_value = [
            {
                'symbol': '000001.SH',
                'name': '浦发银行',
                'score': 85.5,
                'technical_score': 90.0,
                'fundamental_score': 80.0,
                'capital_score': 86.0,
                'confidence': 0.85,
                'risk_level': 'low',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            }
        ]

        # 发送请求 - 技术指标筛选
        response = client.post('/api/signals/scan', json={
            'technical': ['rsi_oversold', 'macd_golden_cross']
        })

        # 验证响应
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 验证筛选条件传递
        call_args = mock_services['scoring'].score_stocks.call_args
        assert call_args[1]['filters']['technical'] == ['rsi_oversold', 'macd_golden_cross']

    def test_scan_with_fundamental_filters(self, client, mock_services):
        """测试扫描 - 基本面筛选"""
        mock_services['pool'].get_hot_stocks.return_value = ['000001.SH']
        mock_services['scoring'].score_stocks.return_value = [
            {
                'symbol': '000001.SH',
                'name': '浦发银行',
                'score': 85.5,
                'technical_score': 80.0,
                'fundamental_score': 95.0,
                'capital_score': 86.0,
                'confidence': 0.85,
                'risk_level': 'low',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            }
        ]

        # 发送请求 - 基本面筛选
        response = client.post('/api/signals/scan', json={
            'fundamental': ['pe_low', 'roe_high']
        })

        # 验证响应
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 验证筛选条件传递
        call_args = mock_services['scoring'].score_stocks.call_args
        assert call_args[1]['filters']['fundamental'] == ['pe_low', 'roe_high']

    def test_scan_with_min_score(self, client, mock_services):
        """测试扫描 - 最低评分筛选"""
        mock_services['pool'].get_hot_stocks.return_value = ['000001.SH', '600036.SH']
        mock_services['scoring'].score_stocks.return_value = [
            {
                'symbol': '000001.SH',
                'name': '浦发银行',
                'score': 85.5,
                'technical_score': 80.0,
                'fundamental_score': 90.0,
                'capital_score': 86.0,
                'confidence': 0.85,
                'risk_level': 'low',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            },
            {
                'symbol': '600036.SH',
                'name': '招商银行',
                'score': 65.0,
                'technical_score': 60.0,
                'fundamental_score': 70.0,
                'capital_score': 65.0,
                'confidence': 0.65,
                'risk_level': 'medium',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            }
        ]

        # 发送请求 - 最低评分70
        response = client.post('/api/signals/scan', json={
            'minScore': 70
        })

        # 验证响应
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 只返回评分>=70的股票
        assert len(data['opportunities']) == 1
        assert data['opportunities'][0]['symbol'] == '000001.SH'
        assert data['opportunities'][0]['score'] >= 70

    def test_scan_with_risk_level(self, client, mock_services):
        """测试扫描 - 风险等级筛选"""
        mock_services['pool'].get_hot_stocks.return_value = ['000001.SH', '600036.SH', '000001.SZ']
        mock_services['scoring'].score_stocks.return_value = [
            {
                'symbol': '000001.SH',
                'name': '浦发银行',
                'score': 85.5,
                'technical_score': 80.0,
                'fundamental_score': 90.0,
                'capital_score': 86.0,
                'confidence': 0.85,
                'risk_level': 'low',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            },
            {
                'symbol': '600036.SH',
                'name': '招商银行',
                'score': 75.0,
                'technical_score': 70.0,
                'fundamental_score': 80.0,
                'capital_score': 75.0,
                'confidence': 0.75,
                'risk_level': 'medium',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            },
            {
                'symbol': '000001.SZ',
                'name': '平安银行',
                'score': 65.0,
                'technical_score': 60.0,
                'fundamental_score': 70.0,
                'capital_score': 65.0,
                'confidence': 0.65,
                'risk_level': 'high',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            }
        ]

        # 发送请求 - 只要低风险和中风险
        response = client.post('/api/signals/scan', json={
            'maxRiskLevel': 'medium'
        })

        # 验证响应
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 只返回风险等级<=medium的股票
        assert len(data['opportunities']) == 2
        risk_levels = [opp['risk_level'] for opp in data['opportunities']]
        assert 'high' not in risk_levels
        assert 'low' in risk_levels
        assert 'medium' in risk_levels

    def test_scan_with_combined_filters(self, client, mock_services):
        """测试扫描 - 组合筛选条件"""
        mock_services['pool'].get_hot_stocks.return_value = ['000001.SH']
        mock_services['scoring'].score_stocks.return_value = [
            {
                'symbol': '000001.SH',
                'name': '浦发银行',
                'score': 85.5,
                'technical_score': 80.0,
                'fundamental_score': 90.0,
                'capital_score': 86.0,
                'confidence': 0.85,
                'risk_level': 'low',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            }
        ]

        # 发送请求 - 组合筛选
        response = client.post('/api/signals/scan', json={
            'technical': ['rsi_oversold'],
            'fundamental': ['pe_low'],
            'minScore': 70,
            'maxRiskLevel': 'medium'
        })

        # 验证响应
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 验证所有筛选条件都传递了
        call_args = mock_services['scoring'].score_stocks.call_args
        assert call_args[1]['filters']['technical'] == ['rsi_oversold']
        assert call_args[1]['filters']['fundamental'] == ['pe_low']

    def test_scan_sorted_by_score(self, client, mock_services):
        """测试扫描 - 结果按评分降序排列"""
        mock_services['pool'].get_hot_stocks.return_value = ['000001.SH', '600036.SH', '000001.SZ']
        mock_services['scoring'].score_stocks.return_value = [
            {
                'symbol': '600036.SH',
                'name': '招商银行',
                'score': 75.0,
                'technical_score': 70.0,
                'fundamental_score': 80.0,
                'capital_score': 75.0,
                'confidence': 0.75,
                'risk_level': 'medium',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            },
            {
                'symbol': '000001.SH',
                'name': '浦发银行',
                'score': 85.5,
                'technical_score': 80.0,
                'fundamental_score': 90.0,
                'capital_score': 86.0,
                'confidence': 0.85,
                'risk_level': 'low',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            },
            {
                'symbol': '000001.SZ',
                'name': '平安银行',
                'score': 65.0,
                'technical_score': 60.0,
                'fundamental_score': 70.0,
                'capital_score': 65.0,
                'confidence': 0.65,
                'risk_level': 'high',
                'signal_type': 'buy',
                'timestamp': '2026-05-24T10:00:00'
            }
        ]

        # 发送请求
        response = client.post('/api/signals/scan', json={})

        # 验证响应
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 验证排序（降序）
        scores = [opp['score'] for opp in data['opportunities']]
        assert scores == sorted(scores, reverse=True)
        assert data['opportunities'][0]['symbol'] == '000001.SH'  # 最高分
        assert data['opportunities'][-1]['symbol'] == '000001.SZ'  # 最低分

    def test_scan_with_strategy_id_uses_strategy_signals(self, client, monkeypatch):
        """测试扫描 - 指定策略ID时使用策略信号生成机会"""
        import adapters.inbound.api.routes.signals as signals_routes

        mock_scoring = Mock()
        mock_strategy = Mock()

        def generate_signal(strategy_id, symbol):
            signals = {
                '000001.SH': {
                    'symbol': '000001.SH',
                    'name': '浦发银行',
                    'strategy_id': strategy_id,
                    'strategy_name': '测试策略',
                    'signal_type': 'buy',
                    'confidence': 0.82,
                    'signal_date': '2026-06-01',
                    'price': 10.5,
                    'created_at': '2026-06-01T10:00:00'
                },
                '600036.SH': {
                    'symbol': '600036.SH',
                    'name': '招商银行',
                    'strategy_id': strategy_id,
                    'strategy_name': '测试策略',
                    'signal_type': 'sell',
                    'confidence': 0.9,
                    'signal_date': '2026-06-01',
                    'price': 35.0,
                    'created_at': '2026-06-01T10:00:00'
                },
                '000002.SZ': None
            }
            return signals[symbol]

        mock_strategy.generate_signal.side_effect = generate_signal
        monkeypatch.setattr(signals_routes, 'scoring_service', mock_scoring)
        monkeypatch.setattr(signals_routes, 'strategy_service', mock_strategy)

        response = client.post('/api/signals/scan', json={
            'strategy_id': '193',
            'stocks': ['000001.SH', '600036.SH', '000002.SZ'],
            'min_score': 80,
            'max_risk_level': 'medium'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['scan_mode'] == 'strategy'
        assert data['strategy_id'] == 193
        assert data['total'] == 1
        assert data['scanned'] == 3

        opportunity = data['opportunities'][0]
        assert opportunity['symbol'] == '000001.SH'
        assert opportunity['name'] == '浦发银行'
        assert opportunity['strategy_id'] == 193
        assert opportunity['strategy_name'] == '测试策略'
        assert opportunity['score'] == 82
        assert opportunity['risk_level'] == 'low'
        assert opportunity['price'] == 10.5

        mock_scoring.score_stocks.assert_not_called()
        assert mock_strategy.generate_signal.call_count == 3

    def test_scan_with_invalid_strategy_id_returns_400(self, client):
        """测试扫描 - 策略ID无效时返回400"""
        response = client.post('/api/signals/scan', json={
            'strategy_id': 'invalid'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'strategy_id' in data['error']

    def test_scan_error_handling(self, client, mock_services):
        """测试扫描 - 错误处理"""
        # Mock抛出异常
        mock_services['pool'].get_hot_stocks.side_effect = Exception("Database error")

        # 发送请求
        response = client.post('/api/signals/scan', json={})

        # 验证响应
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data
