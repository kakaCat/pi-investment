"""
股指期货对冲完整示例

演示如何使用股指期货对冲股票组合的系统性风险：
1. Beta计算
2. 静态对冲策略
3. 动态对冲策略
4. 最小方差对冲
5. 对冲效果评估
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from domain.quantlib.cross_asset_strategies.index_futures_hedge import (
    BetaCalculator,
    IndexFuturesHedgeStrategy,
    DynamicHedgeStrategy,
    MinimumVarianceHedgeStrategy
)


def prepare_sample_data():
    """准备示例数据"""
    print("=" * 60)
    print("步骤1: 准备数据")
    print("=" * 60)

    np.random.seed(42)
    n_days = 252  # 一年交易日

    # 生成指数收益（市场收益）
    index_returns = np.random.randn(n_days) * 0.015

    # 生成组合收益（包含Alpha和Beta）
    alpha = 0.0005  # 日Alpha
    beta = 1.2  # Beta系数
    idiosyncratic = np.random.randn(n_days) * 0.01  # 特质风险

    portfolio_returns = alpha + beta * index_returns + idiosyncratic

    print(f"\n数据统计:")
    print(f"  交易日数: {n_days}")
    print(f"  真实Beta: {beta}")
    print(f"  日Alpha: {alpha:.4f}")
    print(f"\n指数收益:")
    print(f"  均值: {index_returns.mean():.4f}")
    print(f"  标准差: {index_returns.std():.4f}")
    print(f"  年化波动率: {index_returns.std() * np.sqrt(252):.2%}")
    print(f"\n组合收益:")
    print(f"  均值: {portfolio_returns.mean():.4f}")
    print(f"  标准差: {portfolio_returns.std():.4f}")
    print(f"  年化波动率: {portfolio_returns.std() * np.sqrt(252):.2%}")

    return portfolio_returns, index_returns


def beta_calculation_demo(portfolio_returns, index_returns):
    """Beta计算演示"""
    print("\n" + "=" * 60)
    print("步骤2: Beta计算")
    print("=" * 60)

    calculator = BetaCalculator(lookback_period=60)

    # 计算Beta
    beta = calculator.calculate_beta(portfolio_returns, index_returns)
    print(f"\nBeta计算结果: {beta:.4f}")

    # 验证Beta计算
    # Beta = Cov(portfolio, index) / Var(index)
    covariance = np.cov(portfolio_returns, index_returns)[0, 1]
    variance = np.var(index_returns)
    beta_manual = covariance / variance

    print(f"手动计算验证: {beta_manual:.4f}")
    print(f"差异: {abs(beta - beta_manual):.6f}")

    # 计算滚动Beta
    print("\n计算滚动Beta (60日窗口):")
    portfolio_series = pd.Series(portfolio_returns)
    index_series = pd.Series(index_returns)

    rolling_beta = calculator.calculate_rolling_beta(
        portfolio_series,
        index_series,
        window=60
    )

    print(f"  滚动Beta形状: {rolling_beta.shape}")
    print(f"  最近10天Beta:")
    print(rolling_beta.tail(10).to_string())

    # Beta统计
    valid_beta = rolling_beta.dropna()
    print(f"\n滚动Beta统计:")
    print(f"  均值: {valid_beta.mean():.4f}")
    print(f"  标准差: {valid_beta.std():.4f}")
    print(f"  最小值: {valid_beta.min():.4f}")
    print(f"  最大值: {valid_beta.max():.4f}")

    return beta, rolling_beta


def static_hedge_demo(portfolio_returns, index_returns):
    """静态对冲策略演示"""
    print("\n" + "=" * 60)
    print("步骤3: 静态对冲策略")
    print("=" * 60)

    print("\n策略说明:")
    print("  - 计算组合Beta")
    print("  - 使用固定对冲比率")
    print("  - 定期再平衡")

    # 创建策略
    strategy = IndexFuturesHedgeStrategy(
        portfolio_value=10_000_000,  # 1000万组合
        futures_multiplier=300,       # 沪深300期货合约乘数
        hedge_ratio=1.0,              # 完全对冲
        rebalance_threshold=0.1,      # 10%再平衡阈值
        lookback_period=60
    )

    print(f"\n策略参数:")
    print(f"  组合价值: {strategy.portfolio_value:,.0f}")
    print(f"  期货乘数: {strategy.futures_multiplier}")
    print(f"  对冲比率: {strategy.hedge_ratio}")
    print(f"  再平衡阈值: {strategy.rebalance_threshold:.1%}")

    # 更新Beta
    strategy.update_beta(portfolio_returns, index_returns)
    print(f"\n计算的Beta: {strategy.current_beta:.4f}")

    # 计算对冲头寸
    futures_price = 4000  # 假设期货价格
    hedge_position = strategy.calculate_hedge_position(
        portfolio_value=10_000_000,
        beta=strategy.current_beta,
        futures_price=futures_price
    )

    print(f"\n对冲头寸计算:")
    print(f"  期货价格: {futures_price}")
    print(f"  对冲手数: {hedge_position} 手")
    print(f"  对冲名义价值: {abs(hedge_position) * futures_price * strategy.futures_multiplier:,.0f}")

    # 生成再平衡信号
    signal = strategy.generate_rebalance_signal(
        portfolio_value=10_000_000,
        futures_price=futures_price
    )

    if signal:
        print(f"\n再平衡信号:")
        print(f"  当前持仓: {signal['current_position']} 手")
        print(f"  目标持仓: {signal['target_position']} 手")
        print(f"  调整数量: {signal['adjustment']} 手")
        print(f"  Beta: {signal['beta']:.4f}")

        # 执行再平衡
        strategy.on_rebalance(signal['target_position'])
        print(f"\n再平衡已执行，新持仓: {strategy.futures_position} 手")
    else:
        print("\n无需再平衡")

    return strategy


def dynamic_hedge_demo(portfolio_returns, index_returns):
    """动态对冲策略演示"""
    print("\n" + "=" * 60)
    print("步骤4: 动态对冲策略")
    print("=" * 60)

    print("\n策略说明:")
    print("  - 根据市场状况动态调整对冲比率")
    print("  - 考虑市场波动率")
    print("  - 考虑组合与指数的相关性")

    # 创建动态对冲策略
    strategy = DynamicHedgeStrategy(
        portfolio_value=10_000_000,
        futures_multiplier=300,
        min_hedge_ratio=0.5,
        max_hedge_ratio=1.0,
        rebalance_threshold=0.1
    )

    print(f"\n策略参数:")
    print(f"  最小对冲比率: {strategy.min_hedge_ratio}")
    print(f"  最大对冲比率: {strategy.max_hedge_ratio}")

    # 计算市场状况
    market_volatility = index_returns.std() * np.sqrt(252)
    portfolio_volatility = portfolio_returns.std() * np.sqrt(252)
    correlation = np.corrcoef(portfolio_returns, index_returns)[0, 1]

    print(f"\n市场状况:")
    print(f"  市场波动率: {market_volatility:.2%}")
    print(f"  组合波动率: {portfolio_volatility:.2%}")
    print(f"  相关系数: {correlation:.4f}")

    # 调整对冲比率
    strategy.adjust_hedge_ratio(
        market_volatility=market_volatility,
        portfolio_volatility=portfolio_volatility,
        correlation=correlation
    )

    print(f"\n调整后的对冲比率: {strategy.hedge_ratio:.2f}")

    # 不同市场状况下的对冲比率
    print("\n不同市场状况下的对冲比率:")
    print("市场波动率  相关系数  对冲比率")
    print("-" * 40)

    scenarios = [
        (0.15, 0.9),  # 低波动，高相关
        (0.20, 0.8),  # 中波动，高相关
        (0.30, 0.7),  # 高波动，中相关
        (0.40, 0.6),  # 极高波动，中相关
    ]

    for vol, corr in scenarios:
        test_strategy = DynamicHedgeStrategy(
            portfolio_value=10_000_000,
            futures_multiplier=300,
            min_hedge_ratio=0.5,
            max_hedge_ratio=1.0
        )
        test_strategy.adjust_hedge_ratio(vol, portfolio_volatility, corr)
        print(f"{vol:>10.1%}  {corr:>8.2f}  {test_strategy.hedge_ratio:>8.2f}")

    return strategy


def minimum_variance_hedge_demo(portfolio_returns, index_returns):
    """最小方差对冲演示"""
    print("\n" + "=" * 60)
    print("步骤5: 最小方差对冲")
    print("=" * 60)

    print("\n策略说明:")
    print("  - 通过优化找到最小化组合波动率的对冲比率")
    print("  - 最小方差对冲比率 = Cov(portfolio, futures) / Var(futures)")

    # 创建最小方差对冲策略
    strategy = MinimumVarianceHedgeStrategy(
        portfolio_value=10_000_000,
        futures_multiplier=300
    )

    # 模拟期货收益（与指数高度相关）
    futures_returns = index_returns + np.random.randn(len(index_returns)) * 0.002

    # 计算最优对冲比率
    optimal_ratio = strategy.calculate_optimal_hedge_ratio(
        portfolio_returns,
        futures_returns
    )

    print(f"\n最优对冲比率: {optimal_ratio:.4f}")

    # 更新策略
    strategy.update_hedge_ratio(portfolio_returns, futures_returns)
    print(f"策略对冲比率: {strategy.hedge_ratio:.4f}")

    # 对比不同对冲比率的效果
    print("\n不同对冲比率的组合波动率:")
    print("对冲比率  组合波动率")
    print("-" * 30)

    hedge_ratios = [0.0, 0.5, optimal_ratio, 1.0, 1.5]
    for ratio in hedge_ratios:
        # 计算对冲后的收益
        hedged_returns = portfolio_returns + ratio * futures_returns
        hedged_vol = hedged_returns.std() * np.sqrt(252)
        print(f"{ratio:>6.2f}    {hedged_vol:>10.2%}")

    return strategy, futures_returns


def hedge_effectiveness_evaluation(portfolio_returns, index_returns, futures_returns):
    """对冲效果评估"""
    print("\n" + "=" * 60)
    print("步骤6: 对冲效果评估")
    print("=" * 60)

    # 创建策略
    strategy = IndexFuturesHedgeStrategy(
        portfolio_value=10_000_000,
        futures_multiplier=300,
        hedge_ratio=1.0
    )

    # 更新Beta
    strategy.update_beta(portfolio_returns, index_returns)

    # 计算期货持仓
    futures_price = 4000
    futures_position = strategy.calculate_hedge_position(
        10_000_000,
        strategy.current_beta,
        futures_price
    )
    strategy.futures_position = futures_position

    # 转换为Series
    portfolio_series = pd.Series(portfolio_returns)
    index_series = pd.Series(index_returns)
    futures_series = pd.Series(futures_returns)

    # 计算对冲效果
    effectiveness = strategy.calculate_hedge_effectiveness(
        portfolio_series,
        index_series,
        futures_series
    )

    print("\n对冲效果指标:")
    print(f"  未对冲波动率: {effectiveness['unhedged_volatility']:.2%}")
    print(f"  对冲后波动率: {effectiveness['hedged_volatility']:.2%}")
    print(f"  波动率降低: {effectiveness['volatility_reduction']:.2%}")
    print(f"\n  未对冲Beta: {effectiveness['unhedged_beta']:.4f}")
    print(f"  对冲后Beta: {effectiveness['hedged_beta']:.4f}")
    print(f"  Beta降低: {effectiveness['beta_reduction']:.2%}")

    # 累积收益对比
    print("\n累积收益对比:")
    unhedged_cumret = (1 + portfolio_series).cumprod() - 1
    hedged_returns = portfolio_series + futures_series * abs(futures_position) * strategy.futures_multiplier / strategy.portfolio_value
    hedged_cumret = (1 + hedged_returns).cumprod() - 1

    print(f"  未对冲累积收益: {unhedged_cumret.iloc[-1]:.2%}")
    print(f"  对冲后累积收益: {hedged_cumret.iloc[-1]:.2%}")

    # 风险调整收益
    unhedged_sharpe = portfolio_series.mean() / portfolio_series.std() * np.sqrt(252)
    hedged_sharpe = hedged_returns.mean() / hedged_returns.std() * np.sqrt(252)

    print(f"\n风险调整收益:")
    print(f"  未对冲Sharpe: {unhedged_sharpe:.4f}")
    print(f"  对冲后Sharpe: {hedged_sharpe:.4f}")

    # 最大回撤
    unhedged_drawdown = (unhedged_cumret - unhedged_cumret.cummax()).min()
    hedged_drawdown = (hedged_cumret - hedged_cumret.cummax()).min()

    print(f"\n最大回撤:")
    print(f"  未对冲: {unhedged_drawdown:.2%}")
    print(f"  对冲后: {hedged_drawdown:.2%}")


def practical_example():
    """实际应用示例"""
    print("\n" + "=" * 60)
    print("实际应用示例")
    print("=" * 60)

    print("\n场景: 持有科技股组合，担心市场下跌")
    print("目标: 保留Alpha收益，对冲Beta风险")

    # 模拟科技股组合（高Beta）
    np.random.seed(42)
    n_days = 252

    index_returns = np.random.randn(n_days) * 0.015
    alpha = 0.001  # 日Alpha 0.1%
    beta = 1.5  # 高Beta
    portfolio_returns = alpha + beta * index_returns + np.random.randn(n_days) * 0.02

    print(f"\n组合特征:")
    print(f"  Beta: {beta}")
    print(f"  日Alpha: {alpha:.2%}")
    print(f"  年化Alpha: {alpha * 252:.2%}")

    # 创建对冲策略
    strategy = IndexFuturesHedgeStrategy(
        portfolio_value=50_000_000,  # 5000万组合
        futures_multiplier=300,
        hedge_ratio=0.8,  # 80%对冲
        rebalance_threshold=0.15
    )

    strategy.update_beta(portfolio_returns, index_returns)

    print(f"\n对冲方案:")
    print(f"  计算Beta: {strategy.current_beta:.4f}")
    print(f"  对冲比率: {strategy.hedge_ratio}")

    futures_price = 4000
    hedge_position = strategy.calculate_hedge_position(
        50_000_000,
        strategy.current_beta,
        futures_price
    )

    print(f"  期货持仓: {hedge_position} 手")
    print(f"  对冲名义价值: {abs(hedge_position) * futures_price * 300:,.0f}")

    # 模拟市场下跌
    print("\n模拟市场下跌10%:")
    market_drop = -0.10
    portfolio_loss = 50_000_000 * strategy.current_beta * market_drop
    futures_gain = abs(hedge_position) * futures_price * 300 * market_drop

    print(f"  组合损失: {portfolio_loss:,.0f}")
    print(f"  期货盈利: {-futures_gain:,.0f}")
    print(f"  净损失: {portfolio_loss + futures_gain:,.0f}")
    print(f"  对冲效果: {-(futures_gain / portfolio_loss):.1%}")


def main():
    """主函数"""
    print("股指期货对冲完整示例")
    print("=" * 60)

    # 1. 准备数据
    portfolio_returns, index_returns = prepare_sample_data()

    # 2. Beta计算
    beta, rolling_beta = beta_calculation_demo(portfolio_returns, index_returns)

    # 3. 静态对冲策略
    static_strategy = static_hedge_demo(portfolio_returns, index_returns)

    # 4. 动态对冲策略
    dynamic_strategy = dynamic_hedge_demo(portfolio_returns, index_returns)

    # 5. 最小方差对冲
    mv_strategy, futures_returns = minimum_variance_hedge_demo(portfolio_returns, index_returns)

    # 6. 对冲效果评估
    hedge_effectiveness_evaluation(portfolio_returns, index_returns, futures_returns)

    # 7. 实际应用示例
    practical_example()

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)
    print("\n关键要点:")
    print("1. Beta衡量组合的系统性风险")
    print("2. 对冲比率决定对冲程度")
    print("3. 静态对冲简单，动态对冲灵活")
    print("4. 最小方差对冲最优化波动率")
    print("5. 对冲可以保留Alpha，消除Beta")
    print("6. 需要定期再平衡维持对冲效果")


if __name__ == "__main__":
    main()
