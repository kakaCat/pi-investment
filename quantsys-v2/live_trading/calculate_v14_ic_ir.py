"""
计算V14模型的IC和IR指标

IC (Information Coefficient): 因子预测值与实际收益的相关性
IR (Information Ratio): IC的稳定性指标，IR = IC均值 / IC标准差
"""

import os
import sys

import pandas as pd
import numpy as np
import xgboost as xgb
from pathlib import Path
import json
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

def get_test_data():
    """获取测试数据"""
    print("获取测试数据（2025-06-01 to 2026-06-01）...")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 获取创业板股票
    query = '''
        SELECT DISTINCT symbol FROM quant.stocks
        WHERE symbol LIKE '3%'
        LIMIT 100
    '''
    cursor.execute(query)
    symbols = [row[0] for row in cursor.fetchall()]

    # 获取K线数据
    placeholders = ','.join(['%s'] * len(symbols))
    query = f'''
        SELECT
            symbol,
            trade_date as date,
            open, high, low, close, volume,
            COALESCE(turnover_rate, 0) as turnover_rate
        FROM quant.daily_klines
        WHERE symbol IN ({placeholders})
          AND trade_date BETWEEN '2025-06-01' AND '2026-06-01'
        ORDER BY symbol, trade_date
    '''

    cursor.execute(query, symbols)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows, columns=['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'turnover_rate'])
    df['date'] = pd.to_datetime(df['date'])

    print(f"✓ 获取 {len(df)} 条K线数据，{df['symbol'].nunique()} 只股票")
    return df

def calculate_factors(df):
    """计算因子"""
    from live_trading.v13_factors import calculate_v13_factors
    print("计算因子...")
    return calculate_v13_factors(df)

def calculate_ic_ir():
    """计算IC和IR"""

    print("\n" + "="*80)
    print(" V14模型 IC/IR 计算 ")
    print("="*80)

    # 1. 加载模型
    model_path = Path('live_trading/models/v13_model.json')
    factors_path = Path('live_trading/models/valid_factors.json')

    if not model_path.exists() or not factors_path.exists():
        print("❌ 模型文件不存在")
        return

    print("\n[1/5] 加载V14模型...")
    model = xgb.XGBRegressor()
    model.load_model(str(model_path))

    with open(factors_path) as f:
        valid_factors = json.load(f)

    print(f"✓ 模型已加载: {len(valid_factors)}个因子")

    # 2. 获取测试数据
    print("\n[2/5] 获取测试数据...")
    test_data = get_test_data()

    # 3. 计算因子
    print("\n[3/5] 计算因子...")
    test_data = calculate_factors(test_data)

    # 4. 计算标签（实际未来5日收益）
    print("\n[4/5] 计算实际收益...")
    test_data = test_data.sort_values(['symbol', 'date'])
    test_data['actual_return'] = test_data.groupby('symbol')['close'].transform(
        lambda x: x.pct_change(5).shift(-5)
    )

    print(f"  原始样本: {len(test_data)}条")
    print(f"  有实际收益的: {test_data['actual_return'].notna().sum()}条")

    # 5. 模型预测
    print("\n[5/5] 计算IC和IR...")

    # 先检查哪些因子有NaN
    nan_counts = test_data[valid_factors].isna().sum()
    high_nan_factors = nan_counts[nan_counts > len(test_data) * 0.5].index.tolist()

    if high_nan_factors:
        print(f"  移除高NaN因子: {len(high_nan_factors)}个 - {high_nan_factors}")
        valid_factors_clean = [f for f in valid_factors if f not in high_nan_factors]
    else:
        valid_factors_clean = valid_factors

    print(f"  使用因子数: {len(valid_factors_clean)}")

    # 只保留有实际收益和所有因子都有值的样本
    test_clean = test_data.dropna(subset=['actual_return'] + valid_factors_clean).copy()

    print(f"  有效样本: {len(test_clean)}条")

    if len(test_clean) < 50:
        print(f"❌ 有效样本太少: {len(test_clean)}条")
        return

    X_test = test_clean[valid_factors_clean]
    y_actual = test_clean['actual_return']
    y_pred = model.predict(X_test)

    test_clean['predicted_return'] = y_pred

    # 按日期分组计算IC
    ic_by_date = []

    for date, group in test_clean.groupby('date'):
        if len(group) < 10:
            continue

        # 计算Spearman相关系数（IC）
        ic = group['predicted_return'].corr(group['actual_return'], method='spearman')

        if not np.isnan(ic):
            ic_by_date.append({
                'date': date,
                'ic': ic,
                'n_stocks': len(group)
            })

    ic_df = pd.DataFrame(ic_by_date)

    # 计算统计指标
    mean_ic = ic_df['ic'].mean()
    std_ic = ic_df['ic'].std()
    ir = mean_ic / std_ic if std_ic > 0 else 0

    ic_positive_rate = (ic_df['ic'] > 0).sum() / len(ic_df)

    # 输出结果
    print("\n" + "="*80)
    print("IC/IR 统计结果")
    print("="*80)

    print(f"\n📊 核心指标:")
    print(f"  IC均值 (Mean IC):        {mean_ic:.4f}")
    print(f"  IC标准差 (Std IC):       {std_ic:.4f}")
    print(f"  IR (Information Ratio):  {ir:.4f}")
    print(f"  IC>0的比例:              {ic_positive_rate:.1%}")

    print(f"\n📈 IC分布:")
    print(f"  最大IC:                  {ic_df['ic'].max():.4f}")
    print(f"  最小IC:                  {ic_df['ic'].min():.4f}")
    print(f"  中位数IC:                {ic_df['ic'].median():.4f}")
    print(f"  25分位数:                {ic_df['ic'].quantile(0.25):.4f}")
    print(f"  75分位数:                {ic_df['ic'].quantile(0.75):.4f}")

    print(f"\n📅 时间维度:")
    print(f"  测试天数:                {len(ic_df)}天")
    print(f"  平均每日股票数:          {ic_df['n_stocks'].mean():.0f}只")
    print(f"  总样本数:                {len(test_clean):,}条")

    # 评估
    print("\n" + "="*80)
    print("性能评估")
    print("="*80)

    print(f"\n根据量化标准:")

    if mean_ic >= 0.05:
        print(f"  ✅ IC均值 {mean_ic:.4f} >= 0.05 (优秀)")
    elif mean_ic >= 0.03:
        print(f"  ✅ IC均值 {mean_ic:.4f} >= 0.03 (良好)")
    elif mean_ic >= 0.02:
        print(f"  ⚠️  IC均值 {mean_ic:.4f} >= 0.02 (及格)")
    else:
        print(f"  ❌ IC均值 {mean_ic:.4f} < 0.02 (不达标)")

    if ir >= 2.0:
        print(f"  ✅ IR {ir:.4f} >= 2.0 (优秀)")
    elif ir >= 1.0:
        print(f"  ✅ IR {ir:.4f} >= 1.0 (良好)")
    elif ir >= 0.5:
        print(f"  ⚠️  IR {ir:.4f} >= 0.5 (及格)")
    else:
        print(f"  ❌ IR {ir:.4f} < 0.5 (不达标)")

    if ic_positive_rate >= 0.6:
        print(f"  ✅ IC正率 {ic_positive_rate:.1%} >= 60% (优秀)")
    elif ic_positive_rate >= 0.55:
        print(f"  ✅ IC正率 {ic_positive_rate:.1%} >= 55% (良好)")
    else:
        print(f"  ⚠️  IC正率 {ic_positive_rate:.1%} < 55% (一般)")

    # 行业标准对比
    print(f"\n行业标准对比:")
    print(f"  顶尖量化基金: IC=0.05-0.08, IR>2.0")
    print(f"  优秀量化基金: IC=0.03-0.05, IR=1.0-2.0")
    print(f"  及格量化策略: IC=0.02-0.03, IR=0.5-1.0")
    print(f"  V14模型:      IC={mean_ic:.4f}, IR={ir:.4f}")

    # 保存结果
    result = {
        'mean_ic': float(mean_ic),
        'std_ic': float(std_ic),
        'ir': float(ir),
        'ic_positive_rate': float(ic_positive_rate),
        'max_ic': float(ic_df['ic'].max()),
        'min_ic': float(ic_df['ic'].min()),
        'median_ic': float(ic_df['ic'].median()),
        'test_days': len(ic_df),
        'total_samples': len(test_clean),
        'avg_stocks_per_day': float(ic_df['n_stocks'].mean())
    }

    result_path = Path('live_trading/v14_ic_ir_result.json')
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n📁 结果已保存: {result_path}")

    # 保存IC时间序列
    ic_df.to_csv('live_trading/v14_ic_timeseries.csv', index=False)
    print(f"📁 IC时间序列已保存: live_trading/v14_ic_timeseries.csv")

    print("\n" + "="*80)

    return result

if __name__ == '__main__':
    calculate_ic_ir()
