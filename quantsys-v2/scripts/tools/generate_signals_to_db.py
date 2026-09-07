#!/usr/bin/env python3
"""
生成买卖信号并保存到数据库

使用系统已有的接口：
1. 从数据库获取股票列表
2. 获取K线数据
3. 运行策略生成信号
4. 保存信号到数据库
"""

import os
import sys
from datetime import datetime, date
from typing import List, Dict, Any

# 设置数据库连接
os.environ['PGDATABASE'] = 'quant_investment'

from adapters.outbound.repositories import StockORMRepository
from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories import SignalORMRepository
from domain.quantlib.engine.strategy_factory import StrategyFactory


def generate_signals_for_stock(symbol: str, klines: List[Dict]) -> List[Dict]:
    """为单只股票生成信号"""

    # 自动发现所有策略
    if not StrategyFactory._registry:
        StrategyFactory.auto_discover()

    signals = []

    # 运行所有可用策略
    for strategy_type in StrategyFactory._registry.keys():
        try:
            strategy = StrategyFactory.create(strategy_type)

            # 生成信号
            signal = strategy.generate_signal(klines, {})

            if signal and signal.get('action') != 'hold':
                signals.append({
                    'symbol': symbol,
                    'strategy_type': strategy_type,
                    'strategy_name': strategy.name,
                    'action': signal['action'],
                    'confidence': signal.get('confidence', 0.5),
                    'reason': signal.get('reason', ''),
                    'price': klines[-1]['close'] if klines else 0.0
                })
        except Exception as e:
            print(f"  ⚠️  策略 {strategy_type} 执行失败: {e}")
            continue

    return signals


def save_signal_to_db(signal_repo: SignalRepository, signal: Dict, stock_name: str):
    """保存信号到数据库"""
    try:
        signal_repo.create_signal({
            'signal_date': date.today().isoformat(),  # 转换为字符串
            'symbol': signal['symbol'],
            'name': stock_name,
            'action': signal['action'],
            'action_type': 1 if signal['action'] == 'buy' else 2,  # 1=buy, 2=sell
            'strategy_id': signal['strategy_type'],
            'price': signal['price'],
            'reason': signal['reason'],
            'confidence': signal['confidence'],
            'indicators': {}
        })
        return True
    except Exception as e:
        print(f"    ❌ 保存失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 80)
    print("量化交易信号生成系统")
    print("=" * 80)

    # 初始化Repository
    print("\n初始化数据访问层...")
    stock_repo = StockORMRepository()
    kline_repo = KlineORMRepository()
    signal_repo = SignalORMRepository()

    # 获取股票列表（全量）
    print("\n获取股票列表...")
    stocks = stock_repo.get_all(market='A')  # 全量处理
    print(f"找到 {len(stocks)} 只股票")

    if not stocks:
        print("❌ 没有找到股票数据，请先导入股票数据")
        return

    # 统计
    total_signals = 0
    buy_signals = 0
    sell_signals = 0
    saved_signals = 0

    # 为每只股票生成信号
    print("\n开始生成信号...")
    print("-" * 80)

    for i, stock in enumerate(stocks, 1):
        symbol = stock['symbol']
        name = stock.get('name', symbol)

        print(f"\n[{i}/{len(stocks)}] {symbol} ({name})")

        # 获取K线数据（最近100天）
        try:
            from datetime import timedelta
            end_date = date.today().isoformat()
            start_date = (date.today() - timedelta(days=100)).isoformat()

            klines = kline_repo.get_daily_klines(symbol, start_date, end_date)
            if not klines:
                print(f"  ⚠️  没有K线数据，跳过")
                continue

            print(f"  ✓ 获取到 {len(klines)} 天K线数据")
        except Exception as e:
            print(f"  ❌ 获取K线失败: {e}")
            continue

        # 生成信号
        try:
            signals = generate_signals_for_stock(symbol, klines)
            print(f"  ✓ 生成 {len(signals)} 个信号")

            if not signals:
                print(f"  → 无交易信号")
                continue

            # 显示信号
            for signal in signals:
                action_icon = "🟢" if signal['action'] == 'buy' else "🔴"
                print(f"    {action_icon} {signal['strategy_name']:<25} "
                      f"{signal['action']:<6} "
                      f"置信度:{signal['confidence']:.2f} "
                      f"价格:¥{signal['price']:.2f}")

                # 保存到数据库
                if save_signal_to_db(signal_repo, signal, name):
                    saved_signals += 1
                    total_signals += 1
                    if signal['action'] == 'buy':
                        buy_signals += 1
                    else:
                        sell_signals += 1

        except Exception as e:
            print(f"  ❌ 生成信号失败: {e}")
            continue

    # 汇总报告
    print("\n" + "=" * 80)
    print("信号生成完成")
    print("=" * 80)
    print(f"\n总计:")
    print(f"  分析股票数: {len(stocks)}")
    print(f"  生成信号数: {total_signals}")
    print(f"  保存成功数: {saved_signals}")
    print(f"  买入信号: {buy_signals} 个")
    print(f"  卖出信号: {sell_signals} 个")

    # 查询并显示保存的信号
    print("\n" + "=" * 80)
    print("数据库中的最新信号")
    print("=" * 80)

    try:
        latest_signals = signal_repo.get_latest_signals(limit=20)

        if latest_signals:
            print(f"\n{'股票':<12} {'名称':<10} {'动作':<6} {'置信度':<8} {'价格':<10} {'策略'}")
            print("-" * 80)

            for sig in latest_signals:
                action_icon = "🟢" if sig['action'] == 'buy' else "🔴"
                print(f"{sig['symbol']:<12} "
                      f"{sig['name']:<10} "
                      f"{action_icon} {sig['action']:<6} "
                      f"{sig.get('confidence', 0):<8.2f} "
                      f"¥{sig.get('price', 0):<9.2f} "
                      f"{sig.get('strategy_id', 'N/A')}")
        else:
            print("\n暂无信号")

    except Exception as e:
        print(f"\n查询信号失败: {e}")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
