#!/usr/bin/env python3
"""
分批次生成买卖信号并保存到数据库

使用系统已有的接口：
1. 从数据库获取股票列表
2. 分批处理股票
3. 获取K线数据
4. 运行策略生成信号
5. 保存信号到数据库
"""

import os
import sys
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Any

# 设置数据库连接
os.environ['PGDATABASE'] = 'quant_investment'

from adapters.outbound.repositories import StockORMRepository
from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories import SignalORMRepository
from domain.quantlib.engine.strategy_factory import StrategyFactory


# 配置参数
BATCH_SIZE = 500  # 每批处理的股票数量
BATCH_DELAY = 2   # 批次之间的延迟（秒）


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
        except Exception:
            # 静默处理策略错误（如缺少指标），避免输出过多
            pass

    return signals


def save_signal_to_db(signal_repo: SignalRepository, signal: Dict, stock_name: str):
    """保存信号到数据库"""
    try:
        signal_repo.create_signal({
            'signal_date': date.today().isoformat(),
            'symbol': signal['symbol'],
            'name': stock_name,
            'action': signal['action'],
            'action_type': 1 if signal['action'] == 'buy' else 2,
            'strategy_id': signal['strategy_type'],
            'price': signal['price'],
            'reason': signal['reason'],
            'confidence': signal['confidence'],
            'indicators': {}
        })
        return True
    except Exception as e:
        return False


def process_batch(stocks: List[Dict], batch_num: int, total_batches: int,
                 kline_repo: KlineRepository, signal_repo: SignalRepository) -> Dict:
    """处理一批股票"""

    batch_stats = {
        'processed': 0,
        'signals': 0,
        'buy': 0,
        'sell': 0,
        'saved': 0,
        'errors': 0
    }

    print(f"\n{'='*80}")
    print(f"批次 {batch_num}/{total_batches} - 处理 {len(stocks)} 只股票")
    print(f"{'='*80}")

    start_time = time.time()

    for i, stock in enumerate(stocks, 1):
        symbol = stock['symbol']
        name = stock.get('name', symbol)

        # 每50只股票显示一次进度
        if i % 50 == 0 or i == len(stocks):
            elapsed = time.time() - start_time
            speed = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(stocks)}] 进度: {i/len(stocks)*100:.1f}% | "
                  f"速度: {speed:.1f} 股票/秒 | "
                  f"信号: {batch_stats['signals']} 个")

        try:
            # 获取K线数据（最近100天）
            end_date = date.today().isoformat()
            start_date = (date.today() - timedelta(days=100)).isoformat()

            klines = kline_repo.get_daily_klines(symbol, start_date, end_date)
            if not klines:
                batch_stats['processed'] += 1
                continue

            # 生成信号
            signals = generate_signals_for_stock(symbol, klines)

            if signals:
                # 保存信号
                for signal in signals:
                    if save_signal_to_db(signal_repo, signal, name):
                        batch_stats['saved'] += 1
                        batch_stats['signals'] += 1
                        if signal['action'] == 'buy':
                            batch_stats['buy'] += 1
                        else:
                            batch_stats['sell'] += 1

            batch_stats['processed'] += 1

        except Exception as e:
            batch_stats['errors'] += 1
            continue

    elapsed = time.time() - start_time

    # 批次统计
    print(f"\n批次 {batch_num} 完成:")
    print(f"  处理股票: {batch_stats['processed']}")
    print(f"  生成信号: {batch_stats['signals']} 个 (买入:{batch_stats['buy']}, 卖出:{batch_stats['sell']})")
    print(f"  保存成功: {batch_stats['saved']}")
    print(f"  错误数量: {batch_stats['errors']}")
    print(f"  耗时: {elapsed:.1f} 秒")

    return batch_stats


def main():
    """主函数"""
    print("=" * 80)
    print("量化交易信号生成系统 - 批次处理模式")
    print("=" * 80)
    print(f"\n配置:")
    print(f"  批次大小: {BATCH_SIZE} 只股票/批")
    print(f"  批次延迟: {BATCH_DELAY} 秒")

    # 初始化Repository
    print("\n初始化数据访问层...")
    stock_repo = StockORMRepository()
    kline_repo = KlineORMRepository()
    signal_repo = SignalORMRepository()

    # 获取股票列表
    print("\n获取股票列表...")
    all_stocks = stock_repo.get_all(market='A')
    print(f"找到 {len(all_stocks)} 只股票")

    if not all_stocks:
        print("❌ 没有找到股票数据，请先导入股票数据")
        return

    # 计算批次数
    total_batches = (len(all_stocks) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"将分为 {total_batches} 个批次处理")

    # 全局统计
    global_stats = {
        'processed': 0,
        'signals': 0,
        'buy': 0,
        'sell': 0,
        'saved': 0,
        'errors': 0
    }

    overall_start = time.time()

    # 分批处理
    for batch_num in range(1, total_batches + 1):
        start_idx = (batch_num - 1) * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(all_stocks))
        batch_stocks = all_stocks[start_idx:end_idx]

        # 处理当前批次
        batch_stats = process_batch(
            batch_stocks,
            batch_num,
            total_batches,
            kline_repo,
            signal_repo
        )

        # 累加统计
        for key in global_stats:
            global_stats[key] += batch_stats[key]

        # 批次间延迟（最后一批不需要）
        if batch_num < total_batches:
            print(f"\n等待 {BATCH_DELAY} 秒后继续下一批次...")
            time.sleep(BATCH_DELAY)

    overall_elapsed = time.time() - overall_start

    # 最终汇总报告
    print("\n" + "=" * 80)
    print("全部批次处理完成")
    print("=" * 80)
    print(f"\n总计:")
    print(f"  处理股票数: {global_stats['processed']}/{len(all_stocks)}")
    print(f"  生成信号数: {global_stats['signals']}")
    print(f"  保存成功数: {global_stats['saved']}")
    print(f"  买入信号: {global_stats['buy']} 个")
    print(f"  卖出信号: {global_stats['sell']} 个")
    print(f"  错误数量: {global_stats['errors']}")
    print(f"  总耗时: {overall_elapsed/60:.1f} 分钟")
    print(f"  平均速度: {global_stats['processed']/overall_elapsed:.1f} 股票/秒")

    # 查询并显示最新信号样例
    print("\n" + "=" * 80)
    print("数据库中的最新信号样例（前20条）")
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
