#!/usr/bin/env python3
"""
测试价格校验集成到回测服务

验证回测服务是否能正确检测和拒绝使用未来信息的策略
"""

import sys
import os
quantsys_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

import pandas as pd
from datetime import datetime, timedelta
from application.services.strategy_backtest_service import StrategyBacktestService


def create_test_klines(days=100):
    """创建测试K线数据"""
    dates = [(datetime(2025, 1, 1) + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]

    klines = []
    base_price = 100.0

    for i, date in enumerate(dates):
        price = base_price + (i % 20 - 10) * 2

        kline = {
            'trade_date': date,
            'open': price - 1,
            'high': price + 2,
            'low': price - 2,
            'close': price,
            'volume': 1000000 + i * 10000,
            'amount': price * (1000000 + i * 10000),
            'rsi14': 50 + (i % 40 - 20),
            'ma5': price,
            'ma20': price,
            'macd': 0.5 if i % 10 < 5 else -0.5,
            'macd_signal': 0.3 if i % 10 < 5 else -0.3,
        }
        klines.append(kline)

    return klines


def test_valid_strategy():
    """测试：正常策略（无自定义价格）"""

    print("=" * 60)
    print("测试1：正常策略（无自定义价格）")
    print("=" * 60)

    strategy_code = """
my_indicator_name = "正常RSI策略"

def calc_indicator(ctx):
    df = ctx.df

    df['buy'] = df['rsi14'] < 30
    df['sell'] = df['rsi14'] > 70

    return df
"""

    strategy = {
        'code_content': strategy_code,
        'code_type': 'indicator',
        'parsed_params': {}
    }

    klines = create_test_klines(60)
    backtest_service = StrategyBacktestService()

    result = backtest_service.backtest_indicator_strategy(
        strategy=strategy,
        klines=klines,
        initial_cash=1000000
    )

    print(f"\n✅ 回测完成")
    print(f"   总收益率: {result.get('total_return', 0):.2%}")
    print(f"   交易次数: {result.get('total_trades', 0)}")

    # 检查价格校验结果
    price_val = result.get('price_validation', {})
    print(f"   价格校验 - 警告: {len(price_val.get('warnings', []))}")
    print(f"   价格校验 - 错误: {len(price_val.get('errors', []))}")

    assert len(price_val.get('errors', [])) == 0, "不应该有错误"
    print("\n✓ 正常策略通过校验")

    return True


def test_reasonable_custom_price():
    """测试：合理的自定义价格"""

    print("\n" + "=" * 60)
    print("测试2：合理的自定义价格（安全边际）")
    print("=" * 60)

    strategy_code = """
my_indicator_name = "合理的自定义价格策略"

def calc_indicator(ctx):
    df = ctx.df

    # 使用安全边际：low * 1.03 / high * 0.97
    df['buy_tier1'] = df['rsi14'] < 30
    df['buy_tier1_pct'] = 1.0
    df['buy_tier1_price'] = df['low'] * 1.03

    df['sell_tier1'] = df['rsi14'] > 70
    df['sell_tier1_pct'] = 1.0
    df['sell_tier1_price'] = df['high'] * 0.97

    return df
"""

    strategy = {
        'code_content': strategy_code,
        'code_type': 'indicator',
        'parsed_params': {}
    }

    klines = create_test_klines(60)
    backtest_service = StrategyBacktestService()

    result = backtest_service.backtest_indicator_strategy(
        strategy=strategy,
        klines=klines,
        initial_cash=1000000
    )

    print(f"\n✅ 回测完成")
    print(f"   总收益率: {result.get('total_return', 0):.2%}")

    # 检查价格校验结果
    price_val = result.get('price_validation', {})
    print(f"   价格校验 - 警告: {len(price_val.get('warnings', []))}")
    print(f"   价格校验 - 错误: {len(price_val.get('errors', []))}")

    if price_val.get('warnings'):
        print("\n   警告详情:")
        for w in price_val['warnings']:
            print(f"     ⚠️  {w}")

    assert len(price_val.get('errors', [])) == 0, "不应该有错误"
    print("\n✓ 合理的自定义价格通过校验")

    return True


def test_future_info_strategy():
    """测试：使用未来信息的策略（应被拒绝）"""

    print("\n" + "=" * 60)
    print("测试3：未来信息策略（低买高卖）⭐")
    print("=" * 60)

    strategy_code = """
my_indicator_name = "低买高卖作弊策略"

def calc_indicator(ctx):
    df = ctx.df

    # 作弊：精准买在最低价，卖在最高价
    df['buy_tier1'] = df['rsi14'] < 40
    df['buy_tier1_pct'] = 1.0
    df['buy_tier1_price'] = df['low'] * 1.005  # 接近最低价

    df['sell_tier1'] = df['rsi14'] > 60
    df['sell_tier1_pct'] = 1.0
    df['sell_tier1_price'] = df['high'] * 0.995  # 接近最高价

    return df
"""

    strategy = {
        'code_content': strategy_code,
        'code_type': 'indicator',
        'parsed_params': {}
    }

    klines = create_test_klines(60)
    backtest_service = StrategyBacktestService()

    result = backtest_service.backtest_indicator_strategy(
        strategy=strategy,
        klines=klines,
        initial_cash=1000000
    )

    print(f"\n📋 回测结果:")
    print(f"   成功: {result.get('success', True)}")
    print(f"   总收益率: {result.get('total_return', 0):.2%}")

    # 检查价格校验结果
    price_val = result.get('price_validation', {})
    errors = price_val.get('errors', [])
    warnings = price_val.get('warnings', [])

    print(f"   价格校验 - 警告: {len(warnings)}")
    print(f"   价格校验 - 错误: {len(errors)}")

    if errors:
        print("\n   ❌ 错误详情:")
        for e in errors:
            print(f"     {e}")

    if warnings:
        print("\n   ⚠️  警告详情:")
        for w in warnings:
            print(f"     {w}")

    # 验证应该有错误且回测失败
    assert len(errors) > 0, "应该检测到未来信息错误"
    assert '最低价买入和最高价卖出' in errors[0], "错误信息应提到低买高卖"
    assert result.get('success') == False or result.get('error'), "回测应该失败"

    print("\n✓ 未来信息策略被成功拦截！")

    return True


def main():
    """运行所有测试"""

    print("\n🚀 测试价格校验集成到回测服务\n")

    try:
        success1 = test_valid_strategy()
        success2 = test_reasonable_custom_price()
        success3 = test_future_info_strategy()

        if success1 and success2 and success3:
            print("\n" + "=" * 60)
            print("✅ 所有测试通过！")
            print("=" * 60)
            print("\n📝 验证摘要：")
            print("   ✓ 正常策略可以正常回测")
            print("   ✓ 合理的自定义价格可以使用")
            print("   ✓ 未来信息策略被成功拦截")
            print("\n💡 价格校验已成功集成到回测服务！")
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
