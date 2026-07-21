#!/usr/bin/env python3
"""
测试改进后的代码验证器

验证各种 df['buy'] 和 df['sell'] 的写法是否都能被正确识别
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from domain.quantlib.engine.code_validator import CodeValidator


def test_validator():
    """测试验证器对各种写法的支持"""
    validator = CodeValidator()

    test_cases = [
        # (代码片段, 描述, 应该通过)
        ("""
df['buy'] = condition
df['sell'] = condition
""", "标准单引号写法", True),

        ("""
df["buy"] = condition
df["sell"] = condition
""", "标准双引号写法", True),

        ("""
df.loc[:, 'buy'] = condition
df.loc[:, 'sell'] = condition
""", "使用 loc 写法", True),

        ("""
df.loc[df['close'] > 10, 'buy'] = True
df.loc[df['close'] < 10, 'sell'] = True
""", "带条件的 loc 写法", True),

        ("""
df.at[0, 'buy'] = True
df.at[0, 'sell'] = True
""", "使用 at 写法", True),

        ("""
df['ma_short'] = df['close'].rolling(5).mean()
df['ma_long'] = df['close'].rolling(20).mean()
df['buy'] = (df['ma_short'] > df['ma_long']) & (df['ma_short'].shift(1) <= df['ma_long'].shift(1))
df['sell'] = (df['ma_short'] < df['ma_long']) & (df['ma_short'].shift(1) >= df['ma_long'].shift(1))
""", "完整的双均线策略", True),

        ("""
# df['buy'] = condition
df['sell'] = condition
""", "buy 被注释掉（应该失败）", False),

        ("""
df['buy'] = condition
# df['sell'] = condition
""", "sell 被注释掉（应该失败）", False),

        ("""
df['Buy'] = condition
df['Sell'] = condition
""", "大小写错误（应该失败）", False),

        ("""
df['buy'] = condition
""", "只有 buy 没有 sell（应该失败）", False),

        ("""
df['sell'] = condition
""", "只有 sell 没有 buy（应该失败）", False),
    ]

    print("=" * 70)
    print("测试改进后的代码验证器")
    print("=" * 70)

    passed = 0
    failed = 0

    for i, (code, desc, should_pass) in enumerate(test_cases, 1):
        try:
            validator.validate(code, 'indicator')
            result = "通过"
            success = should_pass
        except ValueError as e:
            result = f"失败: {str(e)}"
            success = not should_pass

        status = "✓" if success else "✗"

        print(f"\n测试 {i}: {desc}")
        print(f"  预期: {'通过' if should_pass else '失败'}")
        print(f"  实际: {result}")
        print(f"  结果: {status}")

        if success:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 70)

    return failed == 0


if __name__ == '__main__':
    success = test_validator()
    sys.exit(0 if success else 1)
