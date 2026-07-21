#!/usr/bin/env python3
"""
简化单元测试：直接测试回测引擎的价格处理逻辑
"""

import sys
import os
quantsys_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, quantsys_root)

import pandas as pd
from application.services.strategy_backtest_service import StrategyBacktestService


def test_price_reading_logic():
    """测试：回测引擎读取自定义价格的逻辑"""

    print("=" * 60)
    print("测试：回测引擎价格读取逻辑")
    print("=" * 60)

    # 创建模拟的信号DataFrame
    signals_df = pd.DataFrame({
        'trade_date': ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04', '2025-01-05'],
        'open': [100.0, 101.0, 102.0, 103.0, 104.0],
        'high': [105.0, 106.0, 107.0, 108.0, 109.0],
        'low': [95.0, 96.0, 97.0, 98.0, 99.0],
        'close': [102.0, 103.0, 104.0, 105.0, 106.0],
        'volume': [1000000] * 5,

        # 买入信号 - Tier1 使用最低价
        'buy_tier1': [True, False, False, False, False],
        'buy_tier1_pct': [1.0, 0.0, 0.0, 0.0, 0.0],
        'buy_tier1_price': [96.0, 0, 0, 0, 0],  # low * 1.01 = 95 * 1.01 ≈ 96

        # 卖出信号 - Tier1 使用最高价
        'sell_tier1': [False, False, False, True, False],
        'sell_tier1_pct': [0.0, 0.0, 0.0, 1.0, 0.0],
        'sell_tier1_price': [0, 0, 0, 107.0, 0],  # high * 0.99 = 108 * 0.99 ≈ 107
    })

    # 运行回测
    backtest_service = StrategyBacktestService()
    result = backtest_service.run_backtest_from_signals(
        signals_df=signals_df,
        initial_cash=100000
    )

    print(f"\n✅ 回测完成")
    print(f"   初始资金: 100,000")
    print(f"   最终权益: {result['equity_curve'][-1]['equity']:.2f}")
    print(f"   总收益率: {result['total_return']:.2%}")
    print(f"   交易次数: {result.get('total_trades', len(result.get('trades', [])))}")

    # 检查交易记录
    trades = result.get('trades', [])
    if len(trades) > 0:
        trade = trades[0]
        print(f"\n📋 交易明细：")
        print(f"   买入日期: {trade['entry_date']}")
        print(f"   买入价格: {trade['entry_price']:.2f}")
        print(f"   卖出日期: {trade['exit_date']}")
        print(f"   卖出价格: {trade['exit_price']:.2f}")
        print(f"   盈亏: {trade['pnl']:.2f}")
        print(f"   盈亏率: {trade['pnl_pct']:.2%}")

        # 验证价格
        assert abs(trade['entry_price'] - 96.0) < 0.1, f"买入价应为96.0，实际为{trade['entry_price']}"
        assert abs(trade['exit_price'] - 107.0) < 0.1, f"卖出价应为107.0，实际为{trade['exit_price']}"

        print(f"\n✅ 价格验证通过：")
        print(f"   ✓ 买入价 = {trade['entry_price']:.2f} (预期 96.0)")
        print(f"   ✓ 卖出价 = {trade['exit_price']:.2f} (预期 107.0)")

        return True
    else:
        print("\n❌ 没有生成交易记录")
        return False


def test_default_price():
    """测试：未指定价格时使用收盘价"""

    print("\n" + "=" * 60)
    print("测试：默认使用收盘价")
    print("=" * 60)

    # 不指定 _price 列
    signals_df = pd.DataFrame({
        'trade_date': ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04'],
        'open': [100.0, 101.0, 102.0, 103.0],
        'high': [105.0, 106.0, 107.0, 108.0],
        'low': [95.0, 96.0, 97.0, 98.0],
        'close': [102.0, 103.0, 104.0, 105.0],
        'volume': [1000000] * 4,

        'buy_tier1': [True, False, False, False],
        'buy_tier1_pct': [1.0, 0.0, 0.0, 0.0],
        # 不指定 buy_tier1_price

        'sell_tier1': [False, False, True, False],
        'sell_tier1_pct': [0.0, 0.0, 1.0, 0.0],
        # 不指定 sell_tier1_price
    })

    backtest_service = StrategyBacktestService()
    result = backtest_service.run_backtest_from_signals(
        signals_df=signals_df,
        initial_cash=100000
    )

    print(f"\n✅ 回测完成")
    print(f"   交易次数: {result.get('total_trades', len(result.get('trades', [])))}")

    trades = result.get('trades', [])
    if len(trades) > 0:
        trade = trades[0]
        print(f"\n📋 交易明细：")
        print(f"   买入价格: {trade['entry_price']:.2f} (应为收盘价 102.0)")
        print(f"   卖出价格: {trade['exit_price']:.2f} (应为收盘价 104.0)")

        # 验证使用收盘价
        assert abs(trade['entry_price'] - 102.0) < 0.1, f"买入价应为102.0，实际为{trade['entry_price']}"
        assert abs(trade['exit_price'] - 104.0) < 0.1, f"卖出价应为104.0，实际为{trade['exit_price']}"

        print(f"\n✅ 默认价格验证通过：")
        print(f"   ✓ 买入价 = {trade['entry_price']:.2f} (使用收盘价)")
        print(f"   ✓ 卖出价 = {trade['exit_price']:.2f} (使用收盘价)")

        return True
    else:
        print("\n❌ 没有生成交易记录")
        return False


def test_price_validator():
    """测试：价格校验器"""

    print("\n" + "=" * 60)
    print("测试：价格校验器")
    print("=" * 60)

    from application.services.strategy_code_validator import StrategyCodeValidator

    # 测试1: 基础范围检查
    print("\n【测试1】价格超出 OHLC 范围")
    test_df1 = pd.DataFrame({
        'open': [10.0, 11.0, 12.0],
        'high': [10.5, 11.5, 12.5],
        'low': [9.5, 10.5, 11.5],
        'close': [10.2, 11.2, 12.2],
        'buy_tier1_price': [10.6, 11.6, 12.6],  # 高于 high
        'sell_tier1_price': [9.0, 10.0, 11.0],  # 低于 low
    })

    validator = StrategyCodeValidator()
    result1 = validator.validate_custom_prices(test_df1)

    print(f"  检测到 {len(result1['warnings'])} 个警告，{len(result1['errors'])} 个错误")
    for warning in result1['warnings']:
        print(f"  ⚠️  {warning}")
    for error in result1['errors']:
        print(f"  ❌ {error}")

    assert len(result1['warnings']) >= 2, "应该检测到至少2个警告"
    assert any('buy_tier1_price > high' in w for w in result1['warnings'])
    assert any('sell_tier1_price < low' in w for w in result1['warnings'])

    # 测试2: 价格偏离检查
    print("\n【测试2】价格偏离收盘价过大")
    test_df2 = pd.DataFrame({
        'open': [100.0, 101.0, 102.0],
        'high': [105.0, 106.0, 107.0],
        'low': [95.0, 96.0, 97.0],
        'close': [100.0, 101.0, 102.0],
        'buy_tier1_price': [96.0, 97.0, 98.0],  # 偏离 4%
        'sell_tier1_price': [104.0, 105.0, 106.0],  # 偏离 4%
    })

    result2 = validator.validate_custom_prices(test_df2)

    print(f"  检测到 {len(result2['warnings'])} 个警告，{len(result2['errors'])} 个错误")
    for warning in result2['warnings']:
        print(f"  ⚠️  {warning}")

    assert len(result2['warnings']) >= 2, "应该检测到价格偏离警告"

    # 测试3: 未来信息检测（最重要）
    print("\n【测试3】未来信息检测（低买高卖）")
    test_df3 = pd.DataFrame({
        'open': [100.0, 101.0, 102.0],
        'high': [105.0, 106.0, 107.0],
        'low': [95.0, 96.0, 97.0],
        'close': [100.0, 101.0, 102.0],
        'buy_tier1_price': [95.5, 96.5, 97.5],   # low * 1.005 (接近最低价)
        'sell_tier1_price': [104.5, 105.5, 106.5],  # high * 0.995 (接近最高价)
    })

    result3 = validator.validate_custom_prices(test_df3)

    print(f"  检测到 {len(result3['warnings'])} 个警告，{len(result3['errors'])} 个错误")
    for warning in result3['warnings']:
        print(f"  ⚠️  {warning}")
    for error in result3['errors']:
        print(f"  ❌ {error}")

    assert len(result3['errors']) > 0, "应该检测到未来信息错误"
    assert any('最低价买入和最高价卖出' in e for e in result3['errors']), "应该检测到低买高卖错误"

    print(f"\n✅ 校验功能正常")
    return True


def main():
    """运行所有测试"""

    print("\n🚀 开始测试自定义成交价格功能\n")

    try:
        # 测试1：自定义价格
        success1 = test_price_reading_logic()

        # 测试2：默认价格
        success2 = test_default_price()

        # 测试3：价格校验
        success3 = test_price_validator()

        if success1 and success2 and success3:
            print("\n" + "=" * 60)
            print("✅ 所有测试通过！")
            print("=" * 60)
            print("\n📝 功能验证摘要：")
            print("   ✓ 自定义买入价格正常工作")
            print("   ✓ 自定义卖出价格正常工作")
            print("   ✓ 未指定价格时使用收盘价")
            print("   ✓ 价格校验功能正常工作")
            print("\n💡 自定义成交价格功能实现完成！")
            return 0
        else:
            print("\n❌ 部分测试失败")
            return 1

    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
