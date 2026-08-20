"""
V14快速回测工具

用于快速评估V14模型的实际性能：
1. 计算年化收益率
2. 最大回撤
3. 夏普比率
4. 胜率
"""

import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys

from live_trading.simulation_trader import SimulationTrader
import logging

logging.basicConfig(level=logging.WARNING)

def quick_backtest():
    """快速回测V14模型"""

    print("\n" + "="*80)
    print(" V14模型快速回测 ")
    print("="*80)

    print("\n回测配置:")
    print("  测试期: 2025-06-01 → 2026-06-01 (12个月)")
    print("  初始资金: ¥100,000")
    print("  持仓数量: 5只")
    print("  调仓周期: 7天")

    # 风控配置（使用优化后的配置）
    risk_config = {
        'single_stock_stop_loss': -0.12,
        'portfolio_stop_loss': -0.20,
        'max_position': 0.90,
        'min_position': 0.70,
        'max_single_weight': 0.18,
        'top_n': 5
    }

    print("\n风控策略:")
    print(f"  单股止损: {risk_config['single_stock_stop_loss']:.0%}")
    print(f"  组合止损: {risk_config['portfolio_stop_loss']:.0%}")
    print(f"  仓位范围: {risk_config['min_position']:.0%}-{risk_config['max_position']:.0%}")
    print(f"  单股上限: {risk_config['max_single_weight']:.0%}")

    print("\n" + "="*80)
    print("开始回测...")
    print("="*80)

    try:
        # 初始化交易器
        print("\n[1/3] 加载V14模型...")
        trader = SimulationTrader()
        trader.load_model()
        print(f"✓ 模型已加载: {len(trader.valid_factors)}个因子")

        # 执行回测
        print("\n[2/3] 执行回测...")
        from live_trading.risk_control import backtest_with_risk_control

        results = backtest_with_risk_control(
            trader=trader,
            start_date='2025-06-01',
            end_date='2026-06-01',
            risk_config=risk_config
        )

        if not results:
            print("❌ 回测失败，无数据")
            return

        print("\n[3/3] 分析结果...")

        # 输出结果
        print("\n" + "="*80)
        print("回测结果")
        print("="*80)

        print(f"\n💰 收益指标:")
        print(f"  初始资金: ¥{results['initial_capital']:,.2f}")
        print(f"  最终资金: ¥{results['final_value']:,.2f}")
        print(f"  累计收益: {results['cumulative_return']:.2%}")
        print(f"  年化收益: {results['annual_return']:.2%}")

        print(f"\n⚖️  风险指标:")
        print(f"  最大回撤: {results['max_drawdown']:.2%}")
        print(f"  夏普比率: {results['sharpe_ratio']:.4f}")
        print(f"  胜率: {results['win_rate']:.1%}")

        print(f"\n📊 交易统计:")
        print(f"  总交易次数: {results['total_trades']}次")
        print(f"  平均持仓数: {results['avg_position']:.1f}只")

        # 与V13对比
        print("\n" + "="*80)
        print("V13 vs V14 性能对比")
        print("="*80)

        v13_annual = 0.15  # V13基准
        improvement = (results['annual_return'] / v13_annual - 1) * 100

        print(f"\n{'指标':<20} {'V13':>15} {'V14':>15} {'提升':>15}")
        print("-"*80)
        print(f"{'年化收益率':<20} {v13_annual:>14.1%} {results['annual_return']:>14.1%} {improvement:>14.1f}%")
        print(f"{'最大回撤':<20} {'-18%':>15} {results['max_drawdown']:>14.1%} {'改善':>15}")
        print(f"{'夏普比率':<20} {'1.2':>15} {results['sharpe_ratio']:>14.2f} {((results['sharpe_ratio']/1.2-1)*100):>14.1f}%")

        # 评估
        print("\n" + "="*80)
        print("性能评估")
        print("="*80)

        if results['annual_return'] >= 0.28:
            print(f"\n✅ 优秀！年化收益率 {results['annual_return']:.1%} 达到目标（28-32%）")
        elif results['annual_return'] >= 0.20:
            print(f"\n✅ 良好！年化收益率 {results['annual_return']:.1%} 超过V13")
        elif results['annual_return'] >= v13_annual:
            print(f"\n⚠️  一般。年化收益率 {results['annual_return']:.1%} 略高于V13")
        else:
            print(f"\n❌ 不达标。年化收益率 {results['annual_return']:.1%} 低于V13")

        # 建议
        print("\n" + "="*80)
        print("下一步建议")
        print("="*80)

        if results['annual_return'] >= 0.28:
            print("\n✅ V14达到目标，可以开始使用！")
            print("  1. 小资金实盘验证（1-2万）")
            print("  2. 观察2-3个月实际表现")
            print("  3. 验证通过后扩大资金规模")
        elif results['annual_return'] >= 0.20:
            print("\n✅ V14性能良好，可以使用")
            print("  1. 分析因子重要性: python live_trading/analyze_v14_factors.py")
            print("  2. 优化持仓配置（Kelly仓位）")
            print("  3. 小资金实盘测试")
        else:
            print("\n⚠️  V14需要进一步优化")
            print("  1. 检查数据质量")
            print("  2. 调整超参数")
            print("  3. 增加训练样本（扩展到36个月）")

        print("\n" + "="*80)

        # 保存回测结果
        import json
        from pathlib import Path

        backtest_result = {
            'test_date': '2026-07-01',
            'test_period': '2025-06-01 to 2026-06-01',
            'performance': {
                'annual_return': float(results['annual_return']),
                'max_drawdown': float(results['max_drawdown']),
                'sharpe_ratio': float(results['sharpe_ratio']),
                'win_rate': float(results['win_rate'])
            },
            'vs_v13': {
                'v13_annual': 0.15,
                'v14_annual': float(results['annual_return']),
                'improvement': float(improvement)
            }
        }

        result_path = Path('live_trading/v14_backtest_result.json')
        with open(result_path, 'w') as f:
            json.dump(backtest_result, f, indent=2)

        print(f"\n📁 回测结果已保存: {result_path}")

    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    quick_backtest()
