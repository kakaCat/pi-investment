#!/usr/bin/env python3
"""
直接通过数据库连接创建系统内置指标
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库配置
db_config = {
    'dbname': os.getenv('PGDATABASE', 'quant_investment'),
    'user': os.getenv('PGUSER', 'mac'),
    'password': os.getenv('PGPASSWORD', ''),
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '5432')
}

# 添加项目路径以便导入验证器
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from domain.quantlib.engine.code_validator import CodeValidator
from domain.quantlib.engine.param_parser import ParamParser

def create_builtin_indicators():
    """创建系统内置指标"""

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
            'category': 'momentum',
            'author': 'system'
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
            'category': 'trend',
            'author': 'system'
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
            'description': 'MACD指标策略，适合趋势市场',
            'category': 'trend',
            'author': 'system'
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
            'description': '布林带突破策略，适合震荡市场',
            'category': 'volatility',
            'author': 'system'
        },
        {
            'name': 'KDJ超买超卖策略',
            'code': '''# KDJ超买超卖策略
my_indicator_name = "KDJ超买超卖策略"
my_indicator_description = "K线上穿D线且在超卖区买入，K线下穿D线且在超买区卖出"

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
            'category': 'momentum',
            'author': 'system'
        }
    ]

    print("=" * 70)
    print("创建系统内置指标（直接数据库方式）")
    print("=" * 70)

    try:
        # 连接数据库
        print(f"\n连接数据库: {db_config['dbname']}@{db_config['host']}:{db_config['port']}")
        conn = psycopg2.connect(**db_config, cursor_factory=RealDictCursor)
        conn.autocommit = True
        cursor = conn.cursor()
        print("✓ 数据库连接成功")

        # 初始化验证器
        validator = CodeValidator()
        param_parser = ParamParser()

        created_count = 0
        for indicator_data in builtin_indicators:
            try:
                # 检查是否已存在
                cursor.execute("""
                    SELECT id FROM quant.strategy_configs
                    WHERE strategy_name = %s
                """, (indicator_data['name'],))

                existing = cursor.fetchone()
                if existing:
                    print(f"\n⚠️  指标已存在: {indicator_data['name']} (ID: {existing['id']})")
                    continue

                # 验证代码
                try:
                    validator.validate(indicator_data['code'], 'indicator')
                    validation_status = 'valid'
                    validation_errors = None
                except Exception as e:
                    print(f"\n✗ 验证失败: {indicator_data['name']}")
                    print(f"  错误: {e}")
                    continue

                # 解析参数
                try:
                    parsed_params = param_parser.parse(indicator_data['code'])
                    risk_config = param_parser.extract_risk_config(indicator_data['code'])
                except Exception as e:
                    parsed_params = []
                    risk_config = {}

                # 插入数据库（category和author存储在metadata中）
                metadata = {
                    'builtin': True,
                    'category': indicator_data['category'],
                    'author': indicator_data['author']
                }

                cursor.execute("""
                    INSERT INTO quant.strategy_configs (
                        strategy_name, strategy_type, code_content, code_type,
                        description, author,
                        parsed_params, risk_config, metadata,
                        validation_status, validation_errors, is_active, parameters
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    indicator_data['name'],
                    'builtin',  # 设置为系统内置
                    indicator_data['code'],
                    'indicator',
                    indicator_data['description'],
                    indicator_data['author'],
                    json.dumps(parsed_params),
                    json.dumps(risk_config),
                    json.dumps(metadata),
                    validation_status,
                    validation_errors,
                    True,
                    '{}'  # parameters字段必填
                ))

                result = cursor.fetchone()
                print(f"\n✓ 创建成功: {indicator_data['name']}")
                print(f"  ID: {result['id']}")
                print(f"  分类: {indicator_data['category']}")
                print(f"  作者: {indicator_data['author']}")
                print(f"  类型: builtin (系统内置)")
                created_count += 1

            except Exception as e:
                print(f"\n✗ 创建失败: {indicator_data['name']}")
                print(f"  错误: {e}")
                import traceback
                traceback.print_exc()

        cursor.close()
        conn.close()

        print("\n" + "=" * 70)
        print(f"完成！成功创建 {created_count}/{len(builtin_indicators)} 个系统指标")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ 数据库连接失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    create_builtin_indicators()
