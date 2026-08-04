"""
测试订单盈亏追踪功能

RED 阶段：编写失败的测试
"""
import pytest
from datetime import date, datetime
from application.services.order_service import fill_order, create_order
from application.services.signal_test_log import SignalTestLog
from application.services.data_service import DataService
from adapters.outbound.repositories import StrategyPerformanceRepository


@pytest.fixture
def ds():
    """创建 DataService 实例"""
    return DataService()


@pytest.fixture
def signal_log():
    """创建 SignalTestLog 实例"""
    return SignalTestLog()


@pytest.fixture
def perf_repo():
    """创建 StrategyPerformanceRepository 实例"""
    return StrategyPerformanceRepository()


@pytest.fixture
def cleanup(ds, signal_log, perf_repo):
    """清理测试数据"""
    # 测试前准备：确保测试股票存在
    test_stocks = [
        ('600000.SH', '浦发银行'),
        ('000001.SZ', '平安银行'),
        ('000001.SH', '浦发银行'),
        ('000002.SZ', '万科A'),
    ]

    conn = signal_log._get_conn()
    cursor = conn.cursor()

    for symbol, name in test_stocks:
        cursor.execute(
            """
            INSERT INTO quant.stocks (symbol, name, market, is_active)
            VALUES (%s, %s, %s, true)
            ON CONFLICT (symbol) DO NOTHING
            """,
            (symbol, name, 'SH' if symbol.endswith('.SH') else 'SZ')
        )

    conn.commit()
    cursor.close()
    conn.close()

    yield

    # 清理订单和交易（使用测试股票代码）
    test_symbols = ['600000.SH', '000001.SZ', '000001.SH', '000002.SZ']

    conn = signal_log._get_conn()
    cursor = conn.cursor()

    for symbol in test_symbols:
        cursor.execute("DELETE FROM quant.orders WHERE symbol = %s", (symbol,))
        cursor.execute("DELETE FROM quant.trades WHERE symbol = %s", (symbol,))
        cursor.execute("DELETE FROM quant.signal_test_log WHERE symbol = %s", (symbol,))
        cursor.execute("DELETE FROM quant.strategy_performance WHERE symbol = %s", (symbol,))
        cursor.execute("DELETE FROM quant.positions WHERE symbol = %s", (symbol,))

    conn.commit()
    cursor.close()
    conn.close()


def test_fill_order_updates_signal_test_log_entry_price(ds, signal_log, cleanup):
    """测试订单成交时更新 signal_test_log 的 entry_price"""
    # 1. 创建信号记录
    signal_id = signal_log.record_signal({
        'symbol': '600000.SH',
        'name': '浦发银行',
        'strategy_name': 'ma_cross',
        'signal_date': date.today(),
        'action': 'buy',
        'confidence': 0.85,
        'signal_price': 10.0,
        'entry_price': None,  # 初始为空
        'stop_loss': 9.0,
        'reason': '测试信号'
    })

    # 2. 创建订单（关联信号）
    order_id = create_order(
        ds=ds,
        symbol='600000.SH',
        action='buy',
        order_type='limit',
        quantity=100,
        price=10.5,
        signal_id=signal_id
    )

    # 3. 成交订单
    result = fill_order(
        ds=ds,
        order_id=order_id,
        fill_price=10.3
    )

    assert result['is_full_fill'] is True

    # 4. 验证 signal_test_log 的 entry_price 被更新
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT entry_price FROM {signal_log.TABLE_NAME} WHERE id = %s",
        (signal_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    assert row is not None
    assert row[0] == 10.3  # entry_price 应该被更新为成交价


def test_sell_order_updates_signal_test_log_and_performance(ds, signal_log, perf_repo, cleanup):
    """测试卖出订单时更新 signal_test_log 和 strategy_performance"""
    # 0. 先创建持仓记录（卖出需要有持仓）
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO quant.positions (symbol, quantity, avg_cost, current_price, market_value)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (symbol) DO UPDATE SET quantity = EXCLUDED.quantity
        """,
        ('000001.SZ', 100, 20.5, 22.0, 2200.0)
    )
    conn.commit()
    cursor.close()
    conn.close()

    # 1. 创建买入信号记录（已有 entry_price）
    signal_id = signal_log.record_signal({
        'symbol': '000001.SZ',
        'name': '平安银行',
        'strategy_name': 'turtle',
        'signal_date': date.today(),
        'action': 'buy',
        'confidence': 0.90,
        'signal_price': 20.0,
        'entry_price': 20.5,  # 已成交的入场价
        'stop_loss': 18.0,
        'reason': '测试买入信号'
    })

    # 2. 创建卖出订单（关联同一个信号）
    order_id = create_order(
        ds=ds,
        symbol='000001.SZ',
        action='sell',
        order_type='limit',
        quantity=100,
        price=22.0,
        signal_id=signal_id
    )

    # 3. 成交卖出订单
    result = fill_order(
        ds=ds,
        order_id=order_id,
        fill_price=22.5
    )

    assert result['is_full_fill'] is True

    # 4. 验证 signal_test_log 的 pnl_pct 被更新
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT pnl_pct, current_price, status FROM {signal_log.TABLE_NAME} WHERE id = %s",
        (signal_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    assert row is not None
    pnl_pct = row[0]
    current_price = row[1]
    status = row[2]

    # 盈亏 = (22.5 - 20.5) / 20.5 * 100 ≈ 9.76%
    assert pnl_pct == pytest.approx(9.76, rel=0.01)
    assert current_price == 22.5
    assert status == 'verified'

    # 5. 验证 strategy_performance 表有记录
    records = perf_repo.get_by_strategy_and_symbol('turtle', '000001.SZ')
    assert len(records) == 1

    record = records[0]
    assert record['entry_price'] == 20.5
    assert record['exit_price'] == 22.5
    assert record['pnl_pct'] == pytest.approx(9.76, rel=0.01)
    assert record['source'] == 'live'


def test_fill_order_without_signal_id_does_not_update_log(ds, cleanup):
    """测试没有关联信号的订单成交不会更新 signal_test_log"""
    # 创建订单（不关联信号）
    order_id = create_order(
        ds=ds,
        symbol='000001.SH',
        action='buy',
        order_type='limit',
        quantity=100,
        price=15.0,
        signal_id=None  # 没有关联信号
    )

    # 成交订单
    result = fill_order(
        ds=ds,
        order_id=order_id,
        fill_price=15.2
    )

    assert result['is_full_fill'] is True
    # 不应该抛出异常，正常完成


def test_partial_fill_updates_entry_price_once(ds, signal_log, cleanup):
    """测试部分成交时只在第一次更新 entry_price"""
    # 1. 创建信号记录
    signal_id = signal_log.record_signal({
        'symbol': '000002.SZ',
        'name': '万科A',
        'strategy_name': 'breakout',
        'signal_date': date.today(),
        'action': 'buy',
        'confidence': 0.80,
        'signal_price': 30.0,
        'entry_price': None,
        'stop_loss': 27.0,
        'reason': '测试部分成交'
    })

    # 2. 创建订单
    order_id = create_order(
        ds=ds,
        symbol='000002.SZ',
        action='buy',
        order_type='limit',
        quantity=200,
        price=30.5,
        signal_id=signal_id
    )

    # 3. 第一次部分成交
    result1 = fill_order(
        ds=ds,
        order_id=order_id,
        fill_price=30.3,
        fill_quantity=100
    )

    assert result1['is_full_fill'] is False

    # 验证 entry_price 被更新
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT entry_price FROM {signal_log.TABLE_NAME} WHERE id = %s",
        (signal_id,)
    )
    row = cursor.fetchone()
    first_entry_price = row[0]
    cursor.close()
    conn.close()

    assert first_entry_price == 30.3

    # 4. 第二次部分成交
    result2 = fill_order(
        ds=ds,
        order_id=order_id,
        fill_price=30.6,
        fill_quantity=100
    )

    assert result2['is_full_fill'] is True

    # 验证 entry_price 不变（仍然是第一次成交价）
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT entry_price FROM {signal_log.TABLE_NAME} WHERE id = %s",
        (signal_id,)
    )
    row = cursor.fetchone()
    second_entry_price = row[0]
    cursor.close()
    conn.close()

    assert second_entry_price == 30.3  # 应该保持第一次成交价
