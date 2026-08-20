"""
V14 P0优化版本回测验证

对比V14原版和P0优化版的实际表现
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import json
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

def backtest_v14_p0():
    """回测V14 P0优化版本"""

    print("\n" + "="*80)
    print(" V14 P0优化版本回测验证 ")
    print("="*80)

    print("\n回测配置:")
    print("  测试期: 2025-06-01 → 2026-06-01 (12个月)")
    print("  初始资金: ¥100,000")
    print("  持仓数量: 5只")
    print("  调仓周期: 7天")

    # 加载P0优化模型
    model_path = Path('live_trading/models/v14_p0_model.json')
    if not model_path.exists():
        print("\n❌ P0优化模型不存在")
        return

    print("\n" + "="*80)
    print("加载V14 P0优化模型")
    print("="*80)

    # 读取训练信息
    train_info_path = Path('live_trading/models/v14_p0_train_info.json')
    if train_info_path.exists():
        with open(train_info_path) as f:
            train_info = json.load(f)

        print(f"\n模型信息:")
        print(f"  版本: {train_info['version']}")
        print(f"  训练样本: {train_info['sample_count']:,}条")
        print(f"  有效因子: {train_info['factor_count']}个")
        print(f"  训练时间: {train_info['train_date']}")

        print(f"\n关键改进:")
        for imp in train_info['improvements']:
            print(f"  ✓ {imp}")

    # 执行回测
    print("\n" + "="*80)
    print("执行回测（使用P0优化模型）")
    print("="*80)
    print("⏱️  预计耗时: 2-3分钟...")

    try:
        from live_trading.simulation_trader import SimulationTrader
        from live_trading.risk_control import backtest_with_risk_control

        # 初始化交易器并加载P0模型
        trader = SimulationTrader()

        # 手动加载P0模型
        import xgboost as xgb
        trader.model = xgb.XGBRegressor()
        trader.model.load_model(str(model_path))

        # 加载P0因子列表
        factors_path = Path('live_trading/models/v14_p0_valid_factors.json')
        with open(factors_path) as f:
            trader.valid_factors = json.load(f)

        print(f"✓ P0模型已加载: {len(trader.valid_factors)}个因子")

        # 风控配置
        risk_config = {
            'single_stock_stop_loss': -0.12,
            'portfolio_stop_loss': -0.20,
            'max_position': 0.90,
            'min_position': 0.70,
            'max_single_weight': 0.18,
            'top_n': 5
        }

        # 执行回测
        results = backtest_with_risk_control(
            trader=trader,
            start_date='2025-06-01',
            end_date='2026-06-01',
            risk_config=risk_config
        )

        if not results:
            print("❌ 回测失败")
            return

        # 输出结果
        print("\n" + "="*80)
        print("V14 P0优化版本回测结果")
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

        # 对比V14原版
        print("\n" + "="*80)
        print("V14原版 vs P0优化版对比")
        print("="*80)

        v14_annual = 0.213
        v14_sharpe = 3.43
        v14_drawdown = -0.128

        improvement_annual = (results['annual_return'] / v14_annual - 1) * 100
        improvement_sharpe = (results['sharpe_ratio'] / v14_sharpe - 1) * 100

        print(f"\n{'指标':<20} {'V14原版':>15} {'P0优化版':>15} {'提升':>15}")
        print("-"*80)
        print(f"{'年化收益率':<20} {v14_annual:>14.1%} {results['annual_return']:>14.1%} {improvement_annual:>14.1f}%")
        print(f"{'最大回撤':<20} {v14_drawdown:>14.1%} {results['max_drawdown']:>14.1%} {'改善' if results['max_drawdown'] > v14_drawdown else '恶化':>15}")
        print(f"{'夏普比率':<20} {v14_sharpe:>14.2f} {results['sharpe_ratio']:>14.2f} {improvement_sharpe:>14.1f}%")

        # 评估
        print("\n" + "="*80)
        print("性能评估")
        print("="*80)

        if results['annual_return'] >= 0.28:
            print(f"\n✅ 优秀！年化收益率 {results['annual_return']:.1%} 达到目标（28-32%）")
            print("   建议: 替换V14原版，开始实盘验证")
        elif results['annual_return'] >= 0.25:
            print(f"\n✅ 良好！年化收益率 {results['annual_return']:.1%} 接近目标")
            print("   建议: 替换V14原版，开始实盘验证")
        elif results['annual_return'] >= v14_annual:
            print(f"\n✅ 改善！年化收益率 {results['annual_return']:.1%} 超过V14原版")
            print(f"   提升: +{improvement_annual:.1f}%")
            print("   建议: 替换V14原版，开始实盘验证")
        else:
            print(f"\n⚠️  一般。年化收益率 {results['annual_return']:.1%} 低于V14原版")
            print("   建议: 继续使用V14原版，或执行P2/P3优化")

        # 保存结果
        result_data = {
            'version': 'V14_P0_Optimized',
            'test_date': '2026-07-01',
            'test_period': '2025-06-01 to 2026-06-01',
            'performance': {
                'annual_return': float(results['annual_return']),
                'max_drawdown': float(results['max_drawdown']),
                'sharpe_ratio': float(results['sharpe_ratio']),
                'win_rate': float(results['win_rate'])
            },
            'vs_v14': {
                'v14_annual': 0.213,
                'p0_annual': float(results['annual_return']),
                'improvement': float(improvement_annual)
            }
        }

        result_path = Path('live_trading/v14_p0_backtest_result.json')
        with open(result_path, 'w') as f:
            json.dump(result_data, f, indent=2)

        print(f"\n📁 回测结果已保存: {result_path}")
        print("\n" + "="*80)

    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    backtest_v14_p0()
