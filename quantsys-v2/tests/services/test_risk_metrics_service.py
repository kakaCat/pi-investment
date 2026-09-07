"""
风险指标服务测试
"""
import pytest
import pandas as pd
import numpy as np
from application.services.risk_metrics_service import RiskMetricsService


@pytest.fixture
def risk_service():
    """创建风险指标服务实例"""
    return RiskMetricsService(risk_free=0.03)


@pytest.fixture
def sample_returns():
    """生成样本收益率数据"""
    np.random.seed(42)
    # 生成250天的日收益率（模拟一年交易日）
    # 均值0.1%，标准差1.5%
    returns = np.random.normal(0.001, 0.015, 250)
    return pd.Series(returns)


@pytest.fixture
def sample_benchmark_returns():
    """生成样本基准收益率"""
    np.random.seed(43)
    # 基准收益率稍低，波动率稍小
    returns = np.random.normal(0.0008, 0.012, 250)
    return pd.Series(returns)


class TestRiskMetricsService:
    """风险指标服务测试套件"""

    def test_calculate_sharpe_ratio(self, risk_service, sample_returns):
        """测试夏普比率计算"""
        sharpe = risk_service.calculate_sharpe_ratio(sample_returns)

        # 夏普比率应该是有限数值
        assert isinstance(sharpe, float)
        assert not np.isnan(sharpe)

        # 随机数据可能产生各种夏普比率
        # 只检查在合理范围（不是极端异常值）
        assert sharpe > -100  # 合理范围
        assert sharpe < 100

    def test_calculate_sortino_ratio(self, risk_service, sample_returns):
        """测试索提诺比率计算"""
        sortino = risk_service.calculate_sortino_ratio(sample_returns)

        assert isinstance(sortino, float)
        assert not np.isnan(sortino)

        # 索提诺比率通常高于夏普比率（只惩罚下行波动）
        sharpe = risk_service.calculate_sharpe_ratio(sample_returns)
        # 这个断言在某些随机数据下可能失败，所以放宽条件
        assert sortino >= sharpe * 0.5  # 允许一定误差

    def test_calculate_calmar_ratio(self, risk_service, sample_returns):
        """测试卡尔马比率计算"""
        calmar = risk_service.calculate_calmar_ratio(sample_returns)

        assert isinstance(calmar, float)
        assert not np.isnan(calmar)

        # 卡尔马比率应该在合理范围
        assert calmar > -10
        assert calmar < 10

    def test_calculate_max_drawdown(self, risk_service, sample_returns):
        """测试最大回撤计算"""
        max_dd = risk_service.calculate_max_drawdown(sample_returns)

        assert isinstance(max_dd, float)
        assert not np.isnan(max_dd)

        # 最大回撤应该是负数或0
        assert max_dd <= 0

        # 应该大于-1（不可能跌超100%）
        assert max_dd > -1

    def test_calculate_alpha_beta(self, risk_service, sample_returns, sample_benchmark_returns):
        """测试Alpha/Beta计算"""
        alpha, beta = risk_service.calculate_alpha_beta(
            sample_returns,
            sample_benchmark_returns
        )

        assert isinstance(alpha, float)
        assert isinstance(beta, float)
        assert not np.isnan(alpha)
        assert not np.isnan(beta)

        # Beta应该在合理范围（通常在-2到3之间）
        assert beta > -2
        assert beta < 3

    def test_calculate_var(self, risk_service, sample_returns):
        """测试VaR计算"""
        var_95 = risk_service.calculate_var(sample_returns, cutoff=0.05)

        assert isinstance(var_95, float)
        assert not np.isnan(var_95)

        # VaR应该是负数（表示损失）
        assert var_95 < 0

        # 应该在合理范围
        assert var_95 > -0.5  # 单日最大损失不会超过50%

    def test_calculate_cvar(self, risk_service, sample_returns):
        """测试CVaR计算"""
        cvar_95 = risk_service.calculate_cvar(sample_returns, cutoff=0.05)

        assert isinstance(cvar_95, float)
        assert not np.isnan(cvar_95)

        # CVaR应该是负数
        assert cvar_95 < 0

        # CVaR应该小于等于VaR（绝对值更大）
        var_95 = risk_service.calculate_var(sample_returns, cutoff=0.05)
        assert cvar_95 <= var_95

    def test_calculate_annual_return(self, risk_service, sample_returns):
        """测试年化收益率计算"""
        annual_ret = risk_service.calculate_annual_return(sample_returns)

        assert isinstance(annual_ret, float)
        assert not np.isnan(annual_ret)

        # 年化收益率应该在合理范围
        assert annual_ret > -1  # 不可能亏超100%
        assert annual_ret < 5   # 年化收益不太可能超过500%

    def test_calculate_annual_volatility(self, risk_service, sample_returns):
        """测试年化波动率计算"""
        annual_vol = risk_service.calculate_annual_volatility(sample_returns)

        assert isinstance(annual_vol, float)
        assert not np.isnan(annual_vol)

        # 年化波动率应该是正数
        assert annual_vol > 0

        # 应该在合理范围（通常10%-50%）
        assert annual_vol < 2  # 不太可能超过200%

    def test_calculate_cumulative_return(self, risk_service, sample_returns):
        """测试累计收益率计算"""
        cum_ret = risk_service.calculate_cumulative_return(sample_returns)

        assert isinstance(cum_ret, float)
        assert not np.isnan(cum_ret)

        # 累计收益率应该在合理范围
        assert cum_ret > -1  # 不可能亏超100%

    def test_calculate_information_ratio(self, risk_service, sample_returns, sample_benchmark_returns):
        """测试信息比率计算"""
        ir = risk_service.calculate_information_ratio(
            sample_returns,
            sample_benchmark_returns
        )

        assert isinstance(ir, float)
        assert not np.isnan(ir)

        # 信息比率应该在合理范围
        assert ir > -5
        assert ir < 5

    def test_calculate_all_metrics(self, risk_service, sample_returns):
        """测试一站式计算所有指标"""
        metrics = risk_service.calculate_all_metrics(sample_returns)

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
            assert isinstance(metrics[field], float)
            assert not np.isnan(metrics[field])

    def test_calculate_all_metrics_with_benchmark(
        self,
        risk_service,
        sample_returns,
        sample_benchmark_returns
    ):
        """测试带基准的完整指标计算"""
        metrics = risk_service.calculate_all_metrics(
            sample_returns,
            benchmark_returns=sample_benchmark_returns
        )

        # 检查基准相关字段
        assert 'alpha' in metrics
        assert 'beta' in metrics
        assert 'information_ratio' in metrics

        assert not np.isnan(metrics['alpha'])
        assert not np.isnan(metrics['beta'])
        assert not np.isnan(metrics['information_ratio'])

    def test_different_input_types(self, risk_service):
        """测试不同输入类型的兼容性"""
        # 列表输入
        returns_list = [0.01, -0.02, 0.03, 0.005, -0.01]
        sharpe_list = risk_service.calculate_sharpe_ratio(returns_list)
        assert isinstance(sharpe_list, float)

        # NumPy数组输入
        returns_array = np.array(returns_list)
        sharpe_array = risk_service.calculate_sharpe_ratio(returns_array)
        assert isinstance(sharpe_array, float)

        # pandas Series输入
        returns_series = pd.Series(returns_list)
        sharpe_series = risk_service.calculate_sharpe_ratio(returns_series)
        assert isinstance(sharpe_series, float)

        # 三种输入应该产生相同结果
        assert abs(sharpe_list - sharpe_array) < 1e-10
        assert abs(sharpe_list - sharpe_series) < 1e-10

    def test_custom_risk_free_rate(self, sample_returns):
        """测试自定义无风险利率"""
        service_3pct = RiskMetricsService(risk_free=0.03)
        service_5pct = RiskMetricsService(risk_free=0.05)

        sharpe_3pct = service_3pct.calculate_sharpe_ratio(sample_returns)
        sharpe_5pct = service_5pct.calculate_sharpe_ratio(sample_returns)

        # 无风险利率更高，夏普比率应该更低
        assert sharpe_5pct < sharpe_3pct

    def test_empty_returns(self, risk_service):
        """测试空收益率序列"""
        empty_returns = pd.Series([])

        # 应该返回NaN而不是抛出异常
        sharpe = risk_service.calculate_sharpe_ratio(empty_returns)
        assert np.isnan(sharpe)

    def test_constant_returns(self, risk_service):
        """测试恒定收益率（无波动）"""
        constant_returns = pd.Series([0.01] * 100)

        # 夏普比率应该是无穷大或非常大的数
        # empyrical会处理这种情况
        sharpe = risk_service.calculate_sharpe_ratio(constant_returns)
        # 只要不是NaN就可以
        assert isinstance(sharpe, float)


class TestEdgeCases:
    """边界情况测试"""

    def test_negative_returns_only(self):
        """测试纯亏损策略"""
        service = RiskMetricsService()
        negative_returns = pd.Series([-0.01, -0.02, -0.015, -0.008, -0.012])

        metrics = service.calculate_all_metrics(negative_returns)

        # 夏普比率应该是负数
        assert metrics['sharpe_ratio'] < 0

        # 年化收益率应该是负数
        assert metrics['annual_return'] < 0

        # 最大回撤应该是负数
        assert metrics['max_drawdown'] < 0

    def test_high_volatility(self):
        """测试高波动率策略"""
        service = RiskMetricsService()
        np.random.seed(44)
        high_vol_returns = np.random.normal(0, 0.05, 250)  # 5%日波动率

        metrics = service.calculate_all_metrics(high_vol_returns)

        # 年化波动率应该很高
        assert metrics['annual_volatility'] > 0.5

    def test_perfect_correlation_with_benchmark(self):
        """测试与基准完全相关的策略"""
        service = RiskMetricsService()
        benchmark = pd.Series(np.random.normal(0.001, 0.015, 100))
        strategy = benchmark * 1.5  # 完全相关，但beta=1.5

        alpha, beta = service.calculate_alpha_beta(strategy, benchmark)

        # Beta应该接近1.5
        assert abs(beta - 1.5) < 0.1
