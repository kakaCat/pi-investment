#!/usr/bin/env python3
"""
创建系统内置指标

在数据库中插入常用的技术指标作为系统内置指标
"""

import sys
import os

from application.services.strategy_code_service import StrategyCodeService


def create_builtin_indicators():
    """创建系统内置指标"""
    service = StrategyCodeService()

    builtin_indicators = [
        {
            'name': 'RSI超买超卖策略',
            'code': '''# RSI超买超卖策略
my_indicator_name = "RSI超买超卖策略"
my_indicator_description = "RSI < 30 买入，RSI > 70 卖出"

# @param rsi_period int 14 RSI周期
# @param oversold int 30 超卖阈值
# @param overbought int 70 超买阈值
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

rsi_period = params.get('rsi_period', 14)
oversold = params.get('oversold', 30)
overbought = params.get('overbought', 70)

# 计算 RSI
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

# 生成信号
df['buy'] = df['rsi'] < oversold
df['sell'] = df['rsi'] > overbought
''',
            'description': 'RSI指标超买超卖策略，适合震荡市场',
            'category': 'momentum'
        },
        {
            'name': '双均线交叉策略',
            'code': '''# 双均线交叉策略
my_indicator_name = "双均线交叉策略"
my_indicator_description = "短期均线上穿长期均线买入，下穿卖出"

# @param ma_short int 5 短期均线周期
# @param ma_long int 20 长期均线周期
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

ma_short = params.get('ma_short', 5)
ma_long = params.get('ma_long', 20)

# 计算均线
df['ma_short'] = df['close'].rolling(window=ma_short).mean()
df['ma_long'] = df['close'].rolling(window=ma_long).mean()

# 金叉买入，死叉卖出
df['buy'] = (df['ma_short'] > df['ma_long']) & (df['ma_short'].shift(1) <= df['ma_long'].shift(1))
df['sell'] = (df['ma_short'] < df['ma_long']) & (df['ma_short'].shift(1) >= df['ma_long'].shift(1))
''',
            'description': '经典双均线策略，适合趋势市场',
            'category': 'trend'
        },
        {
            'name': 'MACD金叉死叉策略',
            'code': '''# MACD金叉死叉策略
my_indicator_name = "MACD金叉死叉策略"
my_indicator_description = "MACD金叉买入，死叉卖出"

# @param fast_period int 12 快线周期
# @param slow_period int 26 慢线周期
# @param signal_period int 9 信号线周期
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

fast = params.get('fast_period', 12)
slow = params.get('slow_period', 26)
signal = params.get('signal_period', 9)

# 计算 MACD
ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
df['macd'] = ema_fast - ema_slow
df['signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
df['histogram'] = df['macd'] - df['signal']

# 金叉买入，死叉卖出
df['buy'] = (df['macd'] > df['signal']) & (df['macd'].shift(1) <= df['signal'].shift(1))
df['sell'] = (df['macd'] < df['signal']) & (df['macd'].shift(1) >= df['signal'].shift(1))
''',
            'description': 'MACD指标策略，适合中长期趋势',
            'category': 'trend'
        },
        {
            'name': '布林带突破策略',
            'code': '''# 布林带突破策略
my_indicator_name = "布林带突破策略"
my_indicator_description = "价格突破下轨买入，突破上轨卖出"

# @param period int 20 布林带周期
# @param std_dev float 2.0 标准差倍数
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

period = params.get('period', 20)
std_dev = params.get('std_dev', 2.0)

# 计算布林带
df['middle'] = df['close'].rolling(window=period).mean()
df['std'] = df['close'].rolling(window=period).std()
df['upper'] = df['middle'] + std_dev * df['std']
df['lower'] = df['middle'] - std_dev * df['std']

# 突破下轨买入，突破上轨卖出
df['buy'] = (df['close'] < df['lower']) & (df['close'].shift(1) >= df['lower'].shift(1))
df['sell'] = (df['close'] > df['upper']) & (df['close'].shift(1) <= df['upper'].shift(1))
''',
            'description': '布林带突破策略，适合波动市场',
            'category': 'volatility'
        },
        {
            'name': 'KDJ超买超卖策略',
            'code': '''# KDJ超买超卖策略
my_indicator_name = "KDJ超买超卖策略"
my_indicator_description = "K线与D线金叉买入，死叉卖出"

# @param period int 9 KDJ周期
# @param oversold int 20 超卖阈值
# @param overbought int 80 超买阈值
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

period = params.get('period', 9)
oversold = params.get('oversold', 20)
overbought = params.get('overbought', 80)

# 计算 KDJ
low_min = df['low'].rolling(window=period).min()
high_max = df['high'].rolling(window=period).max()
df['rsv'] = (df['close'] - low_min) / (high_max - low_min) * 100

df['k'] = df['rsv'].ewm(com=2, adjust=False).mean()
df['d'] = df['k'].ewm(com=2, adjust=False).mean()
df['j'] = 3 * df['k'] - 2 * df['d']

# K线上穿D线且在超卖区买入，K线下穿D线且在超买区卖出
df['buy'] = (df['k'] > df['d']) & (df['k'].shift(1) <= df['d'].shift(1)) & (df['k'] < oversold)
df['sell'] = (df['k'] < df['d']) & (df['k'].shift(1) >= df['d'].shift(1)) & (df['k'] > overbought)
''',
            'description': 'KDJ指标策略，适合短线交易',
            'category': 'momentum'
        }
    ]

    print("=" * 70)
    print("创建系统内置指标")
    print("=" * 70)

    created_count = 0
    for indicator_data in builtin_indicators:
        try:
            # 检查是否已存在
            existing = service.strategy_repo.get_by_name(indicator_data['name'])
            if existing:
                print(f"\n⚠️  指标已存在: {indicator_data['name']}")
                continue

            # 创建指标 - 直接调用repository方法以设置strategy_type
            validation_result = service.validate_code(
                indicator_data['code'],
                'indicator'
            )

            if not validation_result['valid']:
                print(f"\n✗ 验证失败: {indicator_data['name']}")
                print(f"  错误: {validation_result.get('error')}")
                continue

            # 直接使用repository创建，以便设置strategy_type='builtin'
            strategy = service.strategy_repo.create_user_strategy({
                'name': indicator_data['name'],
                'code_content': indicator_data['code'],
                'code_type': 'indicator',
                'strategy_type': 'builtin',  # 设置为系统内置指标
                'description': indicator_data['description'],
                'category': indicator_data['category'],
                'is_public': True,
                'parsed_params': validation_result.get('params', []),
                'risk_config': validation_result.get('risk_config', {}),
                'metadata': validation_result.get('metadata', {}),
                'validation_status': 'valid',
                'is_active': True
            })

            result = {
                'strategy_id': strategy['id'],
                'validation': validation_result
            }

            if result['validation']['valid']:
                print(f"\n✓ 创建成功: {indicator_data['name']}")
                print(f"  ID: {result['strategy_id']}")
                print(f"  分类: {indicator_data['category']}")
                print(f"  类型: builtin (系统内置)")
                created_count += 1
            else:
                print(f"\n✗ 创建失败: {indicator_data['name']}")
                print(f"  错误: {result['validation'].get('error')}")

        except Exception as e:
            print(f"\n✗ 创建失败: {indicator_data['name']}")
            print(f"  错误: {str(e)}")

    print("\n" + "=" * 70)
    print(f"完成！成功创建 {created_count}/{len(builtin_indicators)} 个系统指标")
    print("=" * 70)


if __name__ == '__main__':
    create_builtin_indicators()
