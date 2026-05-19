#!/usr/bin/env python3
"""
分析单只股票的因子贡献

使用SHAP值分析每个因子对预测结果的具体贡献

使用方法：
python scripts/analyze_stock_factors.py 000001
python scripts/analyze_stock_factors.py 600036 2026-05-18
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database


def get_feature_names():
    """获取特征名称"""
    return [
        'RSI', 'MACD_DIF', 'MACD_DEA', 'MACD_HIST',
        'KDJ_K', 'KDJ_D', 'KDJ_J', 'CCI', 'WilliamsR',
        'MA5/MA20', 'MA10/MA20', 'MA20/MA60', 'Price/MA5', 'Price/MA20',
        'BB_Position', 'BB_Width',
        'Volume_Ratio', 'OBV', 'MFI',
        'ATR_Ratio',
        'ROC', 'MOM',
        'High_Low_Range', 'Close_Open_Change', 'Volume',
    ]


def extract_features(factors: dict, price: dict) -> np.ndarray:
    """提取特征（与ml_predict.py保持一致）"""
    # 技术因子 - 使用数据库中的实际因子名称
    rsi = factors.get('RSI12', 50)
    macd_dif = factors.get('MACD_macd_dif', 0)
    macd_dea = factors.get('MACD_macd_dea', 0)
    macd_hist = factors.get('MACD_macd_histogram', 0)
    kdj_k = factors.get('KDJ_k', 50)
    kdj_d = factors.get('KDJ_d', 50)
    kdj_j = factors.get('KDJ_j', 50)
    cci = factors.get('CCI14', 0)
    wr = factors.get('WR10', -50)

    # 价格特征
    ma5 = factors.get('MA5', price['close'])
    ma10 = factors.get('MA10', price['close'])
    ma20 = factors.get('MA20', price['close'])
    ma60 = factors.get('MA60', price['close'])
    close = price['close']

    # 安全的除法操作，处理 None 值
    ma5_ma20_ratio = ma5 / ma20 if (ma5 is not None and ma20 is not None and ma20 > 0) else 1.0
    ma10_ma20_ratio = ma10 / ma20 if (ma10 is not None and ma20 is not None and ma20 > 0) else 1.0
    ma20_ma60_ratio = ma20 / ma60 if (ma20 is not None and ma60 is not None and ma60 > 0) else 1.0
    price_ma5_ratio = close / ma5 if (ma5 is not None and ma5 > 0) else 1.0
    price_ma20_ratio = close / ma20 if (ma20 is not None and ma20 > 0) else 1.0

    bb_upper = factors.get('BOLL_bb_upper', close * 1.02)
    bb_middle = factors.get('BOLL_bb_middle', close)
    bb_lower = factors.get('BOLL_bb_lower', close * 0.98)

    bb_width = (bb_upper - bb_lower) / bb_middle if (bb_middle is not None and bb_middle > 0) else 0.04
    bb_position = (close - bb_lower) / (bb_upper - bb_lower) if (bb_upper is not None and bb_lower is not None and bb_upper > bb_lower) else 0.5

    volume_ratio = factors.get('VR', 1.0)
    obv = factors.get('OBV', 0)
    mfi = factors.get('MFI14', 50)

    atr = factors.get('ATR14', 0)
    atr_ratio = atr / close if (atr is not None and close is not None and close > 0) else 0

    roc = factors.get('ROC12', 0)
    mom = factors.get('MOM12', 0)

    # 安全处理所有可能为 None 的值
    obv_val = obv / 1e8 if obv is not None else 0
    volume_val = price['volume'] / 1e8 if price.get('volume') is not None else 0

    high_low_range = (price['high'] - price['low']) / price['close'] if (
        price.get('high') is not None and price.get('low') is not None and
        price.get('close') is not None and price['close'] > 0
    ) else 0

    close_open_change = (price['close'] - price['open']) / price['open'] if (
        price.get('close') is not None and price.get('open') is not None and price['open'] > 0
    ) else 0

    features = np.array([
        rsi, macd_dif, macd_dea, macd_hist,
        kdj_k, kdj_d, kdj_j, cci, wr,
        ma5_ma20_ratio, ma10_ma20_ratio, ma20_ma60_ratio,
        price_ma5_ratio, price_ma20_ratio,
        bb_position, bb_width,
        volume_ratio if volume_ratio is not None else 1.0,
        obv_val,
        mfi if mfi is not None else 50,
        atr_ratio,
        roc if roc is not None else 0,
        mom if mom is not None else 0,
        high_low_range,
        close_open_change,
        volume_val,
    ])

    return features


def analyze_with_shap(model, features: np.ndarray, feature_names: list):
    """使用SHAP分析因子贡献"""
    try:
        import shap

        # 创建SHAP解释器
        explainer = shap.TreeExplainer(model)

        # 计算SHAP值
        shap_values = explainer.shap_values(features.reshape(1, -1))

        # 如果是二分类，取正类的SHAP值
        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        # 创建DataFrame
        df = pd.DataFrame({
            'Feature': feature_names,
            'Value': features,
            'SHAP': shap_values[0],
            'Abs_SHAP': np.abs(shap_values[0])
        })

        # 排序
        df = df.sort_values('Abs_SHAP', ascending=False)

        return df, explainer.expected_value

    except ImportError:
        print("⚠️  SHAP库未安装，使用简化分析")
        print("   安装命令: pip install shap")
        return None, None


def analyze_without_shap(model, features: np.ndarray, feature_names: list):
    """不使用SHAP的简化分析"""
    # 获取特征重要性
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    else:
        print("❌ 模型不支持特征重要性分析")
        return None

    # 计算加权贡献
    contributions = features * importances

    df = pd.DataFrame({
        'Feature': feature_names,
        'Value': features,
        'Importance': importances,
        'Contribution': contributions,
        'Abs_Contribution': np.abs(contributions)
    })

    df = df.sort_values('Abs_Contribution', ascending=False)

    return df


def main():
    if len(sys.argv) < 2:
        print("使用方法: python analyze_stock_factors.py <股票代码> [日期]")
        print("示例: python analyze_stock_factors.py 000001")
        print("示例: python analyze_stock_factors.py 600036 2026-05-18")
        return

    symbol = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else None

    print("=" * 60)
    print(f"分析股票: {symbol}")
    print("=" * 60)

    # 加载模型
    model_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_model.pkl'

    if not model_path.exists():
        print(f"❌ 模型文件不存在: {model_path}")
        return

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    print(f"✅ 模型加载成功")

    # 连接数据库
    db_path = Path.home() / '.pi-invest' / 'stock-db' / 'stocks.db'
    db = Database(str(db_path))
    conn = db._get_connection()

    # 获取最新日期
    if date is None:
        cursor = conn.execute("SELECT MAX(date) FROM factor_values WHERE symbol = ?", (symbol,))
        date = cursor.fetchone()[0]
        if not date:
            print(f"❌ 未找到股票 {symbol} 的数据")
            return

    print(f"分析日期: {date}")

    # 获取因子和价格
    cursor = conn.execute("""
        SELECT factor_name, factor_value
        FROM factor_values
        WHERE symbol = ? AND date = ?
    """, (symbol, date))

    factors = {}
    for row in cursor.fetchall():
        factors[row[0]] = row[1]

    cursor = conn.execute("""
        SELECT open, high, low, close, volume
        FROM daily_klines
        WHERE symbol = ? AND date = ?
    """, (symbol, date))

    row = cursor.fetchone()
    if not row:
        print(f"❌ 未找到价格数据")
        return

    price = {
        'open': row[0],
        'high': row[1],
        'low': row[2],
        'close': row[3],
        'volume': row[4]
    }

    print(f"当前价格: ¥{price['close']:.2f}")

    # 提取特征
    feature_names = get_feature_names()
    features = extract_features(factors, price)

    # 预测
    X = features.reshape(1, -1)
    if hasattr(model, 'predict_proba'):
        proba = model.predict_proba(X)[0]
        up_prob = proba[1]
    else:
        up_prob = model.predict(X)[0]

    print(f"预测上涨概率: {up_prob:.2%}")
    print()

    # 分析因子贡献
    print("=" * 60)
    print("因子贡献分析")
    print("=" * 60)

    # 尝试使用SHAP
    df, base_value = analyze_with_shap(model, features, feature_names)

    if df is None:
        # 使用简化分析
        df = analyze_without_shap(model, features, feature_names)
        if df is None:
            return

        print("\n🏆 Top 10 贡献最大的因子:")
        print("-" * 60)
        for i, (idx, row) in enumerate(df.head(10).iterrows(), 1):
            direction = "📈" if row['Contribution'] > 0 else "📉"
            print(f"{i:2d}. {direction} {row['Feature']:20s} | "
                  f"值: {row['Value']:8.4f} | "
                  f"贡献: {row['Contribution']:+8.4f}")
    else:
        print(f"\n基准预测值: {base_value:.4f}")
        print(f"实际预测值: {up_prob:.4f}")
        print(f"因子总贡献: {df['SHAP'].sum():.4f}")

        print("\n🏆 Top 10 贡献最大的因子:")
        print("-" * 60)
        for i, (idx, row) in enumerate(df.head(10).iterrows(), 1):
            direction = "📈" if row['SHAP'] > 0 else "📉"
            print(f"{i:2d}. {direction} {row['Feature']:20s} | "
                  f"值: {row['Value']:8.4f} | "
                  f"SHAP: {row['SHAP']:+8.4f}")

    # 保存结果
    output_dir = Path(__file__).parent.parent / '.pi-invest'
    output_path = output_dir / f'factor_analysis_{symbol}_{date}.csv'
    df.to_csv(output_path, index=False)
    print(f"\n📄 详细分析已保存: {output_path}")


if __name__ == '__main__':
    main()
