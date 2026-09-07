#!/usr/bin/env python3
"""
买卖信号生成完整示例

展示如何使用Quantsys-v2生成买卖信号
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


from domain.quantlib.engine.strategy_runner import StrategyRunner
from adapters.outbound.repositories import StrategyORMRepository
from domain.quantlib.engine.strategy_combiner import StrategyCombiner


def generate_sample_klines(symbol: str = "000001.SZ", days: int = 100) -> list:
    """生成示例K线数据"""
    np.random.seed(42)

    base_price = 10.0
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    klines = []
    price = base_price

    for date in dates:
        # 模拟价格波动
        change = np.random.randn() * 0.02
        price = price * (1 + change)

        high = price * (1 + abs(np.random.randn() * 0.01))
        low = price * (1 - abs(np.random.randn() * 0.01))
        volume = np.random.randint(1000000, 10000000)

        klines.append({
            'symbol': symbol,
            'date': date.strftime('%Y-%m-%d'),
            'open': price * 0.99,
            'high': high,
            'low': low,
            'close': price,
            'volume': volume,
            'amount': volume * price
        })

    return klines


def example_1_basic_signal_generation():
    """示例1: 基础信号生成"""
    print("=" * 80)
    print("示例1: 基础信号生成")
    print("=" * 80)

    # 1. 准备数据
    symbol = "000001.SZ"
    klines = generate_sample_klines(symbol, days=100)
    print(f"\n数据准备完成: {symbol}, {len(klines)}天K线")

    # 2. 创建策略运行器
    runner = StrategyRunner(strategy_repo=StrategyORMRepository())

    # 3. 运行所有策略，生成信号
    print("\n运行策略，生成信号...")
    signals = runner.run(klines=klines, symbol=symbol)

    # 4. 显示所有信号
    print(f"\n生成 {len(signals)} 个信号:")
    print(f"{'策略':<25} {'动作':<8} {'置信度':<10} {'原因'}")
    print("-" * 80)

    for signal in signals[:10]:  # 显示前10个
        print(f"{signal['strategy_name']:<25} "
              f"{signal['action']:<8} "
              f"{signal['confidence']:<10.2f} "
              f"{signal['reason'][:40]}")

    # 5. 统计信号分布
    buy_signals = [s for s in signals if s['action'] == 'buy']
    sell_signals = [s for s in signals if s['action'] == 'sell']
    hold_signals = [s for s in signals if s['action'] == 'hold']

    print(f"\n信号统计:")
    print(f"  买入信号: {len(buy_signals)} 个")
    print(f"  卖出信号: {len(sell_signals)} 个")
    print(f"  持有信号: {len(hold_signals)} 个")


def example_2_top_signals():
    """示例2: 获取Top N信号"""
    print("\n" + "=" * 80)
    print("示例2: 获取Top N高置信度信号")
    print("=" * 80)

    # 准备数据
    symbol = "000001.SZ"
    klines = generate_sample_klines(symbol, days=100)

    # 创建运行器
    runner = StrategyRunner(strategy_repo=StrategyORMRepository())

    # 获取Top 5买入信号
    print("\nTop 5 买入信号:")
    top_buy_signals = runner.get_top_signals(
        klines=klines,
        symbol=symbol,
        top_n=5,
        action_filter='buy'
    )

    print(f"{'排名':<6} {'策略':<25} {'置信度':<10} {'原因'}")
    print("-" * 80)

    for i, signal in enumerate(top_buy_signals, 1):
        print(f"{i:<6} "
              f"{signal['strategy_name']:<25} "
              f"{signal['confidence']:<10.2f} "
              f"{signal['reason'][:40]}")

    # 获取Top 5卖出信号
    print("\nTop 5 卖出信号:")
    top_sell_signals = runner.get_top_signals(
        klines=klines,
        symbol=symbol,
        top_n=5,
        action_filter='sell'
    )

    for i, signal in enumerate(top_sell_signals, 1):
        print(f"{i:<6} "
              f"{signal['strategy_name']:<25} "
              f"{signal['confidence']:<10.2f} "
              f"{signal['reason'][:40]}")


def example_3_signal_combination():
    """示例3: 信号组合（多策略投票）"""
    print("\n" + "=" * 80)
    print("示例3: 多策略信号组合")
    print("=" * 80)

    # 准备数据
    symbol = "000001.SZ"
    klines = generate_sample_klines(symbol, days=100)

    # 生成信号
    runner = StrategyRunner(strategy_repo=StrategyORMRepository())
    signals = runner.run(klines=klines, symbol=symbol)

    # 创建信号组合器
    combiner = StrategyCombiner()

    # 方法1: 加权投票
    print("\n方法1: 加权投票")
    combined_signal = combiner.combine_signals(
        signals=signals,
        method='weighted_vote'
    )

    print(f"  组合结果: {combined_signal['action']}")
    print(f"  综合置信度: {combined_signal['confidence']:.2f}")
    print(f"  参与策略数: {combined_signal.get('vote_count', 0)}")

    # 方法2: 平均置信度
    print("\n方法2: 平均置信度")
    combined_signal = combiner.combine_signals(
        signals=signals,
        method='average_confidence'
    )

    print(f"  组合结果: {combined_signal['action']}")
    print(f"  平均置信度: {combined_signal['confidence']:.2f}")


def example_4_multi_stock_signals():
    """示例4: 多股票信号生成"""
    print("\n" + "=" * 80)
    print("示例4: 多股票信号生成")
    print("=" * 80)

    # 准备多只股票数据
    symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600036.SH"]

    runner = StrategyRunner(strategy_repo=StrategyORMRepository())
    all_signals = []

    print("\n生成多股票信号...")
    for symbol in symbols:
        klines = generate_sample_klines(symbol, days=100)
        signals = runner.run(klines=klines, symbol=symbol)

        # 只保留买入信号
        buy_signals = [s for s in signals if s['action'] == 'buy']
        all_signals.extend(buy_signals)

    # 按置信度排序
    all_signals.sort(key=lambda x: x['confidence'], reverse=True)

    # 显示Top 10
    print(f"\nTop 10 买入机会（跨股票）:")
    print(f"{'排名':<6} {'股票':<12} {'策略':<25} {'置信度':<10}")
    print("-" * 80)

    for i, signal in enumerate(all_signals[:10], 1):
        print(f"{i:<6} "
              f"{signal['symbol']:<12} "
              f"{signal['strategy_name']:<25} "
              f"{signal['confidence']:<10.2f}")


def example_5_signal_filtering():
    """示例5: 信号过滤和筛选"""
    print("\n" + "=" * 80)
    print("示例5: 信号过滤和筛选")
    print("=" * 80)

    # 准备数据
    symbol = "000001.SZ"
    klines = generate_sample_klines(symbol, days=100)

    # 生成信号
    runner = StrategyRunner(strategy_repo=StrategyORMRepository())
    signals = runner.run(klines=klines, symbol=symbol)

    # 过滤1: 高置信度信号（>0.7）
    print("\n过滤1: 高置信度信号（置信度 > 0.7）")
    high_confidence_signals = [s for s in signals if s['confidence'] > 0.7]
    print(f"  找到 {len(high_confidence_signals)} 个高置信度信号")

    for signal in high_confidence_signals[:5]:
        print(f"    {signal['strategy_name']:<25} "
              f"{signal['action']:<8} "
              f"{signal['confidence']:.2f}")

    # 过滤2: 特定策略类型
    print("\n过滤2: 趋势跟踪策略信号")
    trend_strategies = ['ma_cross', 'turtle', 'donchian_channel']
    trend_signals = [s for s in signals
                     if s['strategy_type'] in trend_strategies
                     and s['action'] == 'buy']
    print(f"  找到 {len(trend_signals)} 个趋势策略买入信号")

    for signal in trend_signals[:5]:
        print(f"    {signal['strategy_name']:<25} "
              f"{signal['confidence']:.2f}")

    # 过滤3: 多策略共振（多个策略同时发出买入信号）
    print("\n过滤3: 多策略共振分析")
    buy_signals = [s for s in signals if s['action'] == 'buy']
    sell_signals = [s for s in signals if s['action'] == 'sell']

    print(f"  买入信号数: {len(buy_signals)}")
    print(f"  卖出信号数: {len(sell_signals)}")

    if len(buy_signals) > len(sell_signals) * 2:
        print(f"  ✅ 多策略共振买入信号！（买入信号数量是卖出的2倍以上）")
    elif len(sell_signals) > len(buy_signals) * 2:
        print(f"  ⚠️ 多策略共振卖出信号！（卖出信号数量是买入的2倍以上）")
    else:
        print(f"  ➖ 信号分歧，建议观望")


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("Quantsys-v2 买卖信号生成完整示例")
    print("=" * 80)

    try:
        # 运行所有示例
        example_1_basic_signal_generation()
        example_2_top_signals()
        example_3_signal_combination()
        example_4_multi_stock_signals()
        example_5_signal_filtering()

        print("\n" + "=" * 80)
        print("所有示例运行完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
