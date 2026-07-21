"""
P0 API Routes Tests
===================

测试新增的时间序列、因子模型和投资组合优化 API 端点。

Author: QuantSys V2
Date: 2026-05-25
"""

import pytest
import json
import numpy as np
from adapters.inbound.api.server import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestTimeSeriesAPI:
    """时间序列分析 API 测试"""

    def test_arima_fit_success(self, client):
        """测试 ARIMA 拟合成功"""
        response = client.post('/api/timeseries/arima/fit', json={
            'symbol': '000001',
            'order': [1, 0, 1],
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'value' in data['data']
        assert 'aic' in data['data']['value']
        assert 'bic' in data['data']['value']

    def test_arima_fit_missing_symbol(self, client):
        """测试 ARIMA 缺少 symbol 参数"""
        response = client.post('/api/timeseries/arima/fit', json={
            'order': [1, 0, 1]
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'symbol is required' in data['message']

    def test_garch_fit_success(self, client):
        """测试 GARCH 拟合成功"""
        response = client.post('/api/timeseries/garch/fit', json={
            'symbol': '000001',
            'p': 1,
            'q': 1,
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'value' in data['data']
        assert 'conditional_volatility' in data['data']['value']

    def test_kalman_filter_success(self, client):
        """测试 Kalman 滤波成功"""
        response = client.post('/api/timeseries/kalman/filter', json={
            'symbol': '000001',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'value' in data['data']

    def test_kalman_smooth_success(self, client):
        """测试 Kalman 平滑成功"""
        response = client.post('/api/timeseries/kalman/smooth', json={
            'symbol': '000001',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True


class TestFactorModelsAPI:
    """因子模型 API 测试"""

    def test_fama_french_3_success(self, client):
        """测试 Fama-French 3因子模型成功"""
        response = client.post('/api/factor-models/fama-french-3/calculate', json={
            'symbol': '000001',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'value' in data['data']
        assert 'alpha' in data['data']['value']
        assert 'betaMkt' in data['data']['value']
        assert 'betaSmb' in data['data']['value']
        assert 'betaHml' in data['data']['value']

    def test_fama_french_3_missing_symbol(self, client):
        """测试 Fama-French 3因子缺少 symbol"""
        response = client.post('/api/factor-models/fama-french-3/calculate', json={
            'start_date': '2024-01-01'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'symbol is required' in data['message']

    def test_fama_french_5_success(self, client):
        """测试 Fama-French 5因子模型成功"""
        response = client.post('/api/factor-models/fama-french-5/calculate', json={
            'symbol': '000001',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'value' in data['data']
        assert 'alpha' in data['data']['value']

    def test_carhart_success(self, client):
        """测试 Carhart 4因子模型成功"""
        response = client.post('/api/factor-models/carhart/calculate', json={
            'symbol': '000001',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'value' in data['data']
        assert 'alpha' in data['data']['value']
        assert 'betaMom' in data['data']['value']

    def test_barra_not_implemented(self, client):
        """测试 Barra 模型返回未实现提示"""
        response = client.post('/api/factor-models/barra/calculate', json={
            'symbol': '000001'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'DataFrame' in data['message']


class TestPortfolioOptimizationAPI:
    """投资组合优化 API 测试"""

    def test_markowitz_min_variance(self, client):
        """测试 Markowitz 最小方差优化"""
        response = client.post('/api/portfolio/markowitz/optimize', json={
            'expected_returns': [0.12, 0.10, 0.08],
            'covariance_matrix': [
                [0.04, 0.01, 0.02],
                [0.01, 0.03, 0.015],
                [0.02, 0.015, 0.05]
            ],
            'method': 'min_variance'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert 'value' in data['data']
        assert 'weights' in data['data']['value']
        assert len(data['data']['value']['weights']) == 3
        # 权重和应该接近 1
        weights_sum = sum(data['data']['value']['weights'])
        assert abs(weights_sum - 1.0) < 0.01

    def test_markowitz_max_sharpe(self, client):
        """测试 Markowitz 最大夏普比率优化"""
        response = client.post('/api/portfolio/markowitz/optimize', json={
            'expected_returns': [0.12, 0.10, 0.08],
            'covariance_matrix': [
                [0.04, 0.01, 0.02],
                [0.01, 0.03, 0.015],
                [0.02, 0.015, 0.05]
            ],
            'method': 'max_sharpe',
            'risk_free_rate': 0.03
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'sharpeRatio' in data['data']['value']
        assert data['data']['value']['sharpeRatio'] > 0

    def test_markowitz_target_return(self, client):
        """测试 Markowitz 目标收益率优化"""
        response = client.post('/api/portfolio/markowitz/optimize', json={
            'expected_returns': [0.12, 0.10, 0.08],
            'covariance_matrix': [
                [0.04, 0.01, 0.02],
                [0.01, 0.03, 0.015],
                [0.02, 0.015, 0.05]
            ],
            'method': 'target_return',
            'target_return': 0.10
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        # 实际收益率应该接近目标收益率
        actual_return = data['data']['value']['expectedReturn']
        assert abs(actual_return - 0.10) < 0.01

    def test_markowitz_missing_params(self, client):
        """测试 Markowitz 缺少必需参数"""
        response = client.post('/api/portfolio/markowitz/optimize', json={
            'expected_returns': [0.12, 0.10, 0.08]
            # 缺少 covariance_matrix
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'required' in data['message']

    def test_black_litterman_success(self, client):
        """测试 Black-Litterman 优化成功"""
        response = client.post('/api/portfolio/black-litterman/optimize', json={
            'market_weights': [0.4, 0.3, 0.3],
            'covariance_matrix': [
                [0.04, 0.01, 0.02],
                [0.01, 0.03, 0.015],
                [0.02, 0.015, 0.05]
            ],
            'views': [[1, -1, 0]],
            'view_confidences': [0.5],
            'risk_aversion': 2.5
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'posterior_returns' in data['data']['value']
        assert 'optimal_weights' in data['data']['value']

    def test_risk_parity_success(self, client):
        """测试 Risk Parity 优化成功"""
        response = client.post('/api/portfolio/risk-parity/optimize', json={
            'covariance_matrix': [
                [0.04, 0.01, 0.02],
                [0.01, 0.03, 0.015],
                [0.02, 0.015, 0.05]
            ]
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'weights' in data['data']['value']
        assert 'risk_contributions' in data['data']['value']
        # 权重和应该接近 1
        weights_sum = sum(data['data']['value']['weights'])
        assert abs(weights_sum - 1.0) < 0.01

    def test_risk_parity_missing_cov_matrix(self, client):
        """测试 Risk Parity 缺少协方差矩阵"""
        response = client.post('/api/portfolio/risk-parity/optimize', json={})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'covariance_matrix is required' in data['message']


class TestAPIErrorHandling:
    """API 错误处理测试"""

    def test_invalid_json(self, client):
        """测试无效的 JSON 请求"""
        response = client.post(
            '/api/timeseries/arima/fit',
            data='invalid json',
            content_type='application/json'
        )
        # Flask 会返回 400 或者我们的错误处理会捕获
        assert response.status_code in [200, 400]

    def test_invalid_action_type(self, client):
        """测试无效的 action_type"""
        response = client.post('/api/timeseries/arima/invalid_action', json={
            'symbol': '000001',
            'order': [1, 0, 1]
        })
        # 应该返回 404 或错误响应
        assert response.status_code in [200, 404]

    def test_insufficient_data(self, client):
        """测试数据不足的情况"""
        response = client.post('/api/timeseries/arima/fit', json={
            'symbol': '000001',
            'order': [1, 0, 1],
            'start_date': '2024-12-30',
            'end_date': '2024-12-31'  # 只有1-2天数据
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        # 应该返回错误或数据不足的提示
        if not data['success']:
            assert 'Insufficient' in data['message'] or 'data' in data['message'].lower()


class TestNumpyJSONSerialization:
    """测试 numpy 数组的 JSON 序列化"""

    def test_weights_are_json_serializable(self, client):
        """测试权重数组可以 JSON 序列化"""
        response = client.post('/api/portfolio/markowitz/optimize', json={
            'expected_returns': [0.12, 0.10, 0.08],
            'covariance_matrix': [
                [0.04, 0.01, 0.02],
                [0.01, 0.03, 0.015],
                [0.02, 0.015, 0.05]
            ],
            'method': 'max_sharpe',
            'risk_free_rate': 0.03
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        # 确保权重是 list 而不是 numpy array
        assert isinstance(data['data']['value']['weights'], list)
        # 确保每个元素都是 Python 原生类型
        for weight in data['data']['value']['weights']:
            assert isinstance(weight, (int, float))

    def test_arima_fitted_values_serializable(self, client):
        """测试 ARIMA 拟合值可以 JSON 序列化"""
        response = client.post('/api/timeseries/arima/fit', json={
            'symbol': '000001',
            'order': [1, 0, 1],
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        if 'fittedValues' in data['data']['value']:
            assert isinstance(data['data']['value']['fittedValues'], list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
