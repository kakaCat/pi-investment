#!/usr/bin/env python3
"""
P2 端到端验证脚本
测试完整的"信号 → 盈亏追踪 → 统计 → 经验"闭环
"""
import sys
import json
from datetime import date, timedelta
from application.services.signal_test_log import SignalTestLog
from application.services.new_order_service import _update_signal_tracking
from application.services.experience_accumulator import ExperienceAccumulator
from adapters.outbound.repositories import StrategyPerformanceRepository

def cleanup_test_data():
    """清理测试数据"""
    signal_log = SignalTestLog()
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quant.signal_test_log WHERE reason = 'P2 E2E 测试'")
    cursor.execute("DELETE FROM quant.strategy_performance WHERE symbol = '600000.SH'")
    conn.commit()
    cursor.close()
    conn.close()

def test_full_loop():
    """测试完整闭环"""
    print("=" * 70)
    print("P2 端到端验证 — 策略循环闭合")
    print("=" * 70)

    signal_log = SignalTestLog()
    perf_repo = StrategyPerformanceORMRepository()

    # 清理旧数据
    print("\n[准备] 清理旧测试数据...")
    cleanup_test_data()
    print("✅ 清理完成")

    # 1. 创建信号
    print("\n[步骤 1/5] 创建测试信号...")
    signal_id = signal_log.record_signal({
        'symbol': '600000.SH',
        'name': '浦发银行',
        'strategy_name': 'ma_cross',
        'signal_date': date.today(),
        'action': 'BUY',
        'confidence': 0.88,
        'signal_price': 10.0,
        'entry_price': None,
        'stop_loss': 9.0,
        'reason': 'P2 E2E 测试'
    })
    print(f"✅ 信号创建成功: signal_id={signal_id}")

    # 2. 模拟买入成交
    print("\n[步骤 2/5] 模拟买入成交...")
    _update_signal_tracking(
        signal_id=signal_id,
        action='buy',
        fill_price=10.2,
        symbol='600000.SH'
    )

    # 验证 entry_price 更新
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(f"SELECT entry_price FROM {signal_log.TABLE_NAME} WHERE id = %s", (signal_id,))
    entry_price = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    assert entry_price == 10.2, f"❌ entry_price 应该是 10.2，实际是 {entry_price}"
    print(f"✅ entry_price 更新成功: {entry_price}")

    # 3. 模拟卖出成交
    print("\n[步骤 3/5] 模拟卖出成交...")
    _update_signal_tracking(
        signal_id=signal_id,
        action='sell',
        fill_price=11.0,
        symbol='600000.SH'
    )

    # 验证 entry_price 更新
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(f"SELECT entry_price FROM {signal_log.TABLE_NAME} WHERE id = %s", (signal_id,))
    entry_price = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    assert entry_price == 10.2, f"❌ entry_price 应该是 10.2，实际是 {entry_price}"
    print(f"✅ entry_price 更新成功: {entry_price}")

    # 验证盈亏计算
    conn = signal_log._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT pnl_pct, status FROM {signal_log.TABLE_NAME} WHERE id = %s",
        (signal_id,)
    )
    pnl_pct, status = cursor.fetchone()
    cursor.close()
    conn.close()

    expected_pnl = (11.0 - 10.2) / 10.2 * 100
    assert abs(float(pnl_pct) - expected_pnl) < 0.01, f"❌ pnl_pct 应该是 {expected_pnl:.2f}，实际是 {pnl_pct}"
    assert status == 'verified', f"❌ status 应该是 'verified'，实际是 {status}"
    print(f"✅ 盈亏计算成功: pnl_pct={float(pnl_pct):.2f}%, status={status}")

    # 4. 验证 strategy_performance 记录
    print("\n[步骤 4/5] 验证 strategy_performance 记录...")
    records = perf_repo.get_by_strategy_and_symbol('ma_cross', '600000.SH')
    assert len(records) >= 1, "❌ strategy_performance 应该有至少 1 条记录"

    latest = records[-1]
    assert float(latest['entry_price']) == 10.2, f"❌ entry_price 不匹配"
    assert float(latest['exit_price']) == 11.0, f"❌ exit_price 不匹配"
    assert abs(float(latest['pnl_pct']) - expected_pnl) < 0.01, f"❌ pnl_pct 不匹配"
    assert latest['source'] == 'live', f"❌ source 应该是 'live'"
    print(f"✅ strategy_performance 记录正确")
    print(f"   - entry_price: {float(latest['entry_price'])}")
    print(f"   - exit_price: {float(latest['exit_price'])}")
    print(f"   - pnl_pct: {float(latest['pnl_pct']):.2f}%")
    print(f"   - source: {latest['source']}")

    # 5. 查询统计
    print("\n[步骤 5/5] 查询统计...")
    stats = perf_repo.get_statistics('ma_cross', '600000.SH', 'live')
    print(f"✅ 统计查询成功:")
    print(f"   - 总交易数: {stats['total_trades']}")
    print(f"   - 盈利交易: {stats['win_trades']}")
    print(f"   - 亏损交易: {stats['loss_trades']}")
    print(f"   - 胜率: {stats['win_rate']:.2f}%")
    print(f"   - 平均盈亏: {stats['avg_pnl_pct']:.2f}%")

    print("\n" + "=" * 70)
    print("✅ 所有验证通过！策略循环闭合功能正常")
    print("=" * 70)
    print("\n核心功能验证:")
    print("  ✅ 信号追踪 - signal_id 贯穿全流程")
    print("  ✅ 盈亏计算 - 买入/卖出自动更新")
    print("  ✅ 数据持久化 - strategy_performance 表记录完整")
    print("  ✅ 统计查询 - 实盘数据可查询")

    # 清理测试数据
    print("\n[清理] 删除测试数据...")
    cleanup_test_data()
    print("✅ 清理完成")

    return True

if __name__ == '__main__':
    try:
        test_full_loop()
        print("\n🎉 P2 端到端验证成功！")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ 验证失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
