"""测试策略能否使用所有因子"""

import sys
sys.path.insert(0, '.')

from application.services.strategy_code_service import StrategyCodeService

service = StrategyCodeService()

# 生成测试数据
test_klines = [
    {'open': 100+i, 'high': 102+i, 'low': 98+i, 'close': 101+i, 'volume': 1000000}
    for i in range(100)
]

print("原始K线字段:", list(test_klines[0].keys()))

# 注入因子
enhanced_klines = service._inject_technical_indicators(test_klines)

# 查看新增的因子
original_keys = set(test_klines[0].keys())
enhanced_keys = set(enhanced_klines[0].keys())
new_factors = enhanced_keys - original_keys

print(f"\n原始字段: {len(original_keys)}个")
print(f"增强后: {len(enhanced_keys)}个")
print(f"新增因子: {len(new_factors)}个")
print(f"\n新增因子列表:")
for factor in sorted(new_factors):
    print(f"  - {factor}")

# 验证向后兼容性
required_factors = ['rsi', 'macd', 'macd_signal', 'macd_hist',
                   'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
                   'ma5', 'ma10', 'ma20', 'ma60', 'atr']
print(f"\n向后兼容性检查:")
for factor in required_factors:
    exists = factor in enhanced_keys
    print(f"  {'✅' if exists else '❌'} {factor}")
