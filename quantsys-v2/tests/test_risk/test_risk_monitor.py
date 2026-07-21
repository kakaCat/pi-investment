"""
风险监控服务测试 - Team A
"""
import pytest
import pandas as pd
import numpy as np

from domain.quantlib.risk.risk_monitor import RiskMonitorService
from domain.quantlib.risk.var import VaRCalculator


class TestRiskMonitorService:
    """风险监控服务测试"""

    @pytest.fixture
    def monitor(self):
        """创建监控服务实例"""
        return RiskMonitorService()

    @pytest.fixture
    def sample_returns(self):
        """生成样本收益率"""
        np.random.seed(42)
        return list(np.random.normal(0.001, 0.02, 100))

    def test_initialization(self, monitor):
        """测试初始化"""
        assert monitor is not None
        assert monitor.var_calculator is not None
        assert monitor.risk_limits is not None

    def test_get_realtime_metrics_insufficient_data(self, monitor):
        """测试数据不足时的指标"""
        metrics = monitor.get_realtime_metrics()

        assert 'timestamp' in metrics
        assert metrics['var_95'] is None
        assert metrics['alerts'] == []

    def test_get_realtime_metrics_with_data(self, monitor, sample_returns):
        """测试有数据时的指标"""
        monitor.portfolio_returns = sample_returns

        metrics = monitor.get_realtime_metrics()

        assert metrics['var_95'] is not None
        assert metrics['cvar_95'] is not None
        assert metrics['sharpe_ratio'] is not None
        assert isinstance(metrics['alerts'], list)

    def test_check_risk_limits_pass(self, monitor):
        """测试风险限额检查通过"""
        position = {
            'symbol': '000001',
            'quantity': 100,
            'price': 100.0,
            'portfolio_value': 100000
        }

        result = monitor.check_risk_limits(position)

        assert result['passed'] is True
        assert len(result['violations']) == 0

    def test_check_risk_limits_violation(self, monitor):
        """测试风险限额违规"""
        position = {
            'symbol': '000001',
            'quantity': 3000,  # 30万，超过20%
            'price': 100.0,
            'portfolio_value': 100000
        }

        result = monitor.check_risk_limits(position)

        assert result['passed'] is False
        assert len(result['violations']) > 0

    def test_add_return(self, monitor):
        """测试添加收益率"""
        monitor.add_return(0.01)
        monitor.add_return(-0.02)

        assert len(monitor.portfolio_returns) == 2
        assert monitor.portfolio_returns[0] == 0.01

    def test_add_return_limit(self, monitor):
        """测试收益率数量限制"""
        # 添加300个收益率
        for i in range(300):
            monitor.add_return(0.001)

        # 应该只保留最近252个
        assert len(monitor.portfolio_returns) == 252


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
