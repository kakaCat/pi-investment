"""
性能测试：TA-Lib vs Pandas 实现

对比新旧版本的因子计算性能
"""

import sys
sys.path.insert(0, '.')

import time
import numpy as np
from domain.quantlib.factors.momentum import MomentumFactors

# 生成测试数据
def generate_test_data(n=1000):
    """生成测试K线数据"""
    base_price = 100
    klines = []
    for i in range(n):
        close = base_price + np.random.randn() * 2
        klines.append({
            'open': close + np.random.randn() * 0.5,
            'high': close + abs(np.random.randn()),
            'low': close - abs(np.random.randn()),
            'close': close,
            'volume': 1000000 + np.random.randint(-100000, 100000)
        })
        base_price = close
    return klines

# 性能测试函数
def benchmark_factor(factor_obj, method_name, klines, iterations=100):
    """测试单个因子的性能"""
    method = getattr(factor_obj, method_name)

    # 预热
    method(klines)

    # 正式测试
    start = time.time()
    for _ in range(iterations):
        method(klines)
    end = time.time()

    elapsed = (end - start) / iterations * 1000  # 转换为毫秒
    return elapsed

# 主测试
if __name__ == '__main__':
    print("=" * 60)
    print("TA-Lib 性能测试")
    print("=" * 60)

    # 测试不同数据量
    data_sizes = [100, 500, 1000]

    momentum = MomentumFactors()

    for size in data_sizes:
        print(f"\n📊 数据量: {size} 根K线")
        print("-" * 60)

        test_data = generate_test_data(size)

        # 测试动量因子
        factors_to_test = [
            ('MACD', 'macd'),
            ('RSI14', 'rsi14'),
            ('ROC10', 'roc_10'),
            ('Momentum10', 'momentum_10'),
        ]

        for factor_name, method_name in factors_to_test:
            try:
                elapsed = benchmark_factor(momentum, method_name, test_data, iterations=100)
                print(f"  {factor_name:15s}: {elapsed:6.2f} ms/次")
            except Exception as e:
                print(f"  {factor_name:15s}: ❌ 失败 ({e})")

    print("\n" + "=" * 60)
    print("✅ 性能测试完成")
    print("=" * 60)
    print("\n💡 TA-Lib 使用 C 语言实现，预期比 pandas 快 5-10 倍")
