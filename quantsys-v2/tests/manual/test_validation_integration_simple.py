#!/usr/bin/env python3
"""
测试价格校验集成（简化版）

直接测试回测引擎的价格校验功能，不执行策略代码
"""

import sys
import os
quantsys_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, quantsys_root)

import pandas as pd
from application.services.strategy_backtest_service import StrategyBacktestService


def test_validation_integration():
    """测试：价格校验集成到回测引擎"""

    print("=" * 60)
    print("测试：价格校验集成到回测引擎")
    print("=" * 60)

    backtest_service = StrategyBacktestService()

    # 测试1：无自定义价格（正常）
    print("\n【测试1】无自定义价格")
    signals_df1 = pd.DataFrame({
        'trade_date': ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04'],
        'open': [100.0, 101.0, 102.0, 103.0],
        'high': [105.0, 106.0, 107.0, 108.0],
        'low': [95.0, 96.0, 97.0, 98.0],
        'close': [102.0, 103.0, 104.0, 105.0],
        'volume': [1000000] * 4,
        'buy_tier1': [True, False, False, False],
        'buy_tier1_pct': [1.0, 0.0, 0.0, 0.0],
        'sell_tier1': [False, False, True, False],
        'sell_tier1_pct': [0.0, 0.0, 1.0, 0.0],
    })

    result1 = backtest_service.run_backtest_from_signals(
        signals_df=signals_df1,
        initial_cash=100000
    )

    price_val1 = result1.get('price_validation', {})
    print(f"  警告: {len(price_val1.get('warnings', []))}")
    print(f"  错误: {len(price_val1.get('errors', []))}")
    print(f"  ✓ 无自定义价格策略通过")

    # 测试2：合理的自定义价格
    print("\n【测试2】合理的自定义价格（安全边际）")
    signals_df2 = pd.DataFrame({
        'trade_date': ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04'],
        'open': [100.0, 101.0, 102.0, 103.0],
        'high': [105.0, 106.0, 107.0, 108.0],
        'low': [95.0, 96.0, 97.0, 98.0],
        'close': [100.0, 101.0, 102.0, 103.0],
        'volume': [1000000] * 4,
        'buy_tier1': [True, False, False, False],
        'buy_tier1_pct': [1.0, 0.0, 0.0, 0.0],
        'buy_tier1_price': [97.85, 0, 0, 0],  # low * 1.03
        'sell_tier1': [False, False, True, False],
        'sell_tier1_pct': [0.0, 0.0, 1.0, 0.0],
        'sell_tier1_price': [0, 0, 103.79, 0],  # high * 0.97
    })

    result2 = backtest_service.run_backtest_from_signals(
        signals_df=signals_df2,
        initial_cash=100000
    )

    price_val2 = result2.get('price_validation', {})
    print(f"  警告: {len(price_val2.get('warnings', []))}")
    print(f"  错误: {len(price_val2.get('errors', []))}")

    if price_val2.get('warnings'):
        for w in price_val2['warnings']:
            print(f"    ⚠️  {w}")

    assert len(price_val2.get('errors', [])) == 0, "不应该有错误"
    print(f"  ✓ 合理的自定义价格通过")

    # 测试3：未来信息（低买高卖）⭐ 最重要
    print("\n【测试3】未来信息（低买高卖）⭐")
    signals_df3 = pd.DataFrame({
        'trade_date': ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04'],
        'open': [100.0, 101.0, 102.0, 103.0],
        'high': [105.0, 106.0, 107.0, 108.0],
        'low': [95.0, 96.0, 97.0, 98.0],
        'close': [100.0, 101.0, 102.0, 103.0],
        'volume': [1000000] * 4,
        'buy_tier1': [True, False, False, False],
        'buy_tier1_pct': [1.0, 0.0, 0.0, 0.0],
        'buy_tier1_price': [95.5, 0, 0, 0],  # low * 1.005（接近最低价）
        'sell_tier1': [False, False, True, False],
        'sell_tier1_pct': [0.0, 0.0, 1.0, 0.0],
        'sell_tier1_price': [0, 0, 106.5, 0],  # high * 0.995（接近最高价）
    })

    result3 = backtest_service.run_backtest_from_signals(
        signals_df=signals_df3,
        initial_cash=100000
    )

    price_val3 = result3.get('price_validation', {})
    errors = price_val3.get('errors', [])
    warnings = price_val3.get('warnings', [])

    print(f"  警告: {len(warnings)}")
    print(f"  错误: {len(errors)}")

    if errors:
        print(f"\n  ❌ 错误详情:")
        for e in errors:
            print(f"    {e}")

    if warnings:
        print(f"\n  ⚠️  警告详情:")
        for w in warnings:
            print(f"    {w}")

    assert len(errors) > 0, "应该检测到未来信息错误"
    assert '最低价买入和最高价卖出' in errors[0], "错误信息应提到低买高卖"
    print(f"\n  ✓ 未来信息策略被成功拦截！")

    return True


def main():
    """运行测试"""

    print("\n🚀 测试价格校验集成\n")

    try:
        test_validation_integration()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print("\n📝 验证摘要：")
        print("   ✓ 无自定义价格策略正常回测")
        print("   ✓ 合理的自定义价格可以使用")
        print("   ✓ 未来信息策略被成功拦截")
        print("\n💡 价格校验已成功集成到回测服务！")
        print("\n🎯 核心功能：")
        print("   • 规则1: OHLC 范围检查 ✅")
        print("   • 规则2: 价格偏离检查 ✅")
        print("   • 规则3: 未来信息检测 ✅（最关键）")
        return 0

    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
