#!/usr/bin/env python3
"""
增强版每日报告 - 包含因子分析

在原有报告基础上，添加：
1. 每只股票的关键因子分析
2. 因子贡献排名
3. 异常因子预警
"""

import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

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
        'ATR_Ratio', 'ROC', 'MOM',
        'High_Low_Range', 'Close_Open_Change', 'Volume',
    ]


def analyze_key_factors(
    model,
    factors: dict,
    price: dict,
    top_n: int = 5
) -> List[Dict]:
    """分析关键因子"""
    from scripts.analyze_stock_factors import extract_features

    feature_names = get_feature_names()
    features = extract_features(factors, price)

    # 获取特征重要性
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    else:
        return []

    # 计算贡献
    contributions = features * importances

    # 创建结果
    results = []
    for i, name in enumerate(feature_names):
        results.append({
            'name': name,
            'value': float(features[i]),
            'importance': float(importances[i]),
            'contribution': float(contributions[i])
        })

    # 按贡献排序
    results.sort(key=lambda x: abs(x['contribution']), reverse=True)

    return results[:top_n]


def interpret_factor(name: str, value: float) -> str:
    """解释因子含义"""
    interpretations = {
        'RSI': lambda v: f"RSI={v:.1f} {'超买' if v > 70 else '超卖' if v < 30 else '中性'}",
        'MACD_DIF': lambda v: f"MACD {'金叉' if v > 0 else '死叉'}",
        'MA5/MA20': lambda v: f"短期均线{'向上' if v > 1 else '向下'}",
        'Price/MA5': lambda v: f"价格{'高于' if v > 1 else '低于'}5日线",
        'BB_Position': lambda v: f"布林带位置{v:.1%} {'接近上轨' if v > 0.8 else '接近下轨' if v < 0.2 else '中性'}",
        'Volume_Ratio': lambda v: f"成交量{'放大' if v > 1.2 else '萎缩' if v < 0.8 else '正常'}",
        'KDJ_K': lambda v: f"KDJ_K={v:.1f} {'超买' if v > 80 else '超卖' if v < 20 else ''}",
    }

    if name in interpretations:
        return interpretations[name](value)
    else:
        return f"{name}={value:.2f}"


def generate_enhanced_report(
    signals: List[Dict],
    model,
    db: Database,
    date: str
) -> str:
    """生成增强版报告"""
    report = []
    report.append(f"# 量化系统每日报告（增强版）- {date}\n")

    # 买入信号分析
    buy_signals = [s for s in signals if s.get('action') == 'BUY'][:5]

    if buy_signals:
        report.append("## 📈 Top 5 买入信号（含因子分析）\n")

        for i, signal in enumerate(buy_signals, 1):
            symbol = signal['symbol']
            report.append(f"### {i}. {symbol} - {signal.get('reason', '未知')} (信心度: {signal.get('confidence', 0):.2f})\n")

            # 获取因子和价格
            conn = db._get_connection()
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
                continue

            price = {
                'open': row[0],
                'high': row[1],
                'low': row[2],
                'close': row[3],
                'volume': row[4]
            }

            report.append(f"- **价格**: ¥{price['close']:.2f}\n")

            # 分析关键因子
            key_factors = analyze_key_factors(model, factors, price, top_n=5)

            if key_factors:
                report.append("- **关键因子**:\n")
                for factor in key_factors:
                    direction = "📈" if factor['contribution'] > 0 else "📉"
                    interpretation = interpret_factor(factor['name'], factor['value'])
                    report.append(f"  {direction} {interpretation} (贡献: {factor['contribution']:+.3f})\n")

            report.append("\n")

    # 卖出信号分析
    sell_signals = [s for s in signals if s.get('action') == 'SELL'][:5]

    if sell_signals:
        report.append("## 📉 Top 5 卖出信号（含因子分析）\n")

        for i, signal in enumerate(sell_signals, 1):
            symbol = signal['symbol']
            report.append(f"### {i}. {symbol} - {signal.get('reason', '未知')} (信心度: {signal.get('confidence', 0):.2f})\n")

            # 获取因子和价格
            conn = db._get_connection()
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
                continue

            price = {
                'open': row[0],
                'high': row[1],
                'low': row[2],
                'close': row[3],
                'volume': row[4]
            }

            report.append(f"- **价格**: ¥{price['close']:.2f}\n")

            # 分析关键因子
            key_factors = analyze_key_factors(model, factors, price, top_n=5)

            if key_factors:
                report.append("- **关键因子**:\n")
                for factor in key_factors:
                    direction = "📈" if factor['contribution'] > 0 else "📉"
                    interpretation = interpret_factor(factor['name'], factor['value'])
                    report.append(f"  {direction} {interpretation} (贡献: {factor['contribution']:+.3f})\n")

            report.append("\n")

    report.append(f"\n---\n*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    return ''.join(report)


def main():
    print("=" * 60)
    print("生成增强版每日报告")
    print("=" * 60)

    # 加载信号
    signals_path = Path(__file__).parent.parent / '.pi-invest' / 'signals.json'

    if not signals_path.exists():
        print(f"❌ 信号文件不存在: {signals_path}")
        return

    with open(signals_path, 'r') as f:
        signals = json.load(f)

    print(f"✅ 加载了 {len(signals)} 个信号")

    # 加载模型
    model_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_model.pkl'

    if not model_path.exists():
        print(f"⚠️  模型文件不存在，将生成简化报告")
        model = None
    else:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        print(f"✅ 模型加载成功")

    # 连接数据库
    db_path = Path.home() / '.pi-invest' / 'stock-db' / 'stocks.db'
    db = Database(str(db_path))

    # 获取最新日期
    conn = db._get_connection()
    cursor = conn.execute("SELECT MAX(date) FROM daily_klines")
    date = cursor.fetchone()[0]

    if not date:
        print("❌ 未找到数据")
        return

    print(f"分析日期: {date}")

    # 生成报告
    if model:
        report = generate_enhanced_report(signals, model, db, date)
    else:
        report = "# 简化报告\n\n模型未加载，无法进行因子分析。\n"

    # 保存报告
    output_path = Path(__file__).parent.parent / '.pi-invest' / f'enhanced_report_{date}.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 报告已保存: {output_path}")
    print("\n预览:")
    print("=" * 60)
    print(report[:1000])
    print("...")


if __name__ == '__main__':
    main()
