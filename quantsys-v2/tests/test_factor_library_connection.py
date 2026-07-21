"""测试因子库能否被正常调用"""

from domain.quantlib.factors.momentum import MomentumFactors
from domain.quantlib.factors.trend import TrendFactors
import pandas as pd

# 准备测试数据
test_klines = [
    {'open': 100 + i, 'high': 102 + i, 'low': 98 + i, 'close': 101 + i, 'volume': 1000000}
    for i in range(100)
]

# 测试动量因子
momentum = MomentumFactors()
print("动量因子支持的方法:", momentum.get_supported_methods())

try:
    # 测试RSI14
    result = momentum.calculate('rsi14', test_klines)
    print(f"✅ RSI14计算成功: {type(result)}")
    if isinstance(result, dict) and 'value' in result:
        print(f"   返回字典格式，value长度: {len(result['value'])}")
    else:
        print(f"   返回列表/数组，长度: {len(result)}")
except Exception as e:
    print(f"❌ RSI14计算失败: {e}")

# 测试趋势因子
trend = TrendFactors()
print("\n趋势因子支持的方法:", trend.get_supported_methods())

print("\n✅ 因子库接口测试完成")
