#!/usr/bin/env python3
"""
策略回测性能优化版本

实现三种优化方案：
1. 方案1：增加任务粒度（批量处理）
2. 方案2：使用线程池（避免序列化开销）
3. 方案3：共享内存（零拷贝）
4. 方案4：混合方案（线程池 + 批量处理）
"""

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing
from multiprocessing import shared_memory
import ctypes



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


# ============================================================================
# 原始实现（基线）
# ============================================================================

def backtest_serial(market_data: Dict[str, pd.DataFrame], strategy_params: Dict) -> List[Dict]:
    """串行回测（基线）"""
    results = []

    for symbol, df in market_data.items():
        result = backtest_single_stock(symbol, df, strategy_params)
        results.append(result)

    return results


def backtest_parallel_baseline(market_data: Dict[str, pd.DataFrame], strategy_params: Dict, n_workers: int = 4) -> List[Dict]:
    """并行回测（原始实现 - 有问题的版本）"""
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = []

        for symbol, df in market_data.items():
            future = executor.submit(backtest_single_stock, symbol, df, strategy_params)
            futures.append(future)

        results = [f.result() for f in futures]

    return results


# ============================================================================
# 方案1：增加任务粒度（批量处理）
# ============================================================================

def backtest_batch(batch_data: List[Tuple[str, pd.DataFrame]], strategy_params: Dict) -> List[Dict]:
    """批量回测多只股票"""
    results = []

    for symbol, df in batch_data:
        result = backtest_single_stock(symbol, df, strategy_params)
        results.append(result)

    return results


def backtest_parallel_batched(
    market_data: Dict[str, pd.DataFrame],
    strategy_params: Dict,
    n_workers: int = 4,
    batch_size: int = 10
) -> List[Dict]:
    """并行回测 - 批量处理版本"""
    # 将股票分批
    items = list(market_data.items())
    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(backtest_batch, batch, strategy_params) for batch in batches]
        batch_results = [f.result() for f in futures]

    # 展平结果
    results = []
    for batch_result in batch_results:
        results.extend(batch_result)

    return results


# ============================================================================
# 方案2：使用线程池（避免序列化开销）
# ============================================================================

def backtest_parallel_threaded(
    market_data: Dict[str, pd.DataFrame],
    strategy_params: Dict,
    n_workers: int = 4
) -> List[Dict]:
    """并行回测 - 线程池版本"""
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = []

        for symbol, df in market_data.items():
            future = executor.submit(backtest_single_stock, symbol, df, strategy_params)
            futures.append(future)

        results = [f.result() for f in futures]

    return results


# ============================================================================
# 方案3：共享内存（零拷贝）
# ============================================================================

def prepare_shared_memory(market_data: Dict[str, pd.DataFrame]) -> Tuple[shared_memory.SharedMemory, Dict]:
    """准备共享内存"""
    # 将所有数据合并为一个大数组
    symbols = list(market_data.keys())
    n_stocks = len(symbols)
    n_days = len(next(iter(market_data.values())))

    # 创建共享数组：[n_stocks, n_days, 5] (open, high, low, close, volume)
    shape = (n_stocks, n_days, 5)
    dtype = np.float64
    nbytes = int(np.prod(shape) * np.dtype(dtype).itemsize)

    shm = shared_memory.SharedMemory(create=True, size=nbytes)
    shared_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)

    # 填充数据
    for i, symbol in enumerate(symbols):
        df = market_data[symbol]
        shared_array[i, :, 0] = df['open'].values
        shared_array[i, :, 1] = df['high'].values
        shared_array[i, :, 2] = df['low'].values
        shared_array[i, :, 3] = df['close'].values
        shared_array[i, :, 4] = df['volume'].values

    # 返回共享内存和元数据
    metadata = {
        'shm_name': shm.name,
        'shape': shape,
        'dtype': 'float64',  # 使用字符串而不是类型对象
        'symbols': symbols
    }

    return shm, metadata


def backtest_single_stock_shared(stock_idx: int, metadata: Dict, strategy_params: Dict) -> Dict:
    """使用共享内存回测单只股票"""
    # 访问共享内存
    shm = shared_memory.SharedMemory(name=metadata['shm_name'])
    shape = metadata['shape']
    dtype = np.dtype(metadata['dtype'])
    shared_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)

    # 提取该股票的数据
    symbol = metadata['symbols'][stock_idx]
    stock_data = shared_array[stock_idx]

    # 构建DataFrame
    df = pd.DataFrame({
        'date': pd.date_range('2023-01-01', periods=shape[1], freq='D'),
        'open': stock_data[:, 0],
        'high': stock_data[:, 1],
        'low': stock_data[:, 2],
        'close': stock_data[:, 3],
        'volume': stock_data[:, 4]
    })

    # 回测
    result = backtest_single_stock(symbol, df, strategy_params)

    shm.close()
    return result


def backtest_parallel_shared_memory(
    market_data: Dict[str, pd.DataFrame],
    strategy_params: Dict,
    n_workers: int = 4
) -> List[Dict]:
    """并行回测 - 共享内存版本"""
    # 准备共享内存
    shm, metadata = prepare_shared_memory(market_data)

    try:
        # 并行处理
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = []

            for i in range(len(metadata['symbols'])):
                future = executor.submit(backtest_single_stock_shared, i, metadata, strategy_params)
                futures.append(future)

            results = [f.result() for f in futures]

        return results

    finally:
        # 清理共享内存
        shm.close()
        shm.unlink()


# ============================================================================
# 方案4：混合方案（线程池 + 批量处理）
# ============================================================================

def backtest_parallel_hybrid(
    market_data: Dict[str, pd.DataFrame],
    strategy_params: Dict,
    n_workers: int = 4,
    batch_size: int = 10
) -> List[Dict]:
    """并行回测 - 混合方案（线程池 + 批量处理）"""
    # 将股票分批
    items = list(market_data.items())
    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(backtest_batch, batch, strategy_params) for batch in batches]
        batch_results = [f.result() for f in futures]

    # 展平结果
    results = []
    for batch_result in batch_results:
        results.extend(batch_result)

    return results


# ============================================================================
# 性能测试框架
# ============================================================================

def benchmark_method(
    method_name: str,
    method_func,
    market_data: Dict[str, pd.DataFrame],
    strategy_params: Dict,
    n_workers: int = 4,
    batch_size: int = 10,
    repeat: int = 3
) -> Dict:
    """测试单个方法的性能"""
    times = []

    for _ in range(repeat):
        start = time.perf_counter()

        if 'batched' in method_name or 'hybrid' in method_name:
            results = method_func(market_data, strategy_params, n_workers, batch_size)
        elif method_name == 'serial':
            results = method_func(market_data, strategy_params)
        else:
            results = method_func(market_data, strategy_params, n_workers)

        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return {
        'method': method_name,
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'n_stocks': len(market_data),
        'throughput': len(market_data) / np.mean(times)
    }


def run_optimized_benchmarks():
    """运行优化版本的基准测试"""
    print("=" * 80)
    print("并行回测优化方案对比测试")
    print("=" * 80)

    results = {
        'test_name': 'backtest_optimization_comparison',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'cpu_count': multiprocessing.cpu_count(),
        'scenarios': []
    }

    # 测试场景（增加更大规模的测试）
    scenarios = [
        {'n_stocks': 100, 'n_days': 252, 'name': '100股票×1年'},
        {'n_stocks': 500, 'n_days': 252, 'name': '500股票×1年'},
        {'n_stocks': 1000, 'n_days': 252, 'name': '1000股票×1年'},
    ]

    strategy_params = {'fast': 5, 'slow': 20}
    n_workers = min(8, multiprocessing.cpu_count())
    batch_size = 50  # 增加批量大小以提高任务粒度

    # 测试方法
    methods = [
        ('serial', backtest_serial),
        ('parallel_baseline', backtest_parallel_baseline),
        ('parallel_batched', backtest_parallel_batched),
        ('parallel_threaded', backtest_parallel_threaded),
        ('parallel_shared_memory', backtest_parallel_shared_memory),
        ('parallel_hybrid', backtest_parallel_hybrid),
    ]

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
            'methods': []
        }

        # 测试各种方法
        for method_name, method_func in methods:
            print(f"\n[{method_name}]")

            try:
                result = benchmark_method(
                    method_name,
                    method_func,
                    market_data,
                    strategy_params,
                    n_workers=n_workers,
                    batch_size=batch_size,
                    repeat=3
                )

                scenario_result['methods'].append(result)

                print(f"  总耗时: {result['mean_time']:.3f}s ± {result['std_time']:.3f}s")
                print(f"  吞吐量: {result['throughput']:.1f} 股票/秒")

            except Exception as e:
                print(f"  ❌ 测试失败: {e}")
                scenario_result['methods'].append({
                    'method': method_name,
                    'error': str(e)
                })

        # 计算加速比
        serial_time = next(m['mean_time'] for m in scenario_result['methods'] if m['method'] == 'serial')

        print(f"\n{'='*80}")
        print(f"性能对比（相对于串行）")
        print(f"{'='*80}")
        print(f"{'方法':<30} {'耗时':>10} {'加速比':>10} {'效率':>10}")
        print(f"{'-'*80}")

        for method_result in scenario_result['methods']:
            if 'error' in method_result:
                continue

            method_time = method_result['mean_time']
            speedup = serial_time / method_time
            efficiency = speedup / n_workers * 100 if 'parallel' in method_result['method'] else 100

            method_result['speedup'] = speedup
            method_result['efficiency'] = efficiency

            status = "✅" if speedup > 1.0 else "❌"
            print(f"{method_result['method']:<30} {method_time:>9.3f}s {speedup:>9.2f}x {efficiency:>9.1f}% {status}")

        results['scenarios'].append(scenario_result)

    # 保存结果
    output_file = Path(__file__).parent / 'results' / 'benchmark_backtest_optimized.json'
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print(f"测试完成！结果已保存到: {output_file}")
    print(f"{'='*80}")

    return results


def print_summary(results: Dict):
    """打印测试摘要"""
    print("\n" + "=" * 80)
    print("测试摘要")
    print("=" * 80)
    print(f"CPU核心数: {results['cpu_count']}")

    # 找出最佳方案
    for scenario in results['scenarios']:
        print(f"\n{scenario['name']}:")

        best_method = None
        best_speedup = 0

        for method in scenario['methods']:
            if 'error' in method:
                continue

            speedup = method.get('speedup', 0)
            if speedup > best_speedup:
                best_speedup = speedup
                best_method = method['method']

            print(f"  {method['method']:<30} {method['mean_time']:>9.3f}s  {speedup:>6.2f}x")

        if best_method:
            print(f"\n  🏆 最佳方案: {best_method} ({best_speedup:.2f}x)")


def main():
    """主函数"""
    try:
        results = run_optimized_benchmarks()
        print_summary(results)

        return 0
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
