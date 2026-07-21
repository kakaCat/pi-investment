"""
测试 StrategyWeightAdjuster 服务
"""
import pytest
from application.services.strategy_weight_adjuster import StrategyWeightAdjuster


def test_get_weight_static_mode(db_connection):
    """测试静态模式权重查询（样本 < 30）"""
    adjuster = StrategyWeightAdjuster()

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
    from adapters.outbound.repositories import StrategyPerformanceRepository
    from datetime import date, timedelta

    # 准备测试数据：创建 >= 30 笔交易记录
    perf_repo = StrategyPerformanceORMRepository()
    strategy_name = 'mature_strategy'

    # 创建 35 笔交易记录，分布在不同市场风格
    base_date = date(2024, 1, 1)
    for i in range(35):
        market_style = 'momentum' if i < 20 else 'oscillation'
        pnl_pct = 5.0 if i % 2 == 0 else -2.0  # 模拟盈亏

        perf_repo.create(
            strategy_name=strategy_name,
            symbol='600000.SH',
            signal_date=base_date + timedelta(days=i),
            entry_price=10.0,
            exit_price=10.0 + (pnl_pct / 100 * 10.0),
            pnl_pct=pnl_pct,
            holding_days=3,
            scenario_tags=[market_style],
            params_snapshot={'fast': 5, 'slow': 20},
            source='paper'
        )

    # 执行测试
    adjuster = StrategyWeightAdjuster()
    result = adjuster.get_weight(
        strategy_name=strategy_name,
        strategy_type='trend_following',
        market_style='momentum'
    )

    assert result['mode'] == 'dynamic'
    assert result['sample_size'] >= 30
    assert 0.6 <= result['weight_adjustment'] <= 2.0
    assert 'historical_performance' in result
    assert result['strategy_name'] == strategy_name


def test_get_weight_unknown_style(db_connection):
    """测试未知风格时的处理"""
    adjuster = StrategyWeightAdjuster()

    result = adjuster.get_weight(
        strategy_name='my_strategy',
        strategy_type='trend_following',
        market_style='unknown'
    )

    assert result['weight_adjustment'] == 1.0  # 默认权重
    assert result['market_style'] == 'unknown'


def test_get_weight_mixed_market(db_connection):
    """测试混合市场风格时的处理"""
    adjuster = StrategyWeightAdjuster()

    result = adjuster.get_weight(
        strategy_name='my_strategy',
        strategy_type='mean_reversion',
        market_style='mixed_market'
    )

    assert result['weight_adjustment'] == 1.0  # 默认权重


def test_get_weight_fallback_on_error(db_connection):
    """测试动态模式失败时回退到静态模式"""
    from adapters.outbound.repositories import StrategyPerformanceRepository
    from datetime import date, timedelta

    # 准备测试数据：创建 >= 30 笔交易记录，但没有 market_style 标签
    perf_repo = StrategyPerformanceORMRepository()
    strategy_name = 'strategy_without_style'

    base_date = date(2024, 1, 1)
    for i in range(35):
        perf_repo.create(
            strategy_name=strategy_name,
            symbol='600000.SH',
            signal_date=base_date + timedelta(days=i),
            entry_price=10.0,
            exit_price=10.5,
            pnl_pct=5.0,
            holding_days=3,
            scenario_tags=None,  # 没有市场风格标签
            params_snapshot={'fast': 5, 'slow': 20},
            source='paper'
        )

    # 执行测试
    adjuster = StrategyWeightAdjuster()
    result = adjuster.get_weight(
        strategy_name=strategy_name,
        strategy_type='trend_following',
        market_style='momentum'
    )

    # 应该回退到静态模式
    assert result['weight_adjustment'] == 1.30  # 1.0 + 0.30 (静态权重)
