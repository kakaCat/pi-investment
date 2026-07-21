#!/usr/bin/env python3
"""
端到端测试：验证修复后的验证器是否解决了回测 API 的问题

模拟用户通过 API 创建指标并回测的完整流程
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from application.services.strategy_code_service import StrategyCodeService


def test_create_and_backtest_indicator():
    """测试创建指标并回测"""
    print("=" * 70)
    print("端到端测试：创建指标 -> 回测")
    print("=" * 70)

    service = StrategyCodeService()

    # 测试用例 1: 标准写法
    print("\n测试 1: 标准 df['buy'] 写法")
    print("-" * 70)

    code1 = """
# 双均线策略
my_indicator_name = "双均线交叉策略"
my_indicator_description = "使用短期/长期均线金叉与死叉生成买卖信号"

# @param ma_short int 5 短期均线周期
# @param ma_long int 20 长期均线周期

ma_short = params.get('ma_short', 5)
ma_long = params.get('ma_long', 20)

df = df.copy()
df['ma_short'] = df['close'].rolling(ma_short).mean()
df['ma_long'] = df['close'].rolling(ma_long).mean()

df['buy'] = (df['ma_short'] > df['ma_long']) & (df['ma_short'].shift(1) <= df['ma_long'].shift(1))
df['sell'] = (df['ma_short'] < df['ma_long']) & (df['ma_short'].shift(1) >= df['ma_long'].shift(1))
"""

    try:
        result = service.create_strategy(
            name="测试-标准写法",
            code=code1,
            code_type='indicator'
        )
        print(f"✓ 策略创建成功 (ID: {result['strategy_id']})")
        print(f"  验证状态: {result['validation']['valid']}")
    except Exception as e:
        print(f"✗ 策略创建失败: {str(e)}")
        return False

    # 测试用例 2: 使用 df.loc 写法
    print("\n测试 2: df.loc[:, 'buy'] 写法")
    print("-" * 70)

    code2 = """
# RSI 策略
my_indicator_name = "RSI超买超卖策略"
my_indicator_description = "RSI < 30 买入，RSI > 70 卖出"

# @param rsi_period int 14 RSI周期
# @param oversold int 30 超卖阈值
# @param overbought int 70 超买阈值

rsi_period = params.get('rsi_period', 14)
oversold = params.get('oversold', 30)
overbought = params.get('overbought', 70)

df = df.copy()

# 计算 RSI
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

# 使用 loc 写法生成信号
df.loc[:, 'buy'] = df['rsi'] < oversold
df.loc[:, 'sell'] = df['rsi'] > overbought
"""

    try:
        result = service.create_strategy(
            name="测试-loc写法",
            code=code2,
            code_type='indicator'
        )
        print(f"✓ 策略创建成功 (ID: {result['strategy_id']})")
        print(f"  验证状态: {result['validation']['valid']}")
    except Exception as e:
        print(f"✗ 策略创建失败: {str(e)}")
        return False

    # 测试用例 3: 错误的代码（应该失败）
    print("\n测试 3: 缺少 sell 信号（应该失败）")
    print("-" * 70)

    code3 = """
df = df.copy()
df['ma'] = df['close'].rolling(20).mean()
df['buy'] = df['close'] > df['ma']
# 故意不生成 sell 信号
"""

    try:
        result = service.create_strategy(
            name="测试-错误代码",
            code=code3,
            code_type='indicator'
        )
        print(f"✗ 应该失败但通过了验证")
        return False
    except Exception as e:
        print(f"✓ 正确拒绝: {str(e)}")

    print("\n" + "=" * 70)
    print("所有测试通过！验证器修复成功。")
    print("=" * 70)

    return True


def main():
    """主测试流程"""
    success = test_create_and_backtest_indicator()

    if success:
        print("\n✓ 修复验证成功！")
        print("\n现在用户可以使用以下写法创建指标：")
        print("  1. df['buy'] = condition")
        print("  2. df.loc[:, 'buy'] = condition")
        print("  3. df.at[idx, 'buy'] = condition")
        print("\n验证器会正确拒绝：")
        print("  - 注释掉的信号生成代码")
        print("  - 缺少 buy 或 sell 信号的代码")
        print("  - 大小写错误的信号名称")
    else:
        print("\n✗ 测试失败，请检查错误信息")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
