"""
测试 StrategyPerformanceRepository

RED 阶段：编写失败的测试
"""
import pytest
from datetime import datetime, date
from adapters.outbound.repositories import StrategyPerformanceRepository


@pytest.fixture
def repo():
    """创建测试 repository"""
    repo = StrategyPerformanceORMRepository()

    # 清理测试数据
    cursor = repo.db.cursor()
    cursor.execute("DELETE FROM quant.strategy_performance")
    repo.db.commit()
    cursor.close()

    yield repo

    # 测试后清理
    cursor = repo.db.cursor()
    cursor.execute("DELETE FROM quant.strategy_performance")
    repo.db.commit()
    cursor.close()


def test_create_performance_record(repo):
    """测试创建策略表现记录"""
    record = repo.create(
        strategy_name='ma_cross',
        symbol='000001.SH',
        signal_date=date(2026, 5, 1),
        entry_price=1800.0,
        exit_price=None,
        pnl_pct=None,
        holding_days=0,
        scenario_tags=['rsi_oversold', 'bull_market'],
        params_snapshot={'fast_period': 5, 'slow_period': 20},
        source='paper'
    )

    assert record is not None
    assert record['id'] is not None
    assert record['strategy_name'] == 'ma_cross'
    assert record['symbol'] == '000001.SH'
    assert record['entry_price'] == 1800.0
    assert record['exit_price'] is None
    assert record['source'] == 'paper'


def test_update_exit_price_and_pnl(repo):
    """测试更新出场价格和盈亏"""
    # 创建记录
    record = repo.create(
        strategy_name='turtle',
        symbol='000001.SZ',
        signal_date=date(2026, 5, 1),
        entry_price=10.0,
        source='live'
    )

    # 更新出场价格
    updated = repo.update_exit(
        record_id=record['id'],
        exit_price=11.0,
        holding_days=5
    )

    assert updated is not None
    assert updated['exit_price'] == 11.0
    assert updated['pnl_pct'] == 10.0  # (11.0 - 10.0) / 10.0 * 100
    assert updated['holding_days'] == 5


def test_get_by_strategy_and_symbol(repo):
    """测试按策略和标的查询"""
    # 创建多条记录
    repo.create(
        strategy_name='ma_cross',
        symbol='000001.SH',
        signal_date=date(2026, 5, 1),
        entry_price=1800.0,
        exit_price=1850.0,
        pnl_pct=2.78,
        source='paper'
    )
    repo.create(
        strategy_name='ma_cross',
        symbol='000001.SH',
        signal_date=date(2026, 5, 10),
        entry_price=1850.0,
        exit_price=1820.0,
        pnl_pct=-1.62,
        source='paper'
    )
    repo.create(
        strategy_name='turtle',
        symbol='000001.SH',
        signal_date=date(2026, 5, 15),
        entry_price=1820.0,
        source='paper'
    )

    # 查询 ma_cross + 000001.SH
    records = repo.get_by_strategy_and_symbol('ma_cross', '000001.SH')

    assert len(records) == 2
    assert all(r['strategy_name'] == 'ma_cross' for r in records)
    assert all(r['symbol'] == '000001.SH' for r in records)


def test_get_statistics(repo):
    """测试统计策略表现"""
    # 创建多条已结算记录
    repo.create(
        strategy_name='ma_cross',
        symbol='000001.SH',
        signal_date=date(2026, 5, 1),
        entry_price=1800.0,
        exit_price=1850.0,
        pnl_pct=2.78,
        holding_days=5,
        source='paper'
    )
    repo.create(
        strategy_name='ma_cross',
        symbol='000001.SH',
        signal_date=date(2026, 5, 10),
        entry_price=1850.0,
        exit_price=1820.0,
        pnl_pct=-1.62,
        holding_days=3,
        source='paper'
    )
    repo.create(
        strategy_name='ma_cross',
        symbol='000001.SH',
        signal_date=date(2026, 5, 15),
        entry_price=1820.0,
        exit_price=1900.0,
        pnl_pct=4.40,
        holding_days=7,
        source='paper'
    )

    # 获取统计
    stats = repo.get_statistics('ma_cross', '000001.SH')

    assert stats is not None
    assert stats['total_trades'] == 3
    assert stats['win_trades'] == 2
    assert stats['loss_trades'] == 1
    assert stats['win_rate'] == pytest.approx(66.67, rel=0.01)
    assert stats['avg_pnl_pct'] == pytest.approx(1.85, rel=0.01)  # (2.78 - 1.62 + 4.40) / 3
    assert stats['avg_holding_days'] == pytest.approx(5.0, rel=0.01)  # (5 + 3 + 7) / 3


def test_get_statistics_by_source(repo):
    """测试按来源统计（纸面 vs 实盘）"""
    # 纸面测试记录
    repo.create(
        strategy_name='turtle',
        symbol='000001.SZ',
        signal_date=date(2026, 5, 1),
        entry_price=10.0,
        exit_price=11.0,
        pnl_pct=10.0,
        source='paper'
    )
    # 实盘记录
    repo.create(
        strategy_name='turtle',
        symbol='000001.SZ',
        signal_date=date(2026, 5, 5),
        entry_price=11.0,
        exit_price=10.5,
        pnl_pct=-4.55,
        source='live'
    )

    # 统计纸面测试
    paper_stats = repo.get_statistics('turtle', '000001.SZ', source='paper')
    assert paper_stats['total_trades'] == 1
    assert paper_stats['win_rate'] == 100.0

    # 统计实盘
    live_stats = repo.get_statistics('turtle', '000001.SZ', source='live')
    assert live_stats['total_trades'] == 1
    assert live_stats['win_rate'] == 0.0


def test_get_recent_performance(repo):
    """测试获取最近N条表现记录"""
    # 创建多条记录
    for i in range(10):
        repo.create(
            strategy_name='ma_cross',
            symbol='000001.SH',
            signal_date=date(2026, 5, i + 1),
            entry_price=1800.0 + i * 10,
            exit_price=1810.0 + i * 10,
            pnl_pct=0.56,
            source='paper'
        )

    # 获取最近 5 条
    recent = repo.get_recent(strategy_name='ma_cross', limit=5)

    assert len(recent) == 5
    # 应该按日期降序排列
    assert recent[0]['signal_date'] > recent[4]['signal_date']


def test_filter_by_scenario_tags(repo):
    """测试按场景标签过滤"""
    # 创建带不同标签的记录
    repo.create(
        strategy_name='rsi_reversal',
        symbol='000001.SH',
        signal_date=date(2026, 5, 1),
        entry_price=1800.0,
        exit_price=1850.0,
        pnl_pct=2.78,
        scenario_tags=['rsi_oversold', 'bull_market'],
        source='paper'
    )
    repo.create(
        strategy_name='rsi_reversal',
        symbol='000001.SH',
        signal_date=date(2026, 5, 10),
        entry_price=1850.0,
        exit_price=1820.0,
        pnl_pct=-1.62,
        scenario_tags=['rsi_overbought', 'bear_market'],
        source='paper'
    )

    # 查询包含 rsi_oversold 标签的记录
    records = repo.get_by_scenario_tag('rsi_oversold')

    assert len(records) == 1
    assert 'rsi_oversold' in records[0]['scenario_tags']
