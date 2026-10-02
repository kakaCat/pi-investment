"""
测试 StrategyOptimizer 并行回测执行引擎
"""
import pytest
from unittest.mock import Mock, patch
from application.services.strategy_optimizer import StrategyOptimizer


class TestStrategyOptimizer:
    """测试策略优化器"""

    def test_optimize_returns_sorted_results_by_sharpe(self):
        """测试优化返回按 Sharpe 排序的结果"""
        # Mock StrategyCodeService
        # 2026-10-02（REQ-261001145152-3982 审查）：**mock 改为"按参数键控"**。
        # 原写法是 `side_effect = [1.5, 2.0, 1.2]`（**按调用先后**依次返回），但优化器是
        # **并行执行**（默认 10 个 worker），谁先回谁先拿到列表里的下一个值 →
        # 参数与得分的对应关系被打乱，本用例**结构性 flaky**（本轮实测首位变成了
        # {'fast': 5, 'slow': 50} 这个最低分组合）。改为按 `params_override` 查表，
        # 与执行顺序无关。
        _score_by_params = {
            (5, 20):  {'sharpe_ratio': 1.5, 'total_return': 0.10, 'max_drawdown': -0.05, 'win_rate': 0.60},
            (10, 30): {'sharpe_ratio': 2.0, 'total_return': 0.15, 'max_drawdown': -0.08, 'win_rate': 0.65},
            (5, 50):  {'sharpe_ratio': 1.2, 'total_return': 0.08, 'max_drawdown': -0.03, 'win_rate': 0.55},
        }

        def _fake_backtest(*args, **kwargs):
            override = kwargs.get('params_override') or {}
            key = (override.get('fast'), override.get('slow'))
            return _score_by_params[key]

        mock_service = Mock()
        mock_service.backtest_strategy.side_effect = _fake_backtest

        optimizer = StrategyOptimizer(mock_service)
        param_grid = [
            {'fast': 5, 'slow': 20},
            {'fast': 10, 'slow': 30},
            {'fast': 5, 'slow': 50},
        ]

        results = optimizer.optimize(
            strategy_id=1,
            symbol='000001.SH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            param_grid=param_grid
        )

        # 验证返回结果按 Sharpe 降序排列
        assert len(results) == 3
        assert results[0]['params'] == {'fast': 10, 'slow': 30}
        assert results[0]['sharpe_ratio'] == 2.0
        assert results[1]['params'] == {'fast': 5, 'slow': 20}
        assert results[1]['sharpe_ratio'] == 1.5
        assert results[2]['params'] == {'fast': 5, 'slow': 50}
        assert results[2]['sharpe_ratio'] == 1.2

    def test_optimize_handles_backtest_failure(self):
        """测试优化处理回测失败的情况"""
        mock_service = Mock()
        mock_service.backtest_strategy.side_effect = [
            {'sharpe_ratio': 1.5, 'total_return': 0.10, 'max_drawdown': -0.05, 'win_rate': 0.60},
            ValueError("K线数据不足"),
            {'sharpe_ratio': 1.2, 'total_return': 0.08, 'max_drawdown': -0.03, 'win_rate': 0.55},
        ]

        optimizer = StrategyOptimizer(mock_service)
        param_grid = [
            {'fast': 5, 'slow': 20},
            {'fast': 10, 'slow': 30},
            {'fast': 5, 'slow': 50},
        ]

        results = optimizer.optimize(
            strategy_id=1,
            symbol='000001.SH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            param_grid=param_grid
        )

        # 验证只返回成功的结果
        assert len(results) == 2
        assert results[0]['sharpe_ratio'] == 1.5
        assert results[1]['sharpe_ratio'] == 1.2

    def test_optimize_returns_empty_when_all_fail(self):
        """测试所有回测都失败时返回空列表"""
        mock_service = Mock()
        mock_service.backtest_strategy.side_effect = ValueError("数据不足")

        optimizer = StrategyOptimizer(mock_service)
        param_grid = [{'fast': 5, 'slow': 20}]

        results = optimizer.optimize(
            strategy_id=1,
            symbol='000001.SH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            param_grid=param_grid
        )

        assert len(results) == 0

    def test_optimize_includes_all_metrics(self):
        """测试优化结果包含所有关键指标"""
        mock_service = Mock()
        mock_service.backtest_strategy.return_value = {
            'sharpe_ratio': 1.8,
            'total_return': 0.12,
            'max_drawdown': -0.06,
            'win_rate': 0.62,
            'total_trades': 45
        }

        optimizer = StrategyOptimizer(mock_service)
        param_grid = [{'fast': 10, 'slow': 30}]

        results = optimizer.optimize(
            strategy_id=1,
            symbol='000001.SH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            param_grid=param_grid
        )

        assert len(results) == 1
        result = results[0]
        assert result['params'] == {'fast': 10, 'slow': 30}
        assert result['sharpe_ratio'] == 1.8
        assert result['total_return'] == 0.12
        assert result['max_drawdown'] == -0.06
        assert result['win_rate'] == 0.62
        assert result['total_trades'] == 45

    def test_optimize_with_empty_grid_returns_empty(self):
        """测试空参数网格返回空结果"""
        mock_service = Mock()
        optimizer = StrategyOptimizer(mock_service)

        results = optimizer.optimize(
            strategy_id=1,
            symbol='000001.SH',
            start_date='2024-01-01',
            end_date='2024-12-31',
            param_grid=[]
        )

        assert len(results) == 0
        mock_service.backtest_strategy.assert_not_called()
