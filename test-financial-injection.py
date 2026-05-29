#!/usr/bin/env python3
"""
验证财务指标注入是否正常工作

测试场景：
1. 检查 _inject_financial 方法是否存在
2. 验证注入后的 klines 是否包含财务指标列
3. 验证策略代码是否能访问这些列
"""

import sys
import os

# 添加 quantsys-v2 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'quantsys-v2'))

from services.strategy_code_service import StrategyCodeService
from quantlib.engine.indicator_strategy_executor import IndicatorStrategyExecutor
import pandas as pd

def test_financial_injection():
    """测试财务指标注入"""

    print("=" * 80)
    print("测试 1: 检查 _inject_financial 方法是否存在")
    print("=" * 80)

    service = StrategyCodeService()

    # 检查方法是否存在
    if hasattr(service, '_inject_financial'):
        print("✓ _inject_financial 方法存在")
    else:
        print("✗ _inject_financial 方法不存在")
        return False

    print("\n" + "=" * 80)
    print("测试 2: 验证注入后的 klines 包含财务指标列")
    print("=" * 80)

    # 创建测试 K 线数据
    test_klines = [
        {
            'trade_date': '2026-04-20',
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 103.0,
            'volume': 1000000
        },
        {
            'trade_date': '2026-04-25',
            'open': 103.0,
            'high': 108.0,
            'low': 102.0,
            'close': 106.0,
            'volume': 1200000
        },
        {
            'trade_date': '2026-05-15',
            'open': 106.0,
            'high': 110.0,
            'low': 105.0,
            'close': 108.0,
            'volume': 1100000
        }
    ]

    print(f"原始 klines 列: {list(test_klines[0].keys())}")

    # 注入财务指标（使用一个真实的股票代码）
    try:
        injected_klines = service._inject_financial(test_klines, '600519')

        print(f"\n注入后 klines 列: {list(injected_klines[0].keys())}")

        # 检查财务指标列是否存在
        expected_columns = [
            'roe_q', 'gross_margin_q', 'net_profit_margin_q', 'debt_ratio_q',
            'revenue_growth_q', 'ocf_to_profit_q', 'current_ratio_q', 'roa_q', 'operating_margin_q',
            'roe_y', 'gross_margin_y', 'net_profit_margin_y', 'debt_ratio_y',
            'revenue_growth_y', 'ocf_to_profit_y', 'current_ratio_y', 'roa_y', 'operating_margin_y'
        ]

        missing_columns = []
        for col in expected_columns:
            if col not in injected_klines[0]:
                missing_columns.append(col)

        if missing_columns:
            print(f"\n✗ 缺少财务指标列: {missing_columns}")
            return False
        else:
            print(f"\n✓ 所有 18 个财务指标列都已注入")

            # 显示示例值
            print("\n示例值（第一行）:")
            for col in expected_columns[:5]:  # 只显示前5个
                value = injected_klines[0][col]
                print(f"  {col}: {value}")

    except Exception as e:
        print(f"\n✗ 注入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("测试 3: 验证策略代码能访问财务指标列")
    print("=" * 80)

    # 创建一个使用财务指标的策略代码（不使用 import）
    strategy_code = """
# 测试策略：使用财务指标

# 检查财务指标列是否存在
print("DataFrame 列:", list(df.columns))

# 尝试访问财务指标
if 'roe_y' in df.columns:
    print("✓ 可以访问 roe_y 列")
    print(f"  roe_y 前3个值: {df['roe_y'].head(3).tolist()}")
else:
    print("✗ 无法访问 roe_y 列")

if 'gross_margin_q' in df.columns:
    print("✓ 可以访问 gross_margin_q 列")
    print(f"  gross_margin_q 前3个值: {df['gross_margin_q'].head(3).tolist()}")
else:
    print("✗ 无法访问 gross_margin_q 列")

# 创建一个使用财务指标的策略
# 使用 fillna 处理 NaN 值
df['quality_stock'] = (
    (df['roe_y'].fillna(0) >= 10) &
    (df['debt_ratio_y'].fillna(100) < 70) &
    (df['gross_margin_q'].fillna(0) > 20)
)

# 简单的买卖信号
df['buy'] = df['quality_stock'] & (df['close'] < df['close'].shift(1))
df['sell'] = ~df['quality_stock'] | (df['close'] > df['close'].shift(1))

print(f"\\n生成的信号:")
print(f"  buy 信号数: {df['buy'].sum()}")
print(f"  sell 信号数: {df['sell'].sum()}")
"""

    try:
        executor = IndicatorStrategyExecutor()
        result = executor.execute(
            code=strategy_code,
            klines=injected_klines,
            params={}
        )

        print("\n✓ 策略代码执行成功")
        print(f"  结果 DataFrame 形状: {result.signals.shape}")
        print(f"  结果 DataFrame 列数: {len(result.signals.columns)}")

        return True

    except Exception as e:
        print(f"\n✗ 策略代码执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("\n财务指标注入验证测试\n")

    success = test_financial_injection()

    print("\n" + "=" * 80)
    if success:
        print("✓ 所有测试通过！财务指标注入功能正常工作。")
        print("\n结论：")
        print("  1. _inject_financial 方法存在（不是 inject_factor）")
        print("  2. 财务指标已正确注入到 klines 中")
        print("  3. 策略代码可以访问这些财务指标列")
        print("\n用户提到的问题可能是：")
        print("  - 搜索了错误的函数名（inject_factor 而不是 _inject_financial）")
        print("  - 或者在某些特定场景下财务数据获取失败（返回 NaN）")
    else:
        print("✗ 测试失败！存在问题。")
    print("=" * 80)
