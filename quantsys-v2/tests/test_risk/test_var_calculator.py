"""
VaR计算器测试套件 (adapted for quantlib API)

测试覆盖:
1. 历史模拟法VaR
2. 参数法VaR
3. 蒙特卡洛法VaR
4. CVaR计算
5. 完整风险指标
6. 边界条件
"""
import pytest
import numpy as np
import pandas as pd

from domain.quantlib.risk.var import VaRCalculator, quick_var, quick_cvar
from domain.quantlib.risk.cvar import CVaRCalculator
from domain.quantlib.exceptions import InsufficientDataError, DataValidationError


class TestVaRCalculator:
    """VaR计算器测试类"""

    @pytest.fixture
    def sample_returns(self):
        """生成样本收益率数据"""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 1000))

    @pytest.fixture
    def negative_returns(self):
        """生成负收益率数据（熊市）"""
        np.random.seed(42)
        return pd.Series(np.random.normal(-0.002, 0.03, 1000))

    # ========== 基础VaR测试 ==========

    def test_historical_var_is_positive(self, sample_returns):
        """测试历史模拟法VaR应该是正数（quantlib返回绝对值）"""
        calculator = VaRCalculator()
        result = calculator.calculate(sample_returns, confidence_level=0.95, method='historical')
        var_95 = result['value']
        assert var_95 > 0, "VaR应该是正数（表示损失绝对值）"

    def test_historical_var_in_reasonable_range(self, sample_returns):
        """测试VaR在合理范围内"""
        calculator = VaRCalculator()
        var_95 = calculator.calculate(sample_returns, confidence_level=0.95, method='historical')['value']
        assert 0 < var_95 < 0.1, "VaR应该在合理范围内"

    def test_var_99_worse_than_var_95(self, sample_returns):
        """测试99% VaR应该比95% VaR更大（更大损失）"""
        calculator = VaRCalculator()
        var_95 = calculator.calculate(sample_returns, confidence_level=0.95, method='historical')['value']
        var_99 = calculator.calculate(sample_returns, confidence_level=0.99, method='historical')['value']
        assert var_99 > var_95, "99% VaR应该比95% VaR更大"

    # ========== CVaR测试 ==========

    def test_cvar_worse_than_var(self, sample_returns):
        """测试CVaR应该比VaR更大"""
        var_calc = VaRCalculator()
        cvar_calc = CVaRCalculator()
        var = var_calc.calculate(sample_returns, confidence_level=0.95, method='historical')['value']
        cvar = cvar_calc.calculate(sample_returns, confidence_level=0.95, method='historical')['value']
        assert cvar > var, "CVaR应该比VaR更大"

    def test_cvar_is_tail_average(self, sample_returns):
        """测试CVaR是尾部损失的平均值"""
        cvar_calc = CVaRCalculator()
        cvar = cvar_calc.calculate(sample_returns, confidence_level=0.95, method='historical')['value']

        # 手动计算尾部平均
        var_threshold = np.percentile(sample_returns, 5)
        tail_losses = sample_returns[sample_returns <= var_threshold]
        expected_cvar = abs(tail_losses.mean())
        assert abs(cvar - expected_cvar) < 0.01, "CVaR应该接近尾部损失平均值"

    # ========== 多种方法对比 ==========

    def test_parametric_var(self, sample_returns):
        """测试参数法VaR"""
        calculator = VaRCalculator()
        var = calculator.calculate(sample_returns, confidence_level=0.95, method='parametric')['value']
        assert var > 0, "参数法VaR应该是正数"
        assert 0 < var < 0.1, "参数法VaR应该在合理范围"

    def test_monte_carlo_var(self, sample_returns):
        """测试蒙特卡洛法VaR"""
        calculator = VaRCalculator()
        var = calculator.calculate(sample_returns, confidence_level=0.95, method='monte_carlo')['value']
        assert var > 0, "蒙特卡洛VaR应该是正数"
        assert 0 < var < 0.1, "蒙特卡洛VaR应该在合理范围"

    def test_compare_methods(self, sample_returns):
        """测试多种方法的对比"""
        calculator = VaRCalculator()
        result = calculator.calculate_multiple_confidence_levels(
            sample_returns, confidence_levels=[0.90, 0.95, 0.99], method='historical'
        )
        values = result['value']
        assert 'var_90' in values
        assert 'var_95' in values
        assert 'var_99' in values
        # 所有方法的结果应该递增
        assert values['var_99'] > values['var_95'] > values['var_90']

    # ========== 完整风险指标测试 ==========

    def test_risk_metrics_completeness(self, sample_returns):
        """测试风险指标的完整性"""
        calculator = VaRCalculator()
        metrics = calculator.calculate_risk_metrics(sample_returns)

        required_keys = ['var_95', 'var_99', 'cvar_95', 'cvar_99',
                        'max_drawdown', 'sharpe_ratio', 'volatility', 'mean_return']
        for key in required_keys:
            assert key in metrics, f"缺少指标: {key}"

    def test_max_drawdown_is_positive(self, sample_returns):
        """测试最大回撤应该是正数（quantlib返回绝对值）"""
        calculator = VaRCalculator()
        metrics = calculator.calculate_risk_metrics(sample_returns)
        assert metrics['max_drawdown'] >= 0, "最大回撤应该是正数或零(绝对值)"

    def test_sharpe_ratio_calculation(self, sample_returns):
        """测试夏普比率计算"""
        calculator = VaRCalculator()
        metrics = calculator.calculate_risk_metrics(sample_returns)
        if sample_returns.mean() > 0:
            assert metrics['sharpe_ratio'] > 0, "正收益应该有正夏普比率"

    # ========== 边界条件测试 ==========

    def test_empty_returns(self):
        """测试空收益率序列"""
        calculator = VaRCalculator()
        empty_returns = []
        with pytest.raises((InsufficientDataError, DataValidationError)):
            calculator.calculate(empty_returns, confidence_level=0.95, method='historical')

    def test_single_return_insufficient(self):
        """测试单个收益率应该抛出InsufficientDataError"""
        calculator = VaRCalculator()
        single_return = pd.Series([0.01])
        with pytest.raises(InsufficientDataError):
            calculator.calculate(single_return, confidence_level=0.95, method='historical')

    def test_all_positive_returns(self):
        """测试全部正收益（确保足够数据量）"""
        calculator = VaRCalculator()
        positive_returns = pd.Series([0.01] * 50)
        var = calculator.calculate(positive_returns, confidence_level=0.95, method='historical')['value']
        assert var > 0, "全部相同正收益时VaR应该较小（但仍为正数）"

    def test_all_negative_returns(self, negative_returns):
        """测试全部负收益（熊市）"""
        calculator = VaRCalculator()
        metrics = calculator.calculate_risk_metrics(negative_returns)
        assert metrics['var_95'] > 0, "熊市VaR应该是正数（更大损失）"
        assert metrics['sharpe_ratio'] < 0, "熊市夏普比率应该是负数"

    # ========== 便捷函数测试 ==========

    def test_quick_var_function(self, sample_returns):
        """测试快速VaR函数"""
        var = quick_var(sample_returns, 0.95)
        assert isinstance(var, float), "应该返回float"
        assert var > 0, "VaR应该是正数"

    def test_quick_cvar_function(self, sample_returns):
        """测试快速CVaR函数"""
        cvar = quick_cvar(sample_returns, 0.95)
        assert isinstance(cvar, float), "应该返回float"
        assert cvar > 0, "CVaR应该是正数"

    # ========== 性能测试 ==========

    def test_performance_large_dataset(self):
        """测试大数据集性能"""
        import time
        np.random.seed(42)
        large_returns = pd.Series(np.random.normal(0.001, 0.02, 10000))

        calculator = VaRCalculator()
        start = time.time()
        var = calculator.calculate(large_returns, confidence_level=0.95, method='historical')['value']
        elapsed = time.time() - start

        assert elapsed < 1.0, f"计算时间应该<1s，实际: {elapsed*1000:.2f}ms"
        assert var > 0, "VaR应该是正数"


# ========== 集成测试 ==========

class TestVaRIntegration:
    """VaR计算器集成测试"""

    def test_real_world_scenario(self):
        """测试真实场景：股票组合风险评估"""
        np.random.seed(42)
        daily_returns = pd.Series(np.random.normal(0.0005, 0.015, 252))

        calculator = VaRCalculator()
        metrics = calculator.calculate_risk_metrics(daily_returns)

        assert 0 < metrics['var_95'] < 0.10, "VaR95应该在合理范围"
        assert metrics['cvar_95'] > metrics['var_95'], "CVaR应该比VaR更大"
        assert 0 <= metrics['max_drawdown'] < 0.5, "最大回撤应该在合理范围"
        assert -5 < metrics['sharpe_ratio'] < 5, "夏普比率应该在合理范围"

    def test_method_consistency(self):
        """测试方法一致性：多次计算应该得到相同结果"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 1000))

        calculator = VaRCalculator()
        var1 = calculator.calculate(returns, confidence_level=0.95, method='historical')['value']
        var2 = calculator.calculate(returns, confidence_level=0.95, method='historical')['value']
        assert var1 == var2, "相同输入应该得到相同结果"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
