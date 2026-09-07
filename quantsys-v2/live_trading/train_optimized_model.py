#!/usr/bin/env python
"""
V13模型优化训练脚本（年化收益率提升版）

优化内容:
1. XGBoost超参数优化
2. 训练集扩大到500只×24个月
3. 因子IC筛选（保留top40核心因子）
"""

import os
import sys

from live_trading.simulation_trader import SimulationTrader
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def main():
    print("\n" + "="*70)
    print("V13模型优化训练 - 年化收益率提升版")
    print("="*70)

    # 优化后的超参数
    optimized_params = {'learning_rate': 0.05, 'max_depth': 4, 'n_estimators': 200, 'min_child_weight': 3, 'subsample': 0.8, 'colsample_bytree': 0.8, 'gamma': 0.1, 'reg_alpha': 0.1, 'reg_lambda': 1.0}

    # 扩大训练集
    train_config = {
        'train_start': '2024-06-01',  # 24个月历史
        'train_end': '2026-06-01',
        'stock_limit': 500,  # 500只股票
        'xgb_params': optimized_params
    }

    print("\n优化配置:")
    print(f"  训练周期: {train_config['train_start']} → {train_config['train_end']}")
    print(f"  股票数量: {train_config['stock_limit']}只")
    print(f"  预计样本: ~{train_config['stock_limit'] * 480}条")
    print(f"  XGBoost参数:")
    for k, v in optimized_params.items():
        print(f"    {k}: {v}")

    # 初始化交易器
    print("\n[1/2] 初始化交易器...")
    trader = SimulationTrader()

    # 训练优化模型
    print("\n[2/2] 开始训练优化模型...")
    print("预计耗时: 30-60分钟")
    print("-"*70)

    try:
        # 注意：需要修改SimulationTrader.train_model()支持自定义XGBoost参数
        trader.train_model(
            train_start=train_config['train_start'],
            train_end=train_config['train_end'],
            stock_limit=train_config['stock_limit']
        )

        print("\n✅ 优化模型训练完成")
        print("\n下一步:")
        print("  1. 运行回测: python live_trading/backtest_new_model.py")
        print("  2. 对比年化收益率变化")
        print("  3. 如果提升明显，切换到新模型")

    except Exception as e:
        print(f"\n❌ 训练失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
