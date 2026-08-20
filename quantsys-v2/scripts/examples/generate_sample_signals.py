#!/usr/bin/env python3
"""
一键生成股票买卖信号

无需数据库，直接运行，生成买卖信号
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# 导入策略
from domain.quantlib.engine.ma_cross import MACrossStrategy
from domain.quantlib.engine.rsi_reversal import RSIReversalStrategy
from domain.quantlib.engine.bollinger_breakout import BollingerBreakoutStrategy
from domain.quantlib.engine.momentum_strategy import MomentumStrategy
from domain.quantlib.engine.mean_reversion_strategy import MeanReversionStrategy


def generate_sample_klines(symbol: str, days: int = 100) -> list:
    """生成示例K线数据（实际使用时替换为真实数据）"""
    np.random.seed(hash(symbol) % 2**32)

    base_price = 10.0 + np.random.rand() * 40.0
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


def run_single_strategy(strategy, klines, params):
    """运行单个策略"""
    try:
        signal = strategy.generate_signal(klines, params)
        return {
            'strategy_name': strategy.name,
            'action': signal['action'],
            'confidence': signal['confidence'],
            'reason': signal.get('reason', ''),
            'success': True
        }
    except Exception as e:
        return {
            'strategy_name': strategy.name,
            'action': 'hold',
            'confidence': 0.0,
            'reason': f'策略执行失败: {str(e)}',
            'success': False
        }


def generate_signals_for_stock(symbol: str, klines: list = None) -> dict:
    """为单只股票生成买卖信号"""

    # 如果没有提供K线数据，生成示例数据
    if klines is None:
        print(f"  生成示例数据...")
        klines = generate_sample_klines(symbol, days=100)

    # 定义策略和参数
    strategies = [
        (MACrossStrategy(name="MA交叉策略"), {'fast': 5, 'slow': 20}),
        (RSIReversalStrategy(name="RSI反转策略"), {'period': 14, 'oversold': 30, 'overbought': 70}),
        (BollingerBreakoutStrategy(name="布林带突破"), {'period': 20, 'std_dev': 2}),
        (MomentumStrategy(name="动量策略"), {'period': 20, 'threshold': 0.02}),
        (MeanReversionStrategy(name="均值回归"), {'period': 20, 'threshold': 2.0}),
    ]

    # 运行所有策略
    signals = []
    for strategy, params in strategies:
        signal = run_single_strategy(strategy, klines, params)
        signals.append(signal)

    # 统计信号
    buy_signals = [s for s in signals if s['action'] == 'buy']
    sell_signals = [s for s in signals if s['action'] == 'sell']
    hold_signals = [s for s in signals if s['action'] == 'hold']

    # 计算综合信号
    if len(buy_signals) > len(sell_signals):
        final_action = 'buy'
        final_confidence = np.mean([s['confidence'] for s in buy_signals]) if buy_signals else 0.0
    elif len(sell_signals) > len(buy_signals):
        final_action = 'sell'
        final_confidence = np.mean([s['confidence'] for s in sell_signals]) if sell_signals else 0.0
    else:
        final_action = 'hold'
        final_confidence = 0.5

    return {
        'symbol': symbol,
        'final_action': final_action,
        'final_confidence': final_confidence,
        'buy_count': len(buy_signals),
        'sell_count': len(sell_signals),
        'hold_count': len(hold_signals),
        'signals': signals,
        'current_price': klines[-1]['close'] if klines else 0.0,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


def print_signal_report(result: dict):
    """打印信号报告"""
    symbol = result['symbol']
    action = result['final_action']
    confidence = result['final_confidence']

    # 动作图标
    action_icon = {
        'buy': '🟢 买入',
        'sell': '🔴 卖出',
        'hold': '⚪ 持有'
    }

    print(f"\n{'='*80}")
    print(f"股票: {symbol}")
    print(f"当前价格: ¥{result['current_price']:.2f}")
    print(f"{'='*80}")

    print(f"\n【综合信号】")
    print(f"  动作: {action_icon.get(action, action)}")
    print(f"  置信度: {confidence:.2%}")
    print(f"  信号统计: 买入{result['buy_count']}个 | 卖出{result['sell_count']}个 | 持有{result['hold_count']}个")

    print(f"\n【各策略信号】")
    print(f"{'策略':<20} {'动作':<8} {'置信度':<10} {'原因'}")
    print(f"{'-'*80}")

    for signal in result['signals']:
        action_str = action_icon.get(signal['action'], signal['action'])
        print(f"{signal['strategy_name']:<20} "
              f"{action_str:<8} "
              f"{signal['confidence']:<10.2%} "
              f"{signal['reason'][:40]}")

    print(f"\n生成时间: {result['timestamp']}")


def main():
    """主函数"""
    print("=" * 80)
    print("量化交易信号生成器")
    print("=" * 80)

    # 定义股票池（可以修改为您关注的股票）
    stock_pool = [
        "000001.SZ",  # 平安银行
        "000002.SZ",  # 万科A
        "600000.SH",  # 浦发银行
        "600036.SH",  # 招商银行
        "000858.SZ",  # 五粮液
    ]

    print(f"\n分析股票池: {len(stock_pool)} 只股票")
    print(f"股票列表: {', '.join(stock_pool)}")

    # 生成信号
    all_results = []

    for i, symbol in enumerate(stock_pool, 1):
        print(f"\n[{i}/{len(stock_pool)}] 分析 {symbol}...")
        result = generate_signals_for_stock(symbol)
        all_results.append(result)
        print_signal_report(result)

    # 汇总报告
    print("\n" + "=" * 80)
    print("汇总报告")
    print("=" * 80)

    # 按置信度排序
    buy_opportunities = [r for r in all_results if r['final_action'] == 'buy']
    buy_opportunities.sort(key=lambda x: x['final_confidence'], reverse=True)

    sell_opportunities = [r for r in all_results if r['final_action'] == 'sell']
    sell_opportunities.sort(key=lambda x: x['final_confidence'], reverse=True)

    print(f"\n【买入机会】({len(buy_opportunities)} 只)")
    if buy_opportunities:
        print(f"{'排名':<6} {'股票':<12} {'当前价':<10} {'置信度':<10} {'买入信号数'}")
        print(f"{'-'*60}")
        for i, r in enumerate(buy_opportunities, 1):
            print(f"{i:<6} {r['symbol']:<12} ¥{r['current_price']:<9.2f} "
                  f"{r['final_confidence']:<10.2%} {r['buy_count']}个")
    else:
        print("  暂无买入机会")

    print(f"\n【卖出信号】({len(sell_opportunities)} 只)")
    if sell_opportunities:
        print(f"{'排名':<6} {'股票':<12} {'当前价':<10} {'置信度':<10} {'卖出信号数'}")
        print(f"{'-'*60}")
        for i, r in enumerate(sell_opportunities, 1):
            print(f"{i:<6} {r['symbol']:<12} ¥{r['current_price']:<9.2f} "
                  f"{r['final_confidence']:<10.2%} {r['sell_count']}个")
    else:
        print("  暂无卖出信号")

    # 保存结果到示例输出目录，避免根目录和脚本目录堆积生成文件
    output_dir = Path(__file__).resolve().parents[1] / 'examples' / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("量化交易信号报告\n")
        f.write("=" * 80 + "\n\n")

        for result in all_results:
            f.write(f"\n股票: {result['symbol']}\n")
            f.write(f"综合信号: {result['final_action']} (置信度: {result['final_confidence']:.2%})\n")
            f.write(f"当前价格: ¥{result['current_price']:.2f}\n")
            f.write(f"信号统计: 买入{result['buy_count']}个 | 卖出{result['sell_count']}个 | 持有{result['hold_count']}个\n")
            f.write("\n各策略信号:\n")
            for signal in result['signals']:
                f.write(f"  {signal['strategy_name']}: {signal['action']} ({signal['confidence']:.2%}) - {signal['reason']}\n")
            f.write("\n" + "-" * 80 + "\n")

    print(f"\n信号报告已保存到: {output_file}")
    print("\n" + "=" * 80)
    print("分析完成！")
    print("=" * 80)


if __name__ == '__main__':
    main()
