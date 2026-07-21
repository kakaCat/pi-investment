"""
组合优化服务单元测试
"""
import pytest
import numpy as np
from application.services.portfolio_optimization_service import (
    PortfolioOptimizationService,
    CVXPY_AVAILABLE
)


class TestPortfolioOptimizationService:
    """测试组合优化服务"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return PortfolioOptimizationService()

    @pytest.fixture
    def sample_data(self):
        """创建示例数据"""
        np.random.seed(42)
        n_assets = 5

        # 模拟预期收益率
        expected_returns = np.array([0.10, 0.12, 0.08, 0.15, 0.09])

        # 模拟协方差矩阵
        volatilities = np.array([0.15, 0.20, 0.12, 0.25, 0.18])
        correlation = np.array([
            [1.0, 0.3, 0.2, 0.1, 0.4],
            [0.3, 1.0, 0.4, 0.2, 0.3],
            [0.2, 0.4, 1.0, 0.1, 0.2],
            [0.1, 0.2, 0.1, 1.0, 0.3],
            [0.4, 0.3, 0.2, 0.3, 1.0]
        ])
        cov_matrix = np.outer(volatilities, volatilities) * correlation

        return {
            'expected_returns': expected_returns,
            'cov_matrix': cov_matrix,
            'n_assets': n_assets
        }

    def test_service_initialization(self, service):
        """测试服务初始化"""
        assert service is not None

    def test_mean_variance_optimization(self, service, sample_data):
        """测试均值-方差优化"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        result = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            risk_aversion=1.0
        )

        assert 'weights' in result
        assert 'expected_return' in result
        assert 'risk' in result
        assert 'sharpe' in result

        # 验证权重
        weights = result['weights']
        assert len(weights) == sample_data['n_assets']
        assert np.isclose(np.sum(weights), 1.0, atol=1e-5)
        assert np.all(weights >= -1e-6)  # 多头约束（允许小误差）

    def test_minimum_variance(self, service, sample_data):
        """测试最小方差优化"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        result = service.minimum_variance(
            cov_matrix=sample_data['cov_matrix']
        )

        assert 'weights' in result
        assert 'risk' in result

        # 验证权重
        weights = result['weights']
        assert len(weights) == sample_data['n_assets']
        assert np.isclose(np.sum(weights), 1.0, atol=1e-5)
        assert np.all(weights >= -1e-6)

    def test_maximum_sharpe(self, service, sample_data):
        """测试最大夏普比率优化"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        result = service.maximum_sharpe(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            risk_free_rate=0.02
        )

        assert 'weights' in result
        assert 'expected_return' in result
        assert 'risk' in result
        assert 'sharpe' in result

        # 验证夏普比率计算
        weights = result['weights']
        assert len(weights) == sample_data['n_assets']
        assert np.isclose(np.sum(weights), 1.0, atol=1e-5)

        # 验证夏普比率
        expected_sharpe = (result['expected_return'] - 0.02) / result['risk']
        assert np.isclose(result['sharpe'], expected_sharpe, atol=1e-4)

    def test_risk_parity(self, service, sample_data):
        """测试风险平价优化"""
        result = service.risk_parity(
            cov_matrix=sample_data['cov_matrix']
        )

        assert 'weights' in result
        assert 'risk' in result
        assert 'risk_contributions' in result

        # 验证权重
        weights = result['weights']
        assert len(weights) == sample_data['n_assets']
        assert np.isclose(np.sum(weights), 1.0, atol=1e-5)
        assert np.all(weights >= 0)

        # 验证风险贡献接近相等
        risk_contrib = result['risk_contributions']
        assert len(risk_contrib) == sample_data['n_assets']
        # 风险贡献应该比较接近（允许一定误差）
        cv = np.std(risk_contrib) / np.mean(risk_contrib)  # 变异系数
        assert cv < 0.5, f"Risk contributions not balanced (CV={cv:.3f})"

    def test_long_only_constraint(self, service, sample_data):
        """测试多头约束"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        constraints = {'long_only': True}

        result = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            constraints=constraints
        )

        weights = result['weights']
        assert np.all(weights >= -1e-6), "Long-only constraint violated"

    def test_max_weight_constraint(self, service, sample_data):
        """测试最大权重约束"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        max_weight = 0.3
        constraints = {
            'long_only': True,
            'max_weight': max_weight
        }

        result = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            constraints=constraints
        )

        weights = result['weights']
        assert np.all(weights <= max_weight + 1e-5), f"Max weight constraint violated"

    def test_min_weight_constraint(self, service, sample_data):
        """测试最小权重约束"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        min_weight = 0.1
        constraints = {
            'long_only': True,
            'min_weight': min_weight
        }

        result = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            constraints=constraints
        )

        weights = result['weights']
        assert np.all(weights >= min_weight - 1e-5), "Min weight constraint violated"

    def test_risk_aversion_effect(self, service, sample_data):
        """测试风险厌恶系数的影响"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        # 低风险厌恶（激进）
        result_aggressive = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            risk_aversion=0.5
        )

        # 高风险厌恶（保守）
        result_conservative = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            risk_aversion=2.0
        )

        # 保守组合的风险应该更低
        assert result_conservative['risk'] <= result_aggressive['risk']

    def test_fallback_when_cvxpy_unavailable(self, service):
        """测试 cvxpy 不可用时的降级"""
        if CVXPY_AVAILABLE:
            pytest.skip("cvxpy is available, cannot test unavailable scenario")

        result = service.mean_variance_optimization(
            expected_returns=np.array([0.1, 0.1, 0.1]),
            cov_matrix=np.eye(3)
        )

        # 应该返回等权重
        assert 'weights' in result
        assert 'method' in result
        assert result['method'] == 'equal_weight_fallback'
        assert np.allclose(result['weights'], 1/3)

    def test_portfolio_risk_calculation(self, service, sample_data):
        """测试组合风险计算的正确性"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        result = service.minimum_variance(
            cov_matrix=sample_data['cov_matrix']
        )

        # 手工计算风险
        weights = result['weights']
        manual_risk = np.sqrt(weights @ sample_data['cov_matrix'] @ weights)

        assert np.isclose(result['risk'], manual_risk, atol=1e-5)

    def test_different_risk_aversions(self, service, sample_data):
        """测试不同风险厌恶系数"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        risk_aversions = [0.5, 1.0, 2.0, 5.0]
        results = []

        for gamma in risk_aversions:
            result = service.mean_variance_optimization(
                expected_returns=sample_data['expected_returns'],
                cov_matrix=sample_data['cov_matrix'],
                risk_aversion=gamma
            )
            results.append(result)

        # 验证随着风险厌恶增加，风险降低
        risks = [r['risk'] for r in results]
        assert all(risks[i] >= risks[i+1] - 1e-5 for i in range(len(risks)-1))

    def test_edge_case_single_asset(self, service):
        """测试单个资产的情况"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        result = service.mean_variance_optimization(
            expected_returns=np.array([0.10]),
            cov_matrix=np.array([[0.04]]),
            risk_aversion=1.0
        )

        # 单个资产应该全仓
        assert np.isclose(result['weights'][0], 1.0, atol=1e-5)

    def test_edge_case_identical_assets(self, service):
        """测试相同资产的情况"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        # 3个完全相同的资产
        result = service.mean_variance_optimization(
            expected_returns=np.array([0.10, 0.10, 0.10]),
            cov_matrix=np.array([
                [0.04, 0.04, 0.04],
                [0.04, 0.04, 0.04],
                [0.04, 0.04, 0.04]
            ]),
            risk_aversion=1.0
        )

        # 应该是等权重（或接近等权重）
        assert len(result['weights']) == 3
        assert np.allclose(result['weights'], 1/3, atol=0.1)


class TestAdvancedOptimization:
    """测试高级优化功能"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return PortfolioOptimizationService()

    @pytest.fixture
    def sample_data(self):
        """创建示例数据"""
        np.random.seed(42)
        n_assets = 6

        # 模拟预期收益率
        expected_returns = np.array([0.10, 0.12, 0.08, 0.15, 0.09, 0.11])

        # 模拟协方差矩阵
        volatilities = np.array([0.15, 0.20, 0.12, 0.25, 0.18, 0.16])
        correlation = np.array([
            [1.0, 0.3, 0.2, 0.1, 0.4, 0.2],
            [0.3, 1.0, 0.4, 0.2, 0.3, 0.3],
            [0.2, 0.4, 1.0, 0.1, 0.2, 0.2],
            [0.1, 0.2, 0.1, 1.0, 0.3, 0.1],
            [0.4, 0.3, 0.2, 0.3, 1.0, 0.3],
            [0.2, 0.3, 0.2, 0.1, 0.3, 1.0]
        ])
        cov_matrix = np.outer(volatilities, volatilities) * correlation

        return {
            'expected_returns': expected_returns,
            'cov_matrix': cov_matrix,
            'n_assets': n_assets
        }

    def test_sector_constraints(self, service, sample_data):
        """测试行业约束"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        # 行业映射：0,1=金融，2,3=科技，4,5=消费
        sector_mapping = {0: 'finance', 1: 'finance', 2: 'tech', 3: 'tech', 4: 'consumer', 5: 'consumer'}
        sector_limits = {
            'finance': (0.2, 0.4),   # 金融20-40%
            'tech': (0.3, 0.5),      # 科技30-50%
            'consumer': (0.1, 0.3)   # 消费10-30%
        }

        constraints = {
            'long_only': True,
            'sector_mapping': sector_mapping,
            'sector_limits': sector_limits
        }

        result = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            risk_aversion=1.0,
            constraints=constraints
        )

        # 验证行业权重
        weights = result['weights']
        finance_weight = weights[0] + weights[1]
        tech_weight = weights[2] + weights[3]
        consumer_weight = weights[4] + weights[5]

        assert 0.2 - 0.01 <= finance_weight <= 0.4 + 0.01
        assert 0.3 - 0.01 <= tech_weight <= 0.5 + 0.01
        assert 0.1 - 0.01 <= consumer_weight <= 0.3 + 0.01

    def test_turnover_constraint(self, service, sample_data):
        """测试换手率约束"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        # 当前持仓
        current_weights = np.array([0.2, 0.2, 0.2, 0.2, 0.1, 0.1])

        constraints = {
            'long_only': True,
            'current_weights': current_weights,
            'max_turnover': 0.2  # 最大20%换手率
        }

        result = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            risk_aversion=1.0,
            constraints=constraints
        )

        # 计算实际换手率
        weights = result['weights']
        turnover = np.sum(np.abs(weights - current_weights)) / 2

        assert turnover <= 0.2 + 0.01  # 允许小误差

    def test_mean_cvar_optimization(self, service):
        """测试均值-CVaR优化"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        # 生成收益率情景
        np.random.seed(42)
        n_scenarios = 100
        n_assets = 4

        # 模拟情景（正态分布）
        returns_scenarios = np.random.normal(0.001, 0.02, (n_scenarios, n_assets))

        result = service.mean_cvar_optimization(
            returns_scenarios=returns_scenarios,
            confidence_level=0.95,
            constraints={'long_only': True}
        )

        assert 'weights' in result
        assert 'var' in result
        assert 'cvar' in result

        # 验证权重
        weights = result['weights']
        assert len(weights) == n_assets
        assert np.isclose(np.sum(weights), 1.0, atol=1e-5)
        assert np.all(weights >= -1e-6)

    def test_combined_constraints(self, service, sample_data):
        """测试组合多种约束"""
        if not CVXPY_AVAILABLE:
            pytest.skip("cvxpy not available")

        current_weights = np.array([0.15, 0.15, 0.2, 0.2, 0.15, 0.15])
        sector_mapping = {0: 'A', 1: 'A', 2: 'B', 3: 'B', 4: 'C', 5: 'C'}
        sector_limits = {'A': (0.2, 0.4), 'B': (0.3, 0.5), 'C': (0.1, 0.3)}

        constraints = {
            'long_only': True,
            'max_weight': 0.25,
            'min_weight': 0.05,
            'current_weights': current_weights,
            'max_turnover': 0.3,
            'sector_mapping': sector_mapping,
            'sector_limits': sector_limits
        }

        result = service.mean_variance_optimization(
            expected_returns=sample_data['expected_returns'],
            cov_matrix=sample_data['cov_matrix'],
            risk_aversion=1.0,
            constraints=constraints
        )

        # 验证所有约束
        weights = result['weights']

        # 权重约束
        assert np.all(weights >= 0.05 - 0.01)
        assert np.all(weights <= 0.25 + 0.01)

        # 换手率
        turnover = np.sum(np.abs(weights - current_weights)) / 2
        assert turnover <= 0.3 + 0.01

        # 行业约束
        sector_A = weights[0] + weights[1]
        sector_B = weights[2] + weights[3]
        sector_C = weights[4] + weights[5]
        assert 0.2 - 0.01 <= sector_A <= 0.4 + 0.01
        assert 0.3 - 0.01 <= sector_B <= 0.5 + 0.01
        assert 0.1 - 0.01 <= sector_C <= 0.3 + 0.01
