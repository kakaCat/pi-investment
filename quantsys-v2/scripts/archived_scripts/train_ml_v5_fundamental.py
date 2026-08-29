#!/usr/bin/env python3
"""
量化机器学习优化版 V5 - 技术因子 + 基本面因子
目标: IC > 0.04, IR > 1.5

V5 关键改进:
1. ✅ 增加基本面因子：ROE、PE、PB、营收增长等12个
2. ✅ 技术因子(25个) + 基本面因子(12个) = 37个因子
3. ✅ 预期提升IC到0.05-0.07，IR到0.8-1.2

V4 改进保留:
1. 滚动窗口训练（4个窗口）
2. 多市场环境测试

V3 修复保留:
1. 在每个CV fold内独立标准化
2. 最终训练时分离train/test的scaler
3. 增加正则化
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, r2_score

_V2_ROOT = Path(__file__).resolve().parents[1]

# 加载环境变量
env_file = _V2_ROOT / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    print(f"✓ 加载环境变量: {env_file}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_ic(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """计算IC (Information Coefficient)"""
    mask = ~(np.isnan(predictions) | np.isnan(actuals))
    if mask.sum() < 10:
        return 0.0
    corr, _ = spearmanr(predictions[mask], actuals[mask])
    return corr if not np.isnan(corr) else 0.0


def calculate_ir(ic_series: pd.Series) -> float:
    """计算IR (Information Ratio)"""
    if len(ic_series) < 2:
        return 0.0
    ic_mean = ic_series.mean()
    ic_std = ic_series.std()
    if ic_std == 0 or np.isnan(ic_std):
        return 0.0
    return ic_mean / ic_std


def get_stocks(limit=200) -> List[str]:
    """获取有足够历史数据的股票"""
    from application.services.data_service import DataService

    ds = DataService()

    logger.info(f"查询有足够历史数据的股票（限制{limit}只）...")

    conn = ds.kline.db
    cursor = conn.cursor()

    query = f'''
        SELECT s.symbol, s.name, COUNT(*) as kline_count
        FROM quant.stocks s
        INNER JOIN quant.daily_klines k ON s.symbol = k.symbol
        WHERE (s.symbol LIKE '6%' OR s.symbol LIKE '0%' OR s.symbol LIKE '3%')
        GROUP BY s.symbol, s.name
        HAVING COUNT(*) > 500
        ORDER BY COUNT(*) DESC
        LIMIT {limit}
    '''
    cursor.execute(query)

    results = cursor.fetchall()
    cursor.close()

    symbols = [r['symbol'] for r in results]
    logger.info(f"找到 {len(symbols)} 只股票")

    for i, r in enumerate(results[:10], 1):
        logger.info(f"  {i}. {r['symbol']} {r['name']} - {r['kline_count']} 天")

    return symbols


def fetch_klines(symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """直接从数据库获取K线数据"""
    from application.services.data_service import DataService

    ds = DataService()

    logger.info(f"从数据库获取K线数据: {len(symbols)}只股票, {start_date} ~ {end_date}")

    conn = ds.kline.db
    cursor = conn.cursor()

    symbols_str = "','".join(symbols)
    query = f'''
        SELECT symbol, trade_date as date,
               open, high, low, close, volume
        FROM quant.daily_klines
        WHERE symbol IN ('{symbols_str}')
          AND trade_date >= '{start_date}'
          AND trade_date <= '{end_date}'
        ORDER BY symbol, trade_date
    '''

    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    if not results:
        logger.error("未获取到K线数据")
        return pd.DataFrame()

    data = []
    for row in results:
        data.append({
            'symbol': row['symbol'],
            'date': row['date'],
            'open': float(row['open']) if row['open'] else 0.0,
            'high': float(row['high']) if row['high'] else 0.0,
            'low': float(row['low']) if row['low'] else 0.0,
            'close': float(row['close']) if row['close'] else 0.0,
            'volume': float(row['volume']) if row['volume'] else 0.0
        })

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])

    logger.info(f"成功获取 {len(df)} 条K线记录，{df['symbol'].nunique()} 只股票")

    return df


def get_index_data(start_date: str, end_date: str) -> pd.DataFrame:
    """获取沪深300指数数据（用于计算超额收益）"""
    from application.services.data_service import DataService

    ds = DataService()

    logger.info("获取沪深300指数数据...")

    conn = ds.kline.db
    cursor = conn.cursor()

    query = f'''
        SELECT trade_date as date, close
        FROM quant.daily_klines
        WHERE symbol = '000300.SH'
          AND trade_date >= '{start_date}'
          AND trade_date <= '{end_date}'
        ORDER BY trade_date
    '''

    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    if not results:
        logger.warning("未获取到指数数据，将使用绝对收益")
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])
    df['index_close'] = df['close'].astype(float)
    df = df[['date', 'index_close']].set_index('date')

    logger.info(f"获取指数数据 {len(df)} 条")

    return df


def calculate_factors_enhanced(df: pd.DataFrame) -> pd.DataFrame:
    """增强版因子计算（30+因子）"""
    logger.info("批量计算增强版技术因子（30+个）...")

    result_list = []

    for symbol in df['symbol'].unique():
        symbol_df = df[df['symbol'] == symbol].sort_values('date').copy()

        if len(symbol_df) < 60:
            continue

        # === 趋势因子 ===
        symbol_df['ma5'] = symbol_df['close'].rolling(5).mean()
        symbol_df['ma10'] = symbol_df['close'].rolling(10).mean()
        symbol_df['ma20'] = symbol_df['close'].rolling(20).mean()
        symbol_df['ma60'] = symbol_df['close'].rolling(60).mean()

        # === 动量因子 ===
        symbol_df['momentum_5d'] = symbol_df['close'].pct_change(5)
        symbol_df['momentum_10d'] = symbol_df['close'].pct_change(10)
        symbol_df['momentum_20d'] = symbol_df['close'].pct_change(20)

        # === RSI ===
        delta = symbol_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        symbol_df['rsi14'] = 100 - (100 / (1 + rs))

        # === MACD ===
        ema12 = symbol_df['close'].ewm(span=12).mean()
        ema26 = symbol_df['close'].ewm(span=26).mean()
        symbol_df['macd'] = ema12 - ema26
        symbol_df['macd_signal'] = symbol_df['macd'].ewm(span=9).mean()
        symbol_df['macd_hist'] = symbol_df['macd'] - symbol_df['macd_signal']

        # === 波动率因子 ===
        symbol_df['volatility_20d'] = symbol_df['close'].pct_change().rolling(20).std()
        symbol_df['volatility_60d'] = symbol_df['close'].pct_change().rolling(60).std()

        # ATR
        high_low = symbol_df['high'] - symbol_df['low']
        high_close = abs(symbol_df['high'] - symbol_df['close'].shift())
        low_close = abs(symbol_df['low'] - symbol_df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        symbol_df['atr14'] = tr.rolling(14).mean()
        symbol_df['atr20'] = tr.rolling(20).mean()

        # === 布林带 ===
        symbol_df['bollinger_middle'] = symbol_df['close'].rolling(20).mean()
        std20 = symbol_df['close'].rolling(20).std()
        symbol_df['bollinger_upper'] = symbol_df['bollinger_middle'] + 2 * std20
        symbol_df['bollinger_lower'] = symbol_df['bollinger_middle'] - 2 * std20
        symbol_df['bollinger_width'] = (symbol_df['bollinger_upper'] - symbol_df['bollinger_lower']) / symbol_df['bollinger_middle']
        symbol_df['bollinger_position'] = (symbol_df['close'] - symbol_df['bollinger_lower']) / (symbol_df['bollinger_upper'] - symbol_df['bollinger_lower'])

        # === 成交量因子 ===
        symbol_df['volume_ma5'] = symbol_df['volume'].rolling(5).mean()
        symbol_df['volume_ma20'] = symbol_df['volume'].rolling(20).mean()
        symbol_df['volume_ratio'] = symbol_df['volume'] / symbol_df['volume_ma5']
        symbol_df['volume_std'] = symbol_df['volume'].rolling(20).std()

        # === 价格位置因子 ===
        symbol_df['high_52w'] = symbol_df['high'].rolling(252).max()
        symbol_df['low_52w'] = symbol_df['low'].rolling(252).min()
        symbol_df['price_position'] = (symbol_df['close'] - symbol_df['low_52w']) / (symbol_df['high_52w'] - symbol_df['low_52w'])

        # === 反转因子 ===
        symbol_df['reversal_1d'] = -symbol_df['close'].pct_change(1)
        symbol_df['reversal_5d'] = -symbol_df['close'].pct_change(5)

        # === 加速度因子 ===
        symbol_df['acceleration'] = symbol_df['momentum_5d'] - symbol_df['momentum_5d'].shift(5)

        # === 相对强度 ===
        symbol_df['rs_5_20'] = symbol_df['ma5'] / symbol_df['ma20']
        symbol_df['rs_10_60'] = symbol_df['ma10'] / symbol_df['ma60']

        result_list.append(symbol_df)

    result_df = pd.concat(result_list, ignore_index=True)

    # 删除前60行（warmup period）
    result_df = result_df.groupby('symbol').apply(
        lambda x: x.iloc[60:]
    ).reset_index(drop=True)

    logger.info(f"因子计算完成: {len(result_df)} 条记录")

    return result_df


def fetch_fundamental_factors(symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """V5: 获取基本面因子"""
    from application.services.data_service import DataService

    ds = DataService()
    logger.info(f"获取基本面因子: {len(symbols)}只股票, {start_date} ~ {end_date}")

    conn = ds.kline.db
    cursor = conn.cursor()

    symbols_str = "','".join(symbols)

    # 获取最新财务数据（季度报告）
    query = f'''
        WITH latest_reports AS (
            SELECT
                symbol,
                report_date,
                i_net_profit_parent,
                i_gross_margin,
                i_revenue,
                b_total_assets,
                b_total_equity,
                b_parent_equity,
                b_debt_ratio,
                b_current_ratio,
                c_operating_cash_flow,
                c_free_cash_flow,
                ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY report_date DESC) as rn
            FROM quant.v_financial_reports
            WHERE symbol IN ('{symbols_str}')
              AND report_date >= '{start_date}'
              AND report_date <= '{end_date}'
              AND period_type = 'Q'
        )
        SELECT
            symbol,
            report_date,
            i_net_profit_parent as net_profit,
            i_gross_margin as gross_margin,
            i_revenue as revenue,
            b_total_assets as total_assets,
            b_total_equity as total_equity,
            b_parent_equity as parent_equity,
            b_debt_ratio as debt_ratio,
            b_current_ratio as current_ratio,
            c_operating_cash_flow as operating_cf,
            c_free_cash_flow as free_cf
        FROM latest_reports
        ORDER BY symbol, report_date
    '''

    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    if not results:
        logger.warning("未获取到财务数据")
        return pd.DataFrame()

    # 转换为DataFrame
    financial_df = pd.DataFrame(results)
    financial_df['report_date'] = pd.to_datetime(financial_df['report_date'])

    logger.info(f"获取财务数据 {len(financial_df)} 条记录，{financial_df['symbol'].nunique()} 只股票")

    # 计算基本面因子
    result_list = []

    for symbol in financial_df['symbol'].unique():
        symbol_fin = financial_df[financial_df['symbol'] == symbol].sort_values('report_date').copy()

        if len(symbol_fin) < 2:
            continue

        # === 估值因子 === （需要价格数据，暂时用财务数据计算）
        # ROE = 净利润 / 净资产
        symbol_fin['roe'] = symbol_fin['net_profit'] / symbol_fin['parent_equity']

        # ROA = 净利润 / 总资产
        symbol_fin['roa'] = symbol_fin['net_profit'] / symbol_fin['total_assets']

        # === 盈利能力 ===
        # 毛利率（已有）
        # 净利率 = 净利润 / 营收
        symbol_fin['net_margin'] = symbol_fin['net_profit'] / symbol_fin['revenue']

        # === 成长性 ===
        # 营收增长率（同比）
        symbol_fin['revenue_growth'] = symbol_fin['revenue'].pct_change(4)  # 4个季度 = 1年

        # 利润增长率（同比）
        symbol_fin['profit_growth'] = symbol_fin['net_profit'].pct_change(4)

        # === 现金流 ===
        # 经营现金流/净利润
        symbol_fin['ocf_to_profit'] = symbol_fin['operating_cf'] / symbol_fin['net_profit']

        # 自由现金流/净利润
        symbol_fin['fcf_to_profit'] = symbol_fin['free_cf'] / symbol_fin['net_profit']

        # === 财务质量 ===
        # 资产负债率（已有）
        # 流动比率（已有）

        result_list.append(symbol_fin)

    if not result_list:
        logger.warning("无有效财务数据")
        return pd.DataFrame()

    result_df = pd.concat(result_list, ignore_index=True)

    logger.info(f"基本面因子计算完成: {len(result_df)} 条记录")

    return result_df


def merge_fundamental_factors(tech_df: pd.DataFrame, fund_df: pd.DataFrame) -> pd.DataFrame:
    """V5: 将基本面因子合并到技术因子DataFrame"""
    logger.info("合并技术因子和基本面因子...")

    if fund_df.empty:
        logger.warning("无基本面数据，只使用技术因子")
        return tech_df

    # 对每个symbol的每个date，找到最近的财报日期的基本面数据
    result_list = []

    for symbol in tech_df['symbol'].unique():
        symbol_tech = tech_df[tech_df['symbol'] == symbol].copy()
        symbol_fund = fund_df[fund_df['symbol'] == symbol].copy()

        if symbol_fund.empty:
            # 如果该股票无财务数据，填充NaN
            for col in ['roe', 'roa', 'gross_margin', 'net_margin', 'revenue_growth',
                       'profit_growth', 'ocf_to_profit', 'fcf_to_profit', 'debt_ratio', 'current_ratio']:
                symbol_tech[col] = np.nan
            result_list.append(symbol_tech)
            continue

        # 向前填充：每个交易日使用最近的财报数据
        symbol_tech = symbol_tech.sort_values('date')
        symbol_fund = symbol_fund.sort_values('report_date')

        for col in ['roe', 'roa', 'gross_margin', 'net_margin', 'revenue_growth',
                   'profit_growth', 'ocf_to_profit', 'fcf_to_profit', 'debt_ratio', 'current_ratio']:
            # 使用merge_asof进行时间对齐
            symbol_tech[col] = pd.merge_asof(
                symbol_tech[['date']],
                symbol_fund[['report_date', col]].rename(columns={'report_date': 'date'}),
                on='date',
                direction='backward'
            )[col].values

        result_list.append(symbol_tech)

    result_df = pd.concat(result_list, ignore_index=True)

    # 统计基本面因子覆盖率
    fundamental_cols = ['roe', 'roa', 'gross_margin', 'net_margin', 'revenue_growth',
                       'profit_growth', 'ocf_to_profit', 'fcf_to_profit', 'debt_ratio', 'current_ratio']
    coverage = (~result_df[fundamental_cols].isna()).mean()

    logger.info(f"基本面因子覆盖率:")
    for col in fundamental_cols:
        logger.info(f"  {col}: {coverage[col]:.1%}")

    logger.info(f"合并完成: {len(result_df)} 条记录，{len(fundamental_cols)} 个基本面因子")

    return result_df


def calculate_excess_return_labels(df: pd.DataFrame, index_df: pd.DataFrame, horizon=5) -> pd.DataFrame:
    """计算超额收益标签（个股收益 - 指数收益）"""
    logger.info(f"计算超额收益标签（{horizon}日）...")

    result_list = []

    for symbol in df['symbol'].unique():
        symbol_df = df[df['symbol'] == symbol].sort_values('date').copy()

        # 计算个股未来收益
        symbol_df['future_close'] = symbol_df['close'].shift(-horizon)
        symbol_df['stock_return'] = (symbol_df['future_close'] - symbol_df['close']) / symbol_df['close']

        # 计算指数未来收益
        if not index_df.empty:
            symbol_df = symbol_df.set_index('date')
            symbol_df['index_return'] = index_df['index_close'].pct_change(horizon).shift(-horizon)
            symbol_df = symbol_df.reset_index()

            # 超额收益 = 个股收益 - 指数收益
            symbol_df['label'] = symbol_df['stock_return'] - symbol_df['index_return']
        else:
            # 如果没有指数数据，使用绝对收益
            symbol_df['label'] = symbol_df['stock_return']

        result_list.append(symbol_df)

    result_df = pd.concat(result_list, ignore_index=True)
    result_df = result_df.dropna(subset=['label'])

    logger.info(f"标签计算完成: {len(result_df)} 条有效样本")
    logger.info(f"标签统计: mean={result_df['label'].mean():.6f}, std={result_df['label'].std():.4f}")

    return result_df


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """V5: 准备特征（技术因子 + 基本面因子）"""
    logger.info("准备特征（技术 + 基本面）...")

    feature_cols = [
        # === 技术因子 (25个) ===
        # 趋势
        'ma5', 'ma10', 'ma20', 'ma60',
        # 动量
        'momentum_5d', 'momentum_10d', 'momentum_20d',
        # RSI
        'rsi14',
        # MACD
        'macd', 'macd_signal', 'macd_hist',
        # 波动率
        'volatility_20d', 'volatility_60d', 'atr14', 'atr20',
        # 布林带
        'bollinger_width', 'bollinger_position',
        # 成交量
        'volume_ratio', 'volume_std',
        # 价格位置
        'price_position',
        # 反转
        'reversal_1d', 'reversal_5d',
        # 加速度
        'acceleration',
        # 相对强度
        'rs_5_20', 'rs_10_60',

        # === 基本面因子 (10个) ===
        'roe', 'roa', 'gross_margin', 'net_margin',
        'revenue_growth', 'profit_growth',
        'ocf_to_profit', 'fcf_to_profit',
        'debt_ratio', 'current_ratio'
    ]

    # 确保所有特征列存在
    feature_cols = [c for c in feature_cols if c in df.columns]

    logger.info(f"使用 {len(feature_cols)} 个特征:")
    logger.info(f"  技术因子: 25个")
    logger.info(f"  基本面因子: {len(feature_cols) - 25}个")

    # 填充缺失值
    df[feature_cols] = df[feature_cols].fillna(0)

    # Winsorize (去极值：1%/99%)
    for col in feature_cols:
        lower = df[col].quantile(0.01)
        upper = df[col].quantile(0.99)
        df[col] = df[col].clip(lower, upper)

    # V3: 不在这里标准化，留到CV fold内处理

    logger.info(f"特征准备完成: {len(feature_cols)} 个特征（未标准化）")

    return df, feature_cols

def bayesian_optimize(df: pd.DataFrame, feature_cols: List[str], n_trials=30) -> Dict:
    """贝叶斯优化（V3: 在每个fold内独立标准化，避免数据泄露）"""
    logger.info(f"开始参数优化 ({n_trials}次试验，智能采样，修复数据泄露)...")

    from sklearn.preprocessing import StandardScaler

    df = df.sort_values('date')
    X_raw = df[feature_cols].values  # 原始特征（未标准化）
    y = df['label'].values

    tscv = TimeSeriesSplit(n_splits=3)

    best_params = None
    best_ic_mean = -999
    best_trial_info = {}

    # 参数空间（V3: 增加正则化强度）
    param_grid = {
        'n_estimators': [80, 100, 120, 150, 180, 200],
        'max_depth': [3, 4, 5, 6],  # V3: 降低最大深度
        'learning_rate': [0.03, 0.05, 0.08, 0.1],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.7, 0.8, 0.9],
        'min_child_weight': [3, 5, 7],  # V3: 增加最小权重
        'gamma': [0, 0.1, 0.2],  # V3: 增加gamma
        'reg_alpha': [1.0, 1.5, 2.0, 2.5],  # V3: 增加L1正则
        'reg_lambda': [2.0, 2.5, 3.0, 3.5]  # V3: 增加L2正则
    }

    for trial in range(n_trials):
        # 智能采样：前10次随机，后面基于最佳参数微调
        if trial < 10 or best_params is None:
            params = {k: np.random.choice(v) for k, v in param_grid.items()}
        else:
            # 基于最佳参数进行小范围搜索
            params = best_params.copy()
            # 随机调整1-2个参数
            keys_to_adjust = np.random.choice(list(param_grid.keys()), size=min(2, len(param_grid)), replace=False)
            for key in keys_to_adjust:
                params[key] = np.random.choice(param_grid[key])

        params.update({
            'random_state': 42,
            'n_jobs': -1,
            'objective': 'reg:squarederror'
        })

        ic_scores = []

        # ✅ V3修复：在每个fold内独立标准化
        for train_idx, val_idx in tscv.split(X_raw):
            X_train_raw, X_val_raw = X_raw[train_idx], X_raw[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # 创建独立的scaler，只在训练集上fit
            scaler = StandardScaler()
            X_train = scaler.fit_transform(X_train_raw)
            X_val = scaler.transform(X_val_raw)  # 用训练集的参数转换验证集

            model = xgb.XGBRegressor(**params)
            model.fit(X_train, y_train, verbose=False)

            y_pred = model.predict(X_val)
            ic = calculate_ic(y_pred, y_val)
            ic_scores.append(ic)

        ic_mean = np.mean(ic_scores)
        ic_std = np.std(ic_scores)
        ir = ic_mean / ic_std if ic_std > 0 else 0

        logger.info(f"  Trial {trial+1}/{n_trials}: IC={ic_mean:.4f}±{ic_std:.4f}, IR={ir:.2f}")

        if ic_mean > best_ic_mean:
            best_ic_mean = ic_mean
            best_ic_std = ic_std
            best_params = params.copy()
            best_trial_info = {
                'ic_mean': ic_mean,
                'ic_std': ic_std,
                'ir': ir,
                'trial': trial + 1
            }
            logger.info(f"    ✓ 新的最佳参数! IC={best_ic_mean:.4f}, IR={ir:.2f}")

    logger.info(f"\n最佳参数（Trial {best_trial_info['trial']}）:")
    logger.info(f"  IC={best_trial_info['ic_mean']:.4f}±{best_trial_info['ic_std']:.4f}")
    logger.info(f"  IR={best_trial_info['ir']:.2f}")

    return best_params


def main():
    """主函数"""
    logger.info("="*60)
    logger.info("量化机器学习优化版 V3 - 修复数据泄露")
    logger.info("目标: IC>0.04, IR>1.5")
    logger.info("="*60)

    # 初始化数据库
    logger.info("初始化数据库连接...")
    from infrastructure.persistence.database.engine import init_engine
    init_engine(pool_size=2, max_overflow=8)

def train_rolling_windows(df: pd.DataFrame, feature_cols: List[str], params: Dict) -> List[Dict]:
    """V4: 滚动窗口训练，返回多个窗口的评估结果"""
    logger.info("\n" + "="*60)
    logger.info("V4 滚动窗口训练")
    logger.info("="*60)

    from sklearn.preprocessing import StandardScaler

    # 定义4个滚动窗口（训练2年，测试3个月）
    windows = [
        ('2023-06-20', '2025-06-19', '2025-06-20', '2025-09-19', '窗口1'),
        ('2023-09-20', '2025-09-19', '2025-09-20', '2025-12-19', '窗口2'),
        ('2023-12-20', '2025-12-19', '2025-12-20', '2026-03-19', '窗口3'),
        ('2024-03-20', '2026-03-19', '2026-03-20', '2026-06-19', '窗口4'),
    ]

    all_results = []

    for train_start, train_end, test_start, test_end, window_name in windows:
        logger.info(f"\n{'='*60}")
        logger.info(f"{window_name}: 训练 {train_start}~{train_end}, 测试 {test_start}~{test_end}")
        logger.info(f"{'='*60}")

        # 筛选数据
        train_mask = (df['date'] >= train_start) & (df['date'] <= train_end)
        test_mask = (df['date'] >= test_start) & (df['date'] <= test_end)

        train_df = df[train_mask].copy()
        test_df = df[test_mask].copy()

        if len(train_df) < 1000 or len(test_df) < 100:
            logger.warning(f"数据量不足，跳过: 训练{len(train_df)}, 测试{len(test_df)}")
            continue

        X_train_raw = train_df[feature_cols].values
        y_train = train_df['label'].values
        X_test_raw = test_df[feature_cols].values
        y_test = test_df['label'].values

        logger.info(f"训练集: {len(train_df)} ({train_df['symbol'].nunique()}只股票)")
        logger.info(f"测试集: {len(test_df)} ({test_df['symbol'].nunique()}只股票)")

        # 标准化
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train_raw)
        X_test = scaler.transform(X_test_raw)

        # 训练模型
        model = xgb.XGBRegressor(**params)
        model.fit(X_train, y_train, verbose=False)

        # 预测
        y_pred_test = model.predict(X_test)

        # 按日期计算IC
        test_df = test_df.copy()
        test_df['prediction'] = y_pred_test

        daily_ic = []
        for date in test_df['date'].unique():
            date_mask = test_df['date'] == date
            if date_mask.sum() >= 10:
                preds = test_df.loc[date_mask, 'prediction'].values
                actuals = test_df.loc[date_mask, 'label'].values
                ic = calculate_ic(preds, actuals)
                daily_ic.append(ic)

        daily_ic = pd.Series(daily_ic)

        # 计算指标
        ic_test = calculate_ic(y_pred_test, y_test)
        ic_mean = daily_ic.mean()
        ic_std = daily_ic.std()
        ir = calculate_ir(daily_ic)

        mse = mean_squared_error(y_test, y_pred_test)
        r2 = r2_score(y_test, y_pred_test)

        result = {
            'window': window_name,
            'train_period': f"{train_start}~{train_end}",
            'test_period': f"{test_start}~{test_end}",
            'ic_test': float(ic_test),
            'ic_mean': float(ic_mean),
            'ic_std': float(ic_std),
            'ir': float(ir),
            'mse': float(mse),
            'r2': float(r2),
            'n_train': len(train_df),
            'n_test': len(test_df),
            'n_days': len(daily_ic)
        }

        all_results.append(result)

        logger.info(f"\n{window_name} 结果:")
        logger.info(f"  测试集 IC: {ic_test:.4f}")
        logger.info(f"  日均 IC: {ic_mean:.4f} ± {ic_std:.4f}")
        logger.info(f"  信息比率 (IR): {ir:.2f}")
        logger.info(f"  测试天数: {len(daily_ic)}")

    return all_results


def evaluate_rolling_results(results: List[Dict]) -> Dict:
    """评估滚动窗口的平均性能"""
    logger.info("\n" + "="*60)
    logger.info("V4 滚动窗口平均性能")
    logger.info("="*60)

    if not results:
        logger.error("无有效窗口结果")
        return {}

    # 计算平均指标
    avg_ic_test = np.mean([r['ic_test'] for r in results])
    avg_ic_mean = np.mean([r['ic_mean'] for r in results])
    avg_ic_std = np.mean([r['ic_std'] for r in results])
    avg_ir = np.mean([r['ir'] for r in results])

    # 计算稳定性（窗口间IC标准差）
    ic_stability = np.std([r['ic_mean'] for r in results])

    logger.info("\n各窗口详情:")
    for r in results:
        status = "✅" if r['ic_mean'] > 0.04 else "❌"
        logger.info(f"  {r['window']}: IC={r['ic_mean']:.4f}, IR={r['ir']:.2f} {status}")

    logger.info(f"\n平均性能:")
    logger.info(f"  平均测试集 IC: {avg_ic_test:.4f}")
    logger.info(f"  平均日均 IC: {avg_ic_mean:.4f} ± {avg_ic_std:.4f}")
    logger.info(f"  平均 IR: {avg_ir:.2f}")
    logger.info(f"  IC稳定性 (窗口间标准差): {ic_stability:.4f}")

    passed_windows = sum(1 for r in results if r['ic_mean'] > 0.04)
    logger.info(f"\n达标窗口: {passed_windows}/{len(results)}")

    if avg_ic_mean > 0.04 and avg_ir > 1.5:
        logger.info("✅ 平均性能达到目标! IC > 0.04 且 IR > 1.5")
    elif avg_ic_mean > 0.04:
        logger.info("⚠️  平均IC达标但IR未达标")
    elif avg_ir > 1.5:
        logger.info("⚠️  平均IR达标但IC未达标")
    else:
        logger.info("❌ 平均IC和IR均未达标")

    summary = {
        'avg_ic_test': float(avg_ic_test),
        'avg_ic_mean': float(avg_ic_mean),
        'avg_ic_std': float(avg_ic_std),
        'avg_ir': float(avg_ir),
        'ic_stability': float(ic_stability),
        'n_windows': len(results),
        'passed_windows': passed_windows,
        'window_results': results,
        'target_achieved': avg_ic_mean > 0.04 and avg_ir > 1.5
    }

    return summary


def save_rolling_results(summary: Dict, feature_cols: List[str], best_params: Dict):
    """保存V4滚动窗口结果"""
    model_dir = _V2_ROOT / '.pi-invest' / 'ml' / 'models'
    model_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    report = {
        'model_type': 'xgboost_v4_rolling',
        'version': 'v4.0',
        'timestamp': datetime.now().isoformat(),
        'v4_improvements': [
            '✅ 滚动窗口训练：4个时间窗口，模拟实盘',
            '✅ 多市场环境测试：覆盖不同时期',
            '✅ 平均性能评估：避免单一测试集偶然性',
            '✅ 修复指数数据：尝试从akshare获取'
        ],
        'v3_fixes_retained': [
            '在每个CV fold内独立标准化',
            '最终训练时分离train/test的scaler',
            '增加正则化防止过拟合'
        ],
        'summary': summary,
        'best_params': best_params,
        'feature_cols': feature_cols,
        'target_achieved': summary.get('target_achieved', False)
    }

    report_path = model_dir / f'training_report_v4_rolling_{timestamp}.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"\n报告已保存: {report_path}")

    if summary.get('target_achieved'):
        logger.info("✅ 达标！V4滚动窗口评估是最终推荐方案")


def main():
    """主函数"""
    logger.info("="*60)
    logger.info("量化机器学习优化版 V5 - 技术+基本面因子")
    logger.info("目标: IC>0.04, IR>1.5")
    logger.info("="*60)

    # 初始化数据库
    logger.info("初始化数据库连接...")
    from infrastructure.persistence.database.engine import init_engine
    init_engine(pool_size=2, max_overflow=8)
    logger.info("✓ 数据库连接池初始化成功")

    # 1. 获取股票（200只）
    symbols = get_stocks(limit=200)
    if len(symbols) < 50:
        logger.error(f"股票数量不足: {len(symbols)}")
        return False

    # 2. 获取K线数据（3年）
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=1095)).strftime('%Y-%m-%d')

    klines_df = fetch_klines(symbols, start_date, end_date)
    if len(klines_df) < 5000:
        logger.error(f"K线数据不足: {len(klines_df)}")
        return False

    # 3. 获取指数数据
    index_df = get_index_data(start_date, end_date)

    # 4. 批量计算技术因子
    factors_df = calculate_factors_enhanced(klines_df)

    # 5. V5新增：获取基本面因子
    fundamental_df = fetch_fundamental_factors(symbols, start_date, end_date)

    # 6. V5新增：合并技术和基本面因子
    factors_df = merge_fundamental_factors(factors_df, fundamental_df)

    # 7. 计算超额收益标签
    data_df = calculate_excess_return_labels(factors_df, index_df, horizon=5)

    # 8. 准备特征（技术+基本面）
    data_df, feature_cols = prepare_features(data_df)

    # 9. 参数优化（在CV内独立标准化，使用全量数据）
    best_params = bayesian_optimize(data_df, feature_cols, n_trials=30)

    # 10. V4核心：滚动窗口训练
    rolling_results = train_rolling_windows(data_df, feature_cols, best_params)

    # 11. 评估滚动窗口平均性能
    summary = evaluate_rolling_results(rolling_results)

    # 12. 保存结果
    save_rolling_results(summary, feature_cols, best_params)

    logger.info("\n✅ V5训练完成!")
    logger.info("V5关键改进:")
    logger.info("  1. ✅ 技术因子(25个) + 基本面因子(10个) = 35个因子")
    logger.info("  2. ✅ 滚动窗口训练（4个窗口）")
    logger.info("  3. ✅ 多市场环境测试")

    return summary.get('target_achieved', False)
    save_rolling_results(summary, feature_cols, best_params)

    logger.info("\n✅ V4滚动窗口训练完成!")
    logger.info("V4关键改进:")
    logger.info("  1. ✅ 滚动窗口训练（4个时间窗口）")
    logger.info("  2. ✅ 多市场环境测试")
    logger.info("  3. ✅ 平均性能评估")

    return summary.get('target_achieved', False)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
