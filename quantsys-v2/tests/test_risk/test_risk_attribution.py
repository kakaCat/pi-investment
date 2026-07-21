"""
风险归因分析测试 (adapted for quantlib API)
"""
import pytest
import pandas as pd
import numpy as np

from domain.quantlib.risk.attribution import RiskAttributionCalculator


class TestRiskAttribution:
    """风险归因分析测试"""

    @pytest.fixture
    def attribution(self):
        """创建归因分析实例"""
        return RiskAttributionCalculator()

    @pytest.fixture
    def sample_data(self):
        """生成样本数据"""
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100)
        returns_df = pd.DataFrame({
            'Asset_A': np.random.normal(0.001, 0.02, 100),
            'Asset_B': np.random.normal(0.0008, 0.015, 100),
            'Asset_C': np.random.normal(0.0012, 0.025, 100),
        }, index=dates)
        weights = [0.4, 0.35, 0.25]
        return returns_df, weights

    def test_initialization(self, attribution):
        """测试初始化"""
        assert attribution is not None

    def test_risk_attribution(self, attribution, sample_data):
        """测试风险归因（资产层面）"""
        returns_df, weights = sample_data
        result = attribution.calculate(returns_df, weights)

        assert 'value' in result
        assert 'portfolio_volatility' in result['value']
        contributions = result['value']['contributions']
        assert 'Asset_A' in contributions
        assert 'percentage_contribution' in contributions['Asset_A']
        assert len(contributions) == 3

    def test_group_attribution(self, attribution, sample_data):
        """测试分组归因"""
        returns_df, weights = sample_data
        groups = ['Tech', 'Tech', 'Finance']

        result = attribution.calculate_group_attribution(returns_df, weights, groups)

        assert 'value' in result
        group_contributions = result['value']['group_contributions']
        assert 'Tech' in group_contributions
        assert 'Finance' in group_contributions
        assert len(group_contributions) == 2

    def test_concentration_metrics(self, attribution, sample_data):
        """测试集中度指标"""
        returns_df, weights = sample_data
        result = attribution.calculate_concentration_metrics(returns_df, weights)

        metrics = result['value']
        assert 'herfindahl_index' in metrics
        assert 'effective_n_assets' in metrics
        assert 'max_contribution' in metrics
        assert 'top_3_contribution' in metrics


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
