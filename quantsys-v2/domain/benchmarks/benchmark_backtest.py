#!/usr/bin/env python3
"""
策略回测性能基准测试

测试场景：
- 单策略回测（1年/3年/5年数据）
- 多策略回测（10/20/50个策略）
- 全市场回测（100/500/1000只股票）
- 串行 vs 并行对比
"""

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing



def generate_market_data(n_stocks: int, n_days: int) -> Dict[str, pd.DataFrame]:
    """生成市场数据"""
    np.random.seed(42)
    market_data = {}

    for i in range(n_stocks):
        symbol = f"00{i:04d}.SZ"

        # 生成价格序列
        base_price = 10 + np.random.rand() * 90
        returns = np.random.randn(n_days) * 0.02
        close = base_price * np.exp(np.cumsum(returns))
        high = close * (1 + np.abs(np.random.randn(n_days) * 0.01))
        low = close * (1 - np.abs(np.random.randn(n_days) * 0.01))
        volume = np.random.randint(1000000, 10000000, n_days)

        df = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=n_days, freq='D'),
            'open': close * 0.99,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

        market_data[symbol] = df

    return market_data


def simple_ma_strategy(df: pd.DataFrame, fast: int = 5, slow: int = 20) -> pd.DataFrame:
    """简单移动平均策略"""
    df = df.copy()

    # 计算移动平均
    df['ma_fast'] = df['close'].rolling(fast).mean()
    df['ma_slow'] = df['close'].rolling(slow).mean()

    # 生成信号
    df['signal'] = 0
    df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1
    df.loc[df['ma_fast'] < df['ma_slow'], 'signal'] = -1

    # 计算收益
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['signal'].shift(1) * df['returns']

    return df


def backtest_single_stock(symbol: str, df: pd.DataFrame, strategy_params: Dict) -> Dict:
    """回测单只股票"""
    result = simple_ma_strategy(
        df,
        fast=strategy_params.get('fast', 5),
        slow=strategy_params.get('slow', 20)
    )

    # 计算指标
    total_return = (1 + result['strategy_returns'].fillna(0)).prod() - 1
    sharpe_ratio = result['strategy_returns'].mean() / (result['strategy_returns'].std() + 1e-10) * np.sqrt(252)

    return {
        'symbol': symbol,
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'n_trades': (result['signal'].diff() != 0).sum()
    }


def backtest_serial(market_data: Dict[str, pd.DataFrame], strategy_params: Dict) -> List[Dict]:
    """串行回测"""
    results = []

    for symbol, df in market_data.items():
        result = backtest_single_stock(symbol, df, strategy_params)
        results.append(result)

    return results


def backtest_parallel(market_data: Dict[str, pd.DataFrame], strategy_params: Dict, n_workers: int = 4) -> List[Dict]:
    """并行回测"""
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = []

        for symbol, df in market_data.items():
            future = executor.submit(backtest_single_stock, symbol, df, strategy_params)
            futures.append(future)

        results = [f.result() for f in futures]

    return results


def benchmark_backtest(
    market_data: Dict[str, pd.DataFrame],
    strategy_params: Dict,
    mode: str = 'serial',
    n_workers: int = 4,
    repeat: int = 3
) -> Dict:
    """测试回测性能"""
    times = []

    for _ in range(repeat):
        start = time.perf_counter()

        if mode == 'serial':
            results = backtest_serial(market_data, strategy_params)
        elif mode == 'parallel':
            results = backtest_parallel(market_data, strategy_params, n_workers)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return {
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'n_stocks': len(market_data),
        'throughput': len(market_data) / np.mean(times)
    }


def run_backtest_benchmarks():
    """运行回测基准测试"""
    print("=" * 80)
    print("策略回测性能基准测试")
    print("=" * 80)

    results = {
        'test_name': 'strategy_backtest',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'cpu_count': multiprocessing.cpu_count(),
        'scenarios': []
    }

    # 测试场景
    scenarios = [
        {'n_stocks': 50, 'n_days': 252, 'name': '50股票×1年'},
        {'n_stocks': 100, 'n_days': 252, 'name': '100股票×1年'},
        {'n_stocks': 200, 'n_days': 252, 'name': '200股票×1年'},
        {'n_stocks': 100, 'n_days': 756, 'name': '100股票×3年'},
    ]

    strategy_params = {'fast': 5, 'slow': 20}

    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"场景: {scenario['name']}")
        print(f"{'='*80}")

        # 生成市场数据
        print(f"生成市场数据...")
        market_data = generate_market_data(scenario['n_stocks'], scenario['n_days'])
        print(f"数据规模: {scenario['n_stocks']} 股票 × {scenario['n_days']} 天")

        scenario_result = {
            'name': scenario['name'],
            'n_stocks': scenario['n_stocks'],
            'n_days': scenario['n_days'],
            'serial': {},
            'parallel': {}
        }

        # 串行回测
        print(f"\n[串行回测]")
        serial_result = benchmark_backtest(
            market_data,
            strategy_params,
            mode='serial',
            repeat=3
        )
        scenario_result['serial'] = serial_result

        print(f"  总耗时: {serial_result['mean_time']:.3f}s ± {serial_result['std_time']:.3f}s")
        print(f"  吞吐量: {serial_result['throughput']:.1f} 股票/秒")

        # 并行回测
        n_workers = min(multiprocessing.cpu_count(), scenario['n_stocks'])
        print(f"\n[并行回测] (workers={n_workers})")

        parallel_result = benchmark_backtest(
            market_data,
            strategy_params,
            mode='parallel',
            n_workers=n_workers,
            repeat=3
        )
        scenario_result['parallel'] = parallel_result

        print(f"  总耗时: {parallel_result['mean_time']:.3f}s ± {parallel_result['std_time']:.3f}s")
        print(f"  吞吐量: {parallel_result['throughput']:.1f} 股票/秒")

        # 计算加速比
        speedup = serial_result['mean_time'] / parallel_result['mean_time']
        scenario_result['speedup'] = speedup
        scenario_result['n_workers'] = n_workers

        print(f"\n[性能对比]")
        print(f"  加速比: {speedup:.2f}x")
        print(f"  并行效率: {speedup / n_workers * 100:.1f}%")

        results['scenarios'].append(scenario_result)

    # 保存结果
    output_file = Path(__file__).parent / 'results' / 'benchmark_backtest.json'
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print(f"测试完成！结果已保存到: {output_file}")
    print(f"{'='*80}")

    return results


def main():
    """主函数"""
    try:
        results = run_backtest_benchmarks()

        # 打印汇总
        print("\n" + "=" * 80)
        print("测试汇总")
        print("=" * 80)
        print(f"CPU核心数: {results['cpu_count']}")

        for scenario in results['scenarios']:
            print(f"\n{scenario['name']}:")
            print(f"  串行: {scenario['serial']['mean_time']:.3f}s ({scenario['serial']['throughput']:.1f} 股票/秒)")
            print(f"  并行: {scenario['parallel']['mean_time']:.3f}s ({scenario['parallel']['throughput']:.1f} 股票/秒)")
            print(f"  加速比: {scenario['speedup']:.2f}x (workers={scenario['n_workers']})")

        return 0
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
