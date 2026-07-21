"""
风险指标 API 路由测试
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


@pytest.fixture
def sample_returns():
    """生成样本收益率数据"""
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, 100).tolist()
    return returns


@pytest.fixture
def sample_benchmark_returns():
    """生成样本基准收益率"""
    np.random.seed(43)
    returns = np.random.normal(0.0008, 0.012, 100).tolist()
    return returns


class TestRiskMetricsRoutes:
    """风险指标 API 测试"""

    def test_calculate_metrics_basic(self, client, sample_returns):
        """测试基础风险指标计算"""
        response = client.post(
            '/api/risk/metrics',
            data=json.dumps({'returns': sample_returns}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['success'] is True
        assert 'metrics' in data

        metrics = data['metrics']
        # 检查所有必需字段
        required_fields = [
            'sharpe_ratio',
            'sortino_ratio',
            'calmar_ratio',
            'max_drawdown',
            'annual_return',
            'annual_volatility',
            'var_95',
            'cvar_95',
            'cumulative_return'
        ]

        for field in required_fields:
            assert field in metrics
            assert isinstance(metrics[field], (int, float))

    def test_calculate_metrics_with_benchmark(self, client, sample_returns, sample_benchmark_returns):
        """测试带基准的风险指标计算"""
        response = client.post(
            '/api/risk/metrics',
            data=json.dumps({
                'returns': sample_returns,
                'benchmark_returns': sample_benchmark_returns,
                'risk_free': 0.03
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['success'] is True
        metrics = data['metrics']

        # 检查基准相关字段
        assert 'alpha' in metrics
        assert 'beta' in metrics
        assert 'information_ratio' in metrics

    def test_calculate_metrics_missing_returns(self, client):
        """测试缺少 returns 参数"""
        response = client.post(
            '/api/risk/metrics',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        # 空请求体会返回 "请求体不能为空" 错误
        assert '空' in data['error'] or 'returns' in data['error']

    def test_calculate_metrics_empty_returns(self, client):
        """测试空 returns 列表"""
        response = client.post(
            '/api/risk/metrics',
            data=json.dumps({'returns': []}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_calculate_metrics_mismatched_benchmark(self, client, sample_returns):
        """测试基准长度不匹配"""
        response = client.post(
            '/api/risk/metrics',
            data=json.dumps({
                'returns': sample_returns,
                'benchmark_returns': [0.01, 0.02]  # 长度不匹配
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '长度' in data['error']

    def test_calculate_metrics_custom_risk_free(self, client, sample_returns):
        """测试自定义无风险利率"""
        response = client.post(
            '/api/risk/metrics',
            data=json.dumps({
                'returns': sample_returns,
                'risk_free': 0.05
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_calculate_sharpe_only(self, client, sample_returns):
        """测试单独计算夏普比率"""
        response = client.post(
            '/api/risk/sharpe',
            data=json.dumps({'returns': sample_returns}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['success'] is True
        assert 'sharpe_ratio' in data
        assert isinstance(data['sharpe_ratio'], (int, float))

    def test_calculate_sharpe_missing_returns(self, client):
        """测试夏普计算缺少 returns"""
        response = client.post(
            '/api/risk/sharpe',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_calculate_alpha_beta(self, client, sample_returns, sample_benchmark_returns):
        """测试 Alpha/Beta 计算"""
        response = client.post(
            '/api/risk/alpha-beta',
            data=json.dumps({
                'returns': sample_returns,
                'benchmark_returns': sample_benchmark_returns
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data['success'] is True
        assert 'alpha' in data
        assert 'beta' in data
        assert isinstance(data['alpha'], (int, float))
        assert isinstance(data['beta'], (int, float))

    def test_calculate_alpha_beta_missing_benchmark(self, client, sample_returns):
        """测试 Alpha/Beta 计算缺少基准"""
        response = client.post(
            '/api/risk/alpha-beta',
            data=json.dumps({'returns': sample_returns}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    def test_calculate_alpha_beta_length_mismatch(self, client, sample_returns):
        """测试 Alpha/Beta 计算长度不匹配"""
        response = client.post(
            '/api/risk/alpha-beta',
            data=json.dumps({
                'returns': sample_returns,
                'benchmark_returns': [0.01, 0.02]  # 长度不匹配
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestRiskMetricsIntegration:
    """风险指标集成测试"""

    def test_full_workflow(self, client):
        """测试完整工作流程"""
        # 1. 生成模拟收益率
        returns = [0.01, -0.02, 0.03, 0.005, -0.01, 0.02, 0.015, -0.005, 0.01, 0.008]
        benchmark = [0.005, -0.01, 0.02, 0.003, -0.008, 0.015, 0.01, -0.003, 0.008, 0.006]

        # 2. 计算完整指标
        response = client.post(
            '/api/risk/metrics',
            data=json.dumps({
                'returns': returns,
                'benchmark_returns': benchmark,
                'risk_free': 0.03
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        metrics = data['metrics']

        # 3. 验证所有指标都存在且为有限数值
        required_metrics = [
            'sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'max_drawdown',
            'annual_return', 'annual_volatility', 'var_95', 'cvar_95',
            'cumulative_return', 'alpha', 'beta', 'information_ratio'
        ]

        for metric_name in required_metrics:
            assert metric_name in metrics
            # 检查是有限数值（不是NaN或Inf）
            value = metrics[metric_name]
            assert isinstance(value, (int, float))
            assert not (value != value)  # 检查不是NaN

        # 4. 验证一些基本逻辑关系
        assert metrics['max_drawdown'] <= 0  # 最大回撤应该是负数或0
        assert metrics['cvar_95'] <= metrics['var_95']  # CVaR应该小于等于VaR
        assert metrics['annual_volatility'] > 0  # 波动率应该是正数

    def test_negative_returns_strategy(self, client):
        """测试亏损策略的指标"""
        # 纯亏损策略
        negative_returns = [-0.01, -0.02, -0.015, -0.008, -0.012] * 10

        response = client.post(
            '/api/risk/metrics',
            data=json.dumps({'returns': negative_returns}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        metrics = data['metrics']

        # 夏普比率应该是负数
        assert metrics['sharpe_ratio'] < 0

        # 年化收益率应该是负数
        assert metrics['annual_return'] < 0

        # 最大回撤应该是负数
        assert metrics['max_drawdown'] < 0
