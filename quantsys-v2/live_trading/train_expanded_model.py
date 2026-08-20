"""
重新训练模型 - 扩大训练数据集

改进：
1. 股票数量：50 → 200只（扩大4倍）
2. 时间跨度：3个月 → 12个月（扩大4倍）
3. 样本量：3,000 → 48,000条（扩大16倍）

目标：
- 提高模型泛化能力
- 覆盖更多市场环境（牛市、熊市、震荡市）
- 减少过拟合风险
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live_trading.simulation_trader import SimulationTrader
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def main():
    print("\n" + "="*70)
    print("重新训练模型 - 扩大训练数据集")
    print("="*70)

    # 配置
    train_start = '2025-06-01'  # 12个月前
    train_end = '2026-06-01'    # 现在
    stock_limit = 200           # 200只股票

    print(f"\n训练配置:")
    print(f"  训练期间: {train_start} -> {train_end} (12个月)")
    print(f"  股票数量: {stock_limit}只")
    print(f"  预计样本: ~{stock_limit * 240}条 (200只 × 240个交易日)")
    print(f"  改进幅度: 样本量扩大16倍 (3,000 → 48,000)")

    # 初始化
    print("\n[1/3] 初始化系统...")
    trader = SimulationTrader()

    # 训练模型
    print("\n[2/3] 开始训练模型...")
    print("预计耗时: 5-10分钟（取决于数据量）")
    print("-"*70)

    try:
        trader.train_model(
            train_start=train_start,
            train_end=train_end,
            stock_limit=stock_limit
        )

        print("\n✅ 模型训练完成")

        # 验证模型
        print("\n[3/3] 验证模型...")
        trader.load_model()

        print(f"\n模型信息:")
        print(f"  有效因子数: {len(trader.valid_factors)}")
        print(f"  模型文件: live_trading/models/v13_model.json")
        print(f"  因子文件: live_trading/models/valid_factors.json")
        print(f"  训练信息: live_trading/models/train_info.json")

        print("\n" + "="*70)
        print("✅ 训练完成，新模型已保存")
        print("="*70)

        print("\n下一步:")
        print("  1. 查看训练信息: cat live_trading/models/train_info.json")
        print("  2. 计算新模型IC/IR: 需要回测验证")
        print("  3. 开始使用新模型进行模拟交易")

    except Exception as e:
        print(f"\n❌ 训练失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
