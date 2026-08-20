"""
验证新模型的IC/IR指标

计算：
1. IC (Information Coefficient): 预测值与实际收益的Spearman相关系数
2. ICIR (IC Information Ratio): IC的均值/标准差
3. 传统IR (Information Ratio): 年化超额收益/跟踪误差

目标：IC > 0.4
"""

import os
import sys

from live_trading.simulation_trader import SimulationTrader
import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def validate_model_ic():
    """验证模型IC指标"""

    print("\n" + "="*70)
    print("新模型IC/IR验证")
    print("="*70)

    # 初始化
    trader = SimulationTrader()
    trader.load_model()

    print(f"\n模型信息:")
    print(f"  有效因子: {len(trader.valid_factors)}个")

    # 使用训练期数据验证（因为训练期是2025-06到2026-06）
    test_start = '2025-09-01'  # 训练期内的后半段
    test_end = '2026-06-01'

    print(f"\n验证期间: {test_start} -> {test_end} (训练期内验证)")
    print("获取测试数据...")

    # 获取测试股票池
    stocks = trader._get_stock_pool(limit=100)  # 使用100只验证
    print(f"测试股票: {len(stocks)}只")

    # 获取测试数据
    test_data = trader._get_historical_data(stocks, test_start, test_end)
    if test_data.empty:
        print("❌ 测试数据为空")
        return

    print(f"测试样本: {len(test_data)}条")

    # 计算因子
    print("计算因子...")
    test_data = trader.factor_calc.calculate_factors(test_data)

    # 计算标签（未来5日收益）
    test_data = test_data.sort_values(['symbol', 'date'])
    test_data['label'] = test_data.groupby('symbol')['close'].transform(
        lambda x: x.pct_change(5).shift(-5)
    )

    # 模型预测
    print("模型预测...")
    test_clean = test_data.dropna(subset=['label'] + trader.valid_factors)

    if len(test_clean) == 0:
        print("❌ 清洗后数据为空")
        return

    X_test = test_clean[trader.valid_factors]
    y_test = test_clean['label']
    predictions = trader.model.predict(X_test)

    test_clean['prediction'] = predictions

    # 计算IC（按日期分组）
    print("\n计算IC指标...")
    daily_ic = []

    for date, group in test_clean.groupby('date'):
        if len(group) < 10:  # 至少10只股票
            continue
        ic = group['prediction'].corr(group['label'], method='spearman')
        if not np.isnan(ic):
            daily_ic.append(ic)

    if len(daily_ic) == 0:
        print("❌ 无法计算IC")
        return

    # 计算指标
    ic_mean = np.mean(daily_ic)
    ic_std = np.std(daily_ic)
    icir = ic_mean / ic_std if ic_std > 0 else 0

    # 整体IC
    overall_ic = test_clean['prediction'].corr(test_clean['label'], method='spearman')

    print("\n" + "="*70)
    print("验证结果")
    print("="*70)
    print(f"\n📊 IC指标:")
    print(f"  整体IC: {overall_ic:.4f}")
    print(f"  日均IC: {ic_mean:.4f}")
    print(f"  IC标准差: {ic_std:.4f}")
    print(f"  ICIR: {icir:.4f}")
    print(f"  IC>0天数: {sum(1 for ic in daily_ic if ic > 0)}/{len(daily_ic)} ({sum(1 for ic in daily_ic if ic > 0)/len(daily_ic)*100:.1f}%)")

    print(f"\n评估:")
    if overall_ic >= 0.4:
        print(f"  ✅ IC={overall_ic:.4f} >= 0.4 (优秀)")
    elif overall_ic >= 0.3:
        print(f"  ✅ IC={overall_ic:.4f} >= 0.3 (良好)")
    elif overall_ic >= 0.2:
        print(f"  ⚠️  IC={overall_ic:.4f} >= 0.2 (一般)")
    else:
        print(f"  ❌ IC={overall_ic:.4f} < 0.2 (不合格)")

    if icir >= 1.5:
        print(f"  ✅ ICIR={icir:.4f} >= 1.5 (稳定)")
    elif icir >= 1.0:
        print(f"  ⚠️  ICIR={icir:.4f} >= 1.0 (可接受)")
    else:
        print(f"  ❌ ICIR={icir:.4f} < 1.0 (不稳定)")

    print("\n" + "="*70)

    # 如果IC不达标
    if overall_ic < 0.4:
        print("\n⚠️  IC未达到0.4目标")
        print("可能原因:")
        print("  1. 测试期市场环境与训练期差异大")
        print("  2. 因子数量太少（31个），需要更多因子")
        print("  3. 模型参数需要调优")
        print("\n建议:")
        print("  1. 降低IC筛选阈值（0.02 → 0.01），保留更多因子")
        print("  2. 使用更长的训练期（12个月 → 24个月）")
        print("  3. 调整XGBoost超参数")

if __name__ == '__main__':
    validate_model_ic()
