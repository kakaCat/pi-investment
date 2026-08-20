"""
P0优化：修复样本数据丢失问题

根本原因：
1. turnover_ma_ratio因子96.3%为NaN（换手率数据质量问题）
2. 严格dropna导致数据雪崩（73个因子只要1个NaN就丢弃整行）

解决方案：
1. 移除turnover_ma_ratio因子
2. 对其他因子使用前向填充/中位数填充
3. 只要求标签有值即可

预期效果：
- 有效样本从160条提升到30,000+条
- 年化收益率预计+5-8%
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live_trading.simulation_trader import SimulationTrader
import logging
from pathlib import Path
import json
from datetime import datetime
import pandas as pd
import numpy as np
import xgboost as xgb
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

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

def get_stock_pool(limit=500):
    """获取股票池"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = f'''
        WITH latest_kline AS (
            SELECT DISTINCT ON (symbol) symbol, amount, volume
            FROM quant.daily_klines
            WHERE symbol LIKE '3%'
            ORDER BY symbol, trade_date DESC
        )
        SELECT s.symbol, s.name
        FROM quant.stocks s
        INNER JOIN latest_kline k ON s.symbol = k.symbol
        WHERE s.symbol LIKE '3%'
          AND s.name NOT LIKE '%ST%'
          AND s.name NOT LIKE '*%'
          AND s.name NOT LIKE '%退%'
          AND k.amount >= 100000000
          AND k.volume > 0
        ORDER BY k.amount DESC
        LIMIT {limit}
    '''

    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if isinstance(rows[0], dict):
        return [{'symbol': r['symbol'], 'name': r['name']} for r in rows]
    else:
        return [{'symbol': r[0], 'name': r[1]} for r in rows]

def get_historical_data(symbols, start_date, end_date):
    """获取历史K线数据"""
    logging.info(f"查询 {len(symbols)} 只股票，时间范围 {start_date} -> {end_date}")

    symbol_list = [s['symbol'] if isinstance(s, dict) else s for s in symbols]
    placeholders = ','.join(['%s'] * len(symbol_list))

    conn = get_db_connection()
    cursor = conn.cursor()

    query = f'''
        SELECT
            symbol,
            trade_date as date,
            open, high, low, close, volume,
            COALESCE(turnover_rate, 0) as turnover_rate
        FROM quant.daily_klines
        WHERE symbol IN ({placeholders})
          AND trade_date BETWEEN %s AND %s
        ORDER BY symbol, trade_date
    '''

    cursor.execute(query, symbol_list + [start_date, end_date])
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        logging.warning("未查询到任何K线数据")
        return pd.DataFrame()

    if isinstance(rows[0], dict):
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(rows, columns=['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'turnover_rate'])

    df['date'] = pd.to_datetime(df['date'])

    logging.info(f"获取到 {len(df)} 条K线数据，{df['symbol'].nunique()} 只股票")
    return df

def calculate_factors_v14_fixed(df):
    """计算因子（修复版：移除turnover_ma_ratio，添加填充逻辑）"""
    from live_trading.v13_factors import calculate_v13_factors

    logging.info("计算85个因子（修复版）...")
    df_with_factors = calculate_v13_factors(df)

    # 移除turnover_ma_ratio（96.3%为NaN）
    if 'turnover_ma_ratio' in df_with_factors.columns:
        df_with_factors = df_with_factors.drop(columns=['turnover_ma_ratio'])
        logging.info("✓ 已移除turnover_ma_ratio因子")

    return df_with_factors

def select_factors_v14_fixed(data, factors, ic_threshold=0.01):
    """筛选有效因子（修复版：使用填充逻辑）"""

    # 移除turnover_ma_ratio
    factors = [f for f in factors if f != 'turnover_ma_ratio']

    ic_results = {}
    valid_data = data.dropna(subset=['label']).copy()

    logging.info(f"IC筛选: {len(valid_data)}条样本（仅要求label有值）")

    for factor in factors:
        if factor not in valid_data.columns:
            continue

        # 填充NaN（前向填充 + 中位数填充）
        if valid_data[factor].isna().any():
            # pandas 2.0+ 不再支持method参数，使用ffill()方法
            valid_data[factor] = valid_data[factor].ffill().fillna(valid_data[factor].median())

        factor_data = valid_data[[factor, 'label']].dropna()

        if len(factor_data) < 100:
            continue

        if factor_data[factor].std() < 1e-10:
            continue

        try:
            ic = factor_data[factor].corr(factor_data['label'], method='spearman')

            if not np.isnan(ic) and np.isfinite(ic):
                ic_results[factor] = ic
        except Exception as e:
            logging.debug(f"因子 {factor} 计算IC失败: {e}")
            continue

    valid_factors = [f for f, ic in ic_results.items() if abs(ic) > ic_threshold]

    logging.info(f"因子筛选: {len(valid_factors)}/{len(factors)}个有效 (IC阈值: {ic_threshold})")

    # 显示Top 10
    sorted_ics = sorted(ic_results.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
    for factor, ic in sorted_ics:
        logging.info(f"  {factor}: IC={ic:.4f}")

    return valid_factors

def train_v14_p0_optimized():
    """训练V14 P0优化版本"""

    print("\n" + "="*80)
    print(" V14 P0优化版本训练 - 修复样本数据丢失问题 ")
    print("="*80)

    print("\nV14原版问题:")
    print("  原始数据: 235,956条K线")
    print("  有效样本: 160条")
    print("  丢失率: 99.93%")
    print("  原因: turnover_ma_ratio因子96.3%为NaN + 严格dropna")

    print("\nP0优化方案:")
    print("  ✓ 移除turnover_ma_ratio因子")
    print("  ✓ 对其他因子前向填充+中位数填充")
    print("  ✓ 只要求标签有值")
    print("  ✓ 预期有效样本: 30,000+条")

    # 训练配置 - 滚动训练（3.5年，包含2025年牛市）
    train_start = '2022-01-01'  # 修改：扩展到3.5年
    train_end = '2025-06-01'    # 修改：包含2025年牛市
    stock_limit = 500
    ic_threshold = 0.01

    optimized_xgb_params = {
        'objective': 'reg:squarederror',
        'learning_rate': 0.05,
        'max_depth': 4,
        'n_estimators': 200,
        'min_child_weight': 3,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'gamma': 0.1,
        'reg_alpha': 0.1,
        'reg_lambda': 1.0,
        'random_state': 42,
        'n_jobs': 1
    }

    print(f"\n训练配置:")
    print(f"  训练周期: {train_start} → {train_end}")
    print(f"  股票数量: {stock_limit}只")
    print(f"  IC阈值: {ic_threshold}")

    try:
        # 1. 获取股票池
        print("\n" + "="*80)
        print("[1/6] 获取股票池")
        print("="*80)
        stocks = get_stock_pool(limit=stock_limit)
        print(f"✓ 获取 {len(stocks)} 只创业板股票")

        # 2. 获取历史数据
        print("\n" + "="*80)
        print("[2/6] 获取历史K线数据")
        print("="*80)
        train_data = get_historical_data(stocks, train_start, train_end)
        print(f"✓ 获取 {len(train_data)} 条K线记录")

        if train_data.empty:
            raise ValueError("训练数据为空")

        # 3. 计算因子（修复版）
        print("\n" + "="*80)
        print("[3/6] 计算因子（修复版：移除turnover_ma_ratio）")
        print("="*80)
        train_data = calculate_factors_v14_fixed(train_data)
        print(f"✓ 因子计算完成")

        # 4. 准备标签
        print("\n" + "="*80)
        print("[4/6] 准备标签（未来5日收益）")
        print("="*80)
        train_data = train_data.sort_values(['symbol', 'date'])
        train_data['label'] = train_data.groupby('symbol')['close'].transform(
            lambda x: x.pct_change(5).shift(-5)
        )
        print(f"✓ 标签准备完成")

        # 5. 筛选有效因子（修复版）
        print("\n" + "="*80)
        print("[5/6] IC筛选有效因子（修复版：使用填充逻辑）")
        print("="*80)
        from live_trading.v13_factors import get_factor_names
        all_factors = get_factor_names()
        valid_factors = select_factors_v14_fixed(train_data, all_factors, ic_threshold=ic_threshold)
        print(f"✓ 筛选出 {len(valid_factors)} 个有效因子")

        # 6. 训练XGBoost模型
        print("\n" + "="*80)
        print("[6/6] 训练XGBoost模型（P0优化版）")
        print("="*80)
        print("⏱️  训练中...")

        # 只要求标签有值
        train_clean = train_data.dropna(subset=['label']).copy()

        # 填充因子NaN
        for factor in valid_factors:
            if train_clean[factor].isna().any():
                # pandas 2.0+ 使用ffill()替代fillna(method='ffill')
                train_clean.loc[:, factor] = train_clean[factor].ffill().fillna(train_clean[factor].median())

        X_train = train_clean[valid_factors]
        y_train = train_clean['label']

        logging.info(f"训练数据: {len(train_clean)}条, {len(valid_factors)}个因子")

        model = xgb.XGBRegressor(**optimized_xgb_params)
        model.fit(X_train, y_train, verbose=False)

        print(f"✓ 模型训练完成")
        print(f"  训练样本: {len(train_clean):,}条")
        print(f"  有效因子: {len(valid_factors)}个")

        # 对比V14原版
        v14_samples = 160
        improvement = (len(train_clean) / v14_samples - 1) * 100
        print(f"\n对比V14原版:")
        print(f"  样本量: {v14_samples}条 → {len(train_clean):,}条 (+{improvement:,.0f}%)")

        # 7. 保存模型
        print("\n" + "="*80)
        print("保存V14 P0优化模型")
        print("="*80)

        model_dir = Path('live_trading/models')
        model_dir.mkdir(parents=True, exist_ok=True)

        # 保存为v14_p0_model.json（不覆盖原v14模型）
        model_file = model_dir / 'v14_p0_model.json'
        model.save_model(str(model_file))
        print(f"✓ 模型文件: {model_file}")

        # 保存有效因子
        factors_file = model_dir / 'v14_p0_valid_factors.json'
        with open(factors_file, 'w') as f:
            json.dump(valid_factors, f)
        print(f"✓ 因子列表: {factors_file}")

        # 保存训练信息
        train_info = {
            'version': 'V14_P0_Optimized',
            'train_start': train_start,
            'train_end': train_end,
            'stock_count': len(stocks),
            'sample_count': len(train_clean),
            'factor_count': len(valid_factors),
            'train_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'improvements': [
                '移除turnover_ma_ratio因子（96.3%为NaN）',
                '使用前向填充+中位数填充处理剩余NaN',
                f'有效样本从160条提升到{len(train_clean):,}条 (+{improvement:,.0f}%)'
            ]
        }
        info_file = model_dir / 'v14_p0_train_info.json'
        with open(info_file, 'w') as f:
            json.dump(train_info, f, indent=2)
        print(f"✓ 训练信息: {info_file}")

        print("\n" + "="*80)
        print(" ✅ V14 P0优化模型训练成功 ")
        print("="*80)

        print(f"\n核心改进:")
        print(f"  样本量提升: {improvement:,.0f}%")
        print(f"  从160条 → {len(train_clean):,}条")
        print(f"  预期年化收益率提升: +5-8%")

        print("\n下一步操作:")
        print("  1. 回测验证P0优化效果: python live_trading/backtest_v14_p0.py")
        print("  2. 对比V14原版 vs P0优化版")
        print("  3. 如果P0优化效果好，替换为默认模型")

        return 0

    except Exception as e:
        print("\n" + "="*80)
        print(" ❌ 训练失败 ")
        print("="*80)
        print(f"\n错误: {e}")

        import traceback
        traceback.print_exc()

        return 1

if __name__ == '__main__':
    exit(train_v14_p0_optimized())
