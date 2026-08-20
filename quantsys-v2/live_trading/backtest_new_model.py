"""
新模型回测 - 计算年化收益

使用新模型(68因子, IC=0.5465)进行回测
计算年化收益、最大回撤、夏普比率
"""

import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys

from live_trading.simulation_trader import SimulationTrader
from live_trading.risk_control import backtest_with_risk_control
import logging

logging.basicConfig(level=logging.WARNING)

# 回测配置
config = {
    'single_stock_stop_loss': -0.15,    # -15% 单股止损
    'portfolio_stop_loss': -0.20,        # -20% 组合止损
    'max_position': 0.85,                # 最大仓位85%
    'min_position': 0.70,                # 最小仓位70%
    'max_single_weight': 0.15,           # 单股最大15%
    'top_n': 8                           # 持仓8只
}

print("\n" + "="*70)
print("新模型回测 (68因子, IC=0.5465)")
print("="*70)

print(f"\n回测配置:")
print(f"  测试期: 2025-06-01 → 2026-06-01 (12个月)")
print(f"  初始资金: ¥100,000")
print(f"  风控策略:")
print(f"    - 单股止损: {config['single_stock_stop_loss']:.0%}")
print(f"    - 组合止损: {config['portfolio_stop_loss']:.0%}")
print(f"    - 仓位范围: {config['min_position']:.0%}-{config['max_position']:.0%}")
print(f"    - 持仓数量: {config['top_n']}只")
print(f"    - 单股上限: {config['max_single_weight']:.0%}")

print("\n初始化交易器...")
trader = SimulationTrader()
trader.load_model()
print(f"模型已加载: {len(trader.valid_factors)}个因子")

print("\n开始回测...")
print("="*70)

# 执行回测
results = backtest_with_risk_control(
    trader=trader,
    start_date='2025-06-01',
    end_date='2026-06-01',
    risk_config=config
)

print("\n" + "="*70)
print("回测结果")
print("="*70)

if not results:
    print("❌ 回测失败，无数据")
    exit(1)

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

print("\n" + "="*70)
print("评估")
print("="*70)

# 评估年化收益
if results['annual_return'] >= 0.3:
    print(f"✅ 年化收益 {results['annual_return']:.2%} >= 30% (优秀)")
elif results['annual_return'] >= 0.2:
    print(f"✅ 年化收益 {results['annual_return']:.2%} >= 20% (良好)")
elif results['annual_return'] >= 0.1:
    print(f"⚠️  年化收益 {results['annual_return']:.2%} >= 10% (一般)")
else:
    print(f"❌ 年化收益 {results['annual_return']:.2%} < 10% (不达标)")

# 评估回撤
if results['max_drawdown'] >= -0.20:
    print(f"✅ 最大回撤 {results['max_drawdown']:.2%} >= -20% (达标)")
else:
    print(f"❌ 最大回撤 {results['max_drawdown']:.2%} < -20% (超标)")

# 评估夏普
if results['sharpe_ratio'] >= 2.0:
    print(f"✅ 夏普比率 {results['sharpe_ratio']:.2f} >= 2.0 (优秀)")
elif results['sharpe_ratio'] >= 1.0:
    print(f"✅ 夏普比率 {results['sharpe_ratio']:.2f} >= 1.0 (良好)")
else:
    print(f"⚠️  夏普比率 {results['sharpe_ratio']:.2f} < 1.0 (一般)")

print("="*70)
