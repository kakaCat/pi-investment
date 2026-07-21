"""
Walk-Forward分析测试 - Team C
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from domain.quantlib.backtest.walk_forward import WalkForwardAnalysis


class TestWalkForwardAnalysis:
    """Walk-Forward分析测试"""

    @pytest.fixture
    def wfa(self):
        """创建WFA实例"""
        return WalkForwardAnalysis(
            train_period=50,
            test_period=20,
            step_size=10
        )

    @pytest.fixture
    def sample_data(self):
        """生成样本数据"""
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200)
        data = pd.DataFrame({
            'close': np.cumsum(np.random.randn(200)) + 100,
            'volume': np.random.randint(1000, 10000, 200)
        }, index=dates)
        return data

    @pytest.fixture
    def simple_strategy(self):
        """简单策略函数"""
        def strategy(data, ma_period=20):
            returns = data['close'].pct_change()
            return {
                'return': float(returns.mean()),
                'sharpe': float(returns.mean() / returns.std() * np.sqrt(252))
            }
        return strategy

    def test_initialization(self, wfa):
        """测试初始化"""
        assert wfa is not None
        assert wfa.train_period == 50
        assert wfa.test_period == 20
        assert wfa.step_size == 10

    def test_run(self, wfa, sample_data, simple_strategy):
        """测试运行WFA"""
        param_grid = {'ma_period': [10, 20, 30]}

        results = wfa.run(sample_data, simple_strategy, param_grid)

        assert 'periods' in results
        assert 'avg_return' in results
        assert 'avg_sharpe' in results
        assert 'stability' in results
        assert len(results['periods']) > 0

    def test_period_structure(self, wfa, sample_data, simple_strategy):
        """测试周期结构"""
        param_grid = {'ma_period': [20]}

        results = wfa.run(sample_data, simple_strategy, param_grid)
        period = results['periods'][0]

        assert 'train_start' in period
        assert 'train_end' in period
        assert 'test_start' in period
        assert 'test_end' in period
        assert 'best_params' in period
        assert 'test_return' in period
        assert 'test_sharpe' in period


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
