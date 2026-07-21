"""
市场冲击模型测试 - Team C
"""
import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from domain.quantlib.backtest.market_impact import AlmgrenChrissModel


class TestAlmgrenChrissModel:
    """市场冲击模型测试"""

    @pytest.fixture
    def model(self):
        """创建模型实例"""
        return AlmgrenChrissModel(
            permanent_impact_coef=0.1,
            temporary_impact_coef=0.01,
            volatility=0.02
        )

    def test_initialization(self, model):
        """测试初始化"""
        assert model is not None
        assert model.gamma == 0.1
        assert model.eta == 0.01
        assert model.sigma == 0.02

    def test_calculate_impact(self, model):
        """测试冲击计算"""
        result = model.calculate_impact(
            order_size=10000,
            adv=1000000,
            price=100.0,        execution_time=1.0
        )

        assert 'permanent_impact' in result
        assert 'temporary_impact' in result
        assert 'total_impact' in result
        assert 'impact_bps' in result

        assert result['total_impact'] > 0
        assert result['impact_bps'] > 0

    def test_impact_increases_with_order_size(self, model):
        """测试冲击随订单大小增加"""
        small_order = model.calculate_impact(5000, 1000000, 100.0)
        large_order = model.calculate_impact(50000, 1000000, 100.0)

        assert large_order['total_impact'] > small_order['total_impact']

    def test_optimal_execution_schedule(self, model):
        """测试最优执行策略"""
        schedule = model.optimal_execution_schedule(
            total_shares=10000,
            total_time=1.0
        )

        assert len(schedule) == 390  # 1天 = 390分钟
        assert np.sum(schedule) > 0
        assert np.isclose(np.sum(schedule), 10000, rtol=0.01)

    def test_estimate_total_cost(self, model):
        """测试总成本估算"""
        result = model.estimate_total_cost(
            order_size=10000,
            adv=1000000,
            price=100.0
        )

        assert 'market_impact' in result
        assert 'commission' in result
        assert 'slippage' in result
        assert 'total_cost' in result

        assert result['total_cost'] > result['market_impact']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
