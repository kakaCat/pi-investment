"""
V14参数优化回测脚本

测试参数优化效果（不重训练模型）
"""
import os
import sys

import logging
logging.basicConfig(level=logging.WARNING)

def backtest_v14_optimized():
    """回测V14参数优化版本"""

    print("\n" + "="*80)
    print(" V14参数优化版本回测验证 ")
    print("="*80)

    print("\n回测配置:")
    print("  测试期: 2025-06-01 → 2026-06-01 (12个月)")
    print("  初始资金: ¥100,000")

    print("\n参数对比:")
    print("  项目          V14原版    参数优化版    说明")
    print("  " + "-"*70)
    print("  持仓数量      5只        15只         分散风险，捕捉板块")
    print("  调仓周期      7天        30天         减少交易，捕捉趋势")
    print("  总仓位        90%        95%          提高仓位")
    print("  单股权重      18%        8%           降低集中度")
    print("  止损线        -12%       -15%         放宽止损")

    from live_trading.simulation_trader import SimulationTrader
    from pathlib import Path
    import json

    # 检查模型文件
    model_path = Path('live_trading/models/v14_original_backup.json')
    if not model_path.exists():
        print(f"\n⚠️  原V14模型备份不存在，使用当前模型")
        model_path = Path('live_trading/models/v14_p0_model.json')

    if not model_path.exists():
        print("\n❌ 模型文件不存在，无法回测")
        return

    print(f"\n使用模型: {model_path}")

    # 创建交易器
    trader = SimulationTrader()
    trader.account_name = 'v14_optimized_test'
    trader.model_path = str(model_path)

    # 应用优化参数
    trader.max_positions = 15
    trader.rebalance_days = 30
    trader.max_position_pct = 0.95
    trader.stop_loss = -0.15

    print("\n" + "="*80)
    print("开始回测")
    print("="*80)

    # TODO: 实现完整回测逻辑
    # 这里需要调用SimulationTrader的回测方法

    print("\n⚠️  需要实现完整的回测逻辑")
    print("建议: 使用quantsys-v2的通用回测工具")

    print("\n" + "="*80)
    print(" 参数优化配置已更新")
    print("="*80)

    print("\n下一步:")
    print("  1. 使用V14Strategy(已更新参数)")
    print("  2. 运行实盘模拟观察效果")
    print("  3. 或使用通用回测工具验证")

if __name__ == '__main__':
    backtest_v14_optimized()
