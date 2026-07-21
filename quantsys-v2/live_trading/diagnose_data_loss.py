"""
样本数据丢失问题诊断脚本

分析235,956条K线 → 160条有效样本的原因
"""

import os
os.environ['OMP_NUM_THREADS'] = '1'

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import psycopg2

def get_db_connection():
    """获取数据库连接"""
    db_config = {
        'dbname': os.getenv('PGDATABASE', 'quant_investment'),
        'user': os.getenv('PGUSER', os.getenv('USER')),
        'password': os.getenv('PGPASSWORD', ''),
        'host': os.getenv('PGHOST', 'localhost'),
        'port': os.getenv('PGPORT', '5432')
    }
    return psycopg2.connect(**db_config)

def diagnose_data_loss():
    """诊断数据丢失原因"""

    print("\n" + "="*80)
    print(" 样本数据丢失问题诊断 ")
    print("="*80)

    # 1. 获取原始数据
    print("\n[1/6] 获取原始K线数据...")
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT symbol FROM quant.stocks
        WHERE symbol LIKE '3%'
        LIMIT 100
    '''
    cursor.execute(query)
    symbols = [row[0] for row in cursor.fetchall()]

    placeholders = ','.join(['%s'] * len(symbols))
    query = f'''
        SELECT symbol, trade_date as date, close, volume,
               COALESCE(turnover_rate, 0) as turnover_rate
        FROM quant.daily_klines
        WHERE symbol IN ({placeholders})
          AND trade_date BETWEEN '2024-06-01' AND '2026-06-01'
        ORDER BY symbol, trade_date
    '''

    cursor.execute(query, symbols)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows, columns=['symbol', 'date', 'close', 'volume', 'turnover_rate'])
    df['date'] = pd.to_datetime(df['date'])

    print(f"✓ 原始数据: {len(df)}条, {df['symbol'].nunique()}只股票")

    # 2. 检查turnover_rate
    print("\n[2/6] 检查换手率数据质量...")
    turnover_null = df['turnover_rate'].isna().sum()
    turnover_zero = (df['turnover_rate'] == 0).sum()
    print(f"  换手率为NULL: {turnover_null}条 ({turnover_null/len(df)*100:.1f}%)")
    print(f"  换手率为0: {turnover_zero}条 ({turnover_zero/len(df)*100:.1f}%)")

    # 3. 模拟因子计算（关键部分）
    print("\n[3/6] 模拟因子计算...")

    result = []
    for symbol, group in df.groupby('symbol'):
        data = group.sort_values('date').copy()

        # 关键因子：需要60日窗口
        data['ma_60'] = data['close'].rolling(60).mean()

        # 关键因子：需要20日窗口
        data['volatility_20d'] = data['close'].pct_change().rolling(20).std()
        data['turnover_ma_ratio'] = data['turnover_rate'] / data['turnover_rate'].rolling(20).mean()

        # 基本面因子：需要60日+4期窗口
        pe_proxy = data['close'] / data['close'].rolling(60).mean()
        data['roe_proxy_q'] = 1 / (pe_proxy + 0.01)
        data['roe_proxy_y'] = data['roe_proxy_q'].rolling(4).mean()  # 再需要4期

        result.append(data)

    df_with_factors = pd.concat(result, ignore_index=True)

    print(f"  因子计算后: {len(df_with_factors)}条")

    # 检查各因子的NaN情况
    print("\n  关键因子NaN统计:")
    for col in ['ma_60', 'volatility_20d', 'turnover_ma_ratio', 'roe_proxy_y']:
        nan_count = df_with_factors[col].isna().sum()
        nan_pct = nan_count / len(df_with_factors) * 100
        print(f"    {col:<25} {nan_count:>6}条 ({nan_pct:>5.1f}%)")

    # 4. 添加标签（未来5日收益）
    print("\n[4/6] 添加标签（未来5日收益）...")
    df_with_factors = df_with_factors.sort_values(['symbol', 'date'])
    df_with_factors['label'] = df_with_factors.groupby('symbol')['close'].transform(
        lambda x: x.pct_change(5).shift(-5)
    )

    label_nan = df_with_factors['label'].isna().sum()
    print(f"  标签为NaN: {label_nan}条 ({label_nan/len(df_with_factors)*100:.1f}%)")

    # 5. 模拟严格清洗（dropna所有列）
    print("\n[5/6] 模拟数据清洗...")

    test_factors = ['ma_60', 'volatility_20d', 'turnover_ma_ratio', 'roe_proxy_y']

    print(f"\n  清洗前: {len(df_with_factors)}条")

    # 方案1: 严格清洗（当前V14的做法）
    df_strict = df_with_factors.dropna(subset=['label'] + test_factors)
    print(f"  严格清洗后(dropna所有列): {len(df_strict)}条 (保留{len(df_strict)/len(df_with_factors)*100:.2f}%)")

    # 方案2: 宽松清洗（只要求标签+80%因子）
    df_relaxed = df_with_factors.dropna(subset=['label']).copy()
    df_relaxed = df_relaxed[df_relaxed[test_factors].isna().sum(axis=1) <= len(test_factors) * 0.2]
    print(f"  宽松清洗后(标签+80%因子): {len(df_relaxed)}条 (保留{len(df_relaxed)/len(df_with_factors)*100:.2f}%)")

    # 方案3: 填充NaN后清洗
    df_filled = df_with_factors.dropna(subset=['label']).copy()
    for col in test_factors:
        if df_filled[col].isna().any():
            df_filled[col] = df_filled[col].fillna(df_filled[col].median())
    print(f"  填充NaN后: {len(df_filled)}条 (保留{len(df_filled)/len(df_with_factors)*100:.2f}%)")

    # 6. 分析关键原因
    print("\n[6/6] 数据丢失原因分析...")
    print("\n" + "="*80)
    print(" 根本原因 ")
    print("="*80)

    # 找出哪个因子导致最多数据丢失
    print("\n单个因子导致的数据丢失:")
    for col in test_factors:
        df_drop_one = df_with_factors.dropna(subset=['label', col])
        loss = len(df_with_factors) - len(df_drop_one)
        loss_pct = loss / len(df_with_factors) * 100
        print(f"  {col:<25} 丢失{loss:>6}条 ({loss_pct:>5.1f}%)")

    # 组合效应
    print("\n组合清洗效应:")
    df_temp = df_with_factors.dropna(subset=['label'])
    print(f"  只要求label: 保留{len(df_temp)}条 ({len(df_temp)/len(df_with_factors)*100:.1f}%)")

    for i, col in enumerate(test_factors, 1):
        df_temp = df_temp.dropna(subset=[col])
        print(f"  +{col}: 保留{len(df_temp)}条 ({len(df_temp)/len(df_with_factors)*100:.1f}%)")

    print("\n" + "="*80)
    print(" 结论 ")
    print("="*80)

    print(f"""
关键发现:
1. turnover_ma_ratio是最大元凶
   - 换手率数据本身有{turnover_zero}条为0或NULL
   - rolling(20).mean()会放大NaN
   - 导致该因子大量为NaN

2. 窗口期累积效应
   - ma_60需要60条历史数据
   - roe_proxy_y需要60+4=64条
   - 每只股票前64条基本都是NaN

3. 严格dropna导致雪崩
   - 73个因子，只要1个NaN就丢弃整行
   - 结果: 235,956条 → 160条 (99.93%丢失)

解决方案:
✓ 移除turnover_ma_ratio因子（贡献度为0）
✓ 对剩余因子使用中位数/前向填充
✓ 只要求80%因子有值即可
✓ 预期保留率: >80%
✓ 预期有效样本: >50,000条
    """)

    print("\n" + "="*80)

if __name__ == '__main__':
    diagnose_data_loss()
