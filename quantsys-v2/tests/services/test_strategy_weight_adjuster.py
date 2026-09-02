"""
测试 StrategyWeightAdjuster 服务
"""
import pytest
from unittest.mock import Mock
from application.services.strategy_weight_adjuster import StrategyWeightAdjuster


def _mock_repos(sample_size: int = 0, static_weight: float = 0.30):
    """构造测试用的 Mock 仓库"""
    performance_repo = Mock()
    performance_repo.get_statistics.return_value = {'total_trades': sample_size}
    weight_repo = Mock()
    weight_repo.get_static_weight.return_value = static_weight
    return weight_repo, performance_repo


def test_get_weight_static_mode(db_connection):
    """测试静态模式权重查询（样本 < 30）"""
    weight_repo, performance_repo = _mock_repos(sample_size=10)
    adjuster = StrategyWeightAdjuster(
        weight_repo=weight_repo,
        performance_repo=performance_repo,
    )

    result = adjuster.get_weight(
        strategy_name='my_ma_cross',
        strategy_type='trend_following',
        market_style='momentum'
    )

    assert result['mode'] == 'static'
    assert result['weight_adjustment'] == 1.30  # 1.0 + 0.30
    assert result['sample_size'] < 30
    assert result['strategy_name'] == 'my_ma_cross'
    assert result['strategy_type'] == 'trend_following'
    assert result['market_style'] == 'momentum'


def test_get_weight_dynamic_mode(db_connection):
    """测试动态模式权重计算（样本 >= 30）"""
    weight_repo, performance_repo = _mock_repos(sample_size=35)
    adjuster = StrategyWeightAdjuster(
        weight_repo=weight_repo,
        performance_repo=performance_repo,
    )

    # 模拟按风格的历史表现，使动态计算有数据可用
    adjuster._get_performance_by_style = Mock(return_value={
        'momentum': {'sharpe': 1.8, 'win_rate': 0.65},
        'oscillation': {'sharpe': 0.6, 'win_rate': 0.42},
    })

    result = adjuster.get_weight(
        strategy_name='mature_strategy',
        strategy_type='trend_following',
        market_style='momentum'
    )

    assert result['mode'] == 'dynamic'
    assert result['sample_size'] >= 30
    assert 0.6 <= result['weight_adjustment'] <= 2.0
    assert 'historical_performance' in result
    assert result['strategy_name'] == 'mature_strategy'


def test_get_weight_unknown_style(db_connection):
    """测试未知风格时的处理"""
    weight_repo, performance_repo = _mock_repos(sample_size=10)
    adjuster = StrategyWeightAdjuster(
        weight_repo=weight_repo,
        performance_repo=performance_repo,
    )

    result = adjuster.get_weight(
        strategy_name='my_strategy',
        strategy_type='trend_following',
        market_style='unknown'
    )

    assert result['weight_adjustment'] == 1.0  # 默认权重
    assert result['market_style'] == 'unknown'


def test_get_weight_mixed_market(db_connection):
    """测试混合市场风格时的处理"""
    weight_repo, performance_repo = _mock_repos(sample_size=10)
    adjuster = StrategyWeightAdjuster(
        weight_repo=weight_repo,
        performance_repo=performance_repo,
    )

    result = adjuster.get_weight(
        strategy_name='my_strategy',
        strategy_type='mean_reversion',
        market_style='mixed_market'
    )

    assert result['weight_adjustment'] == 1.0  # 默认权重


def test_get_weight_fallback_on_error(db_connection):
    """测试动态模式失败时回退到静态模式"""
    weight_repo, performance_repo = _mock_repos(sample_size=35)
    adjuster = StrategyWeightAdjuster(
        weight_repo=weight_repo,
        performance_repo=performance_repo,
    )

    # 模拟没有当前市场风格数据，触发回退
    adjuster._get_performance_by_style = Mock(return_value={})

    result = adjuster.get_weight(
        strategy_name='strategy_without_style',
        strategy_type='trend_following',
        market_style='momentum'
    )

    # 应该回退到静态模式
    assert result['weight_adjustment'] == 1.30  # 1.0 + 0.30 (静态权重)
