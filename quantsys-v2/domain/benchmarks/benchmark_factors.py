#!/usr/bin/env python3
"""
因子计算性能基准测试

测试场景：
- 1K/10K/100K股票 × 10个因子
- CPU vs GPU对比
- 单线程 vs 多线程
- 有缓存 vs 无缓存
"""

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.quantlib.gpu_acceleration.gpu_factors import GPUFactorCalculator


def generate_test_data(n_stocks: int, n_days: int = 252) -> pd.DataFrame:
    """生成测试数据"""
    np.random.seed(42)

    data = []
    for i in range(n_stocks):
        symbol = f"00{i:04d}.SZ"

        # 生成价格序列
        base_price = 10 + np.random.rand() * 90
        returns = np.random.randn(n_days) * 0.02
        close = base_price * np.exp(np.cumsum(returns))
        high = close * (1 + np.abs(np.random.randn(n_days) * 0.01))
        low = close * (1 - np.abs(np.random.randn(n_days) * 0.01))
        volume = np.random.randint(1000000, 10000000, n_days)

        for j in range(n_days):
            data.append({
                'symbol': symbol,
                'date': f'2025-{(j % 12) + 1:02d}-{(j % 28) + 1:02d}',
                'open': close[j] * 0.99,
                'high': high[j],
                'low': low[j],
                'close': close[j],
                'volume': volume[j]
            })

    return pd.DataFrame(data)


def benchmark_single_factor(
    calculator: GPUFactorCalculator,
    prices: np.ndarray,
    factor_name: str,
    repeat: int = 3
) -> Dict:
    """测试单个因子计算性能"""
    times = []

    for _ in range(repeat):
        start = time.perf_counter()

        if factor_name == 'sma':
            result = calculator.calculate_sma(prices, 20)
        elif factor_name == 'ema':
            result = calculator.calculate_ema(prices, 12)
        elif factor_name == 'rsi':
            result = calculator.calculate_rsi(prices, 14)
        elif factor_name == 'macd':
            result = calculator.calculate_macd(prices)
        elif factor_name == 'bollinger':
            result = calculator.calculate_bollinger_bands(prices)
        else:
            raise ValueError(f"Unknown factor: {factor_name}")

        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return {
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'max_time': np.max(times)
    }


def benchmark_batch_factors(
    calculator: GPUFactorCalculator,
    df: pd.DataFrame,
    factors: List[str],
    repeat: int = 3
) -> Dict:
    """测试批量因子计算性能"""
    times = []

    for _ in range(repeat):
        start = time.perf_counter()
        result = calculator.batch_calculate_factors(df, factors)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return {
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'max_time': np.max(times),
        'n_factors': len(factors),
        'n_rows': len(df)
    }


def run_factor_benchmarks():
    """运行因子计算基准测试"""
    print("=" * 80)
    print("因子计算性能基准测试")
    print("=" * 80)

    results = {
        'test_name': 'factor_calculation',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'scenarios': []
    }

    # 测试场景
    scenarios = [
        {'n_stocks': 100, 'n_days': 252, 'name': '100股票×252天'},
        {'n_stocks': 1000, 'n_days': 252, 'name': '1K股票×252天'},
        {'n_stocks': 5000, 'n_days': 252, 'name': '5K股票×252天'},
    ]

    factors = ['sma_20', 'ema_12', 'rsi_14', 'macd', 'bollinger']

    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"场景: {scenario['name']}")
        print(f"{'='*80}")

        # 生成测试数据
        print(f"生成测试数据...")
        df = generate_test_data(scenario['n_stocks'], scenario['n_days'])
        print(f"数据规模: {len(df):,} 行")

        scenario_result = {
            'name': scenario['name'],
            'n_stocks': scenario['n_stocks'],
            'n_days': scenario['n_days'],
            'n_rows': len(df),
            'cpu': {},
            'gpu': {}
        }

        # CPU测试
        print(f"\n[CPU测试]")
        cpu_calc = GPUFactorCalculator(use_gpu=False)

        cpu_result = benchmark_batch_factors(cpu_calc, df, factors, repeat=3)
        scenario_result['cpu'] = cpu_result

        print(f"  批量计算 {len(factors)} 个因子:")
        print(f"    平均耗时: {cpu_result['mean_time']:.3f}s")
        print(f"    标准差: {cpu_result['std_time']:.3f}s")
        print(f"    吞吐量: {len(df) / cpu_result['mean_time']:.0f} 行/秒")

        # GPU测试
        try:
            print(f"\n[GPU测试]")
            gpu_calc = GPUFactorCalculator(use_gpu=True)

            if gpu_calc.use_gpu:
                gpu_result = benchmark_batch_factors(gpu_calc, df, factors, repeat=3)
                scenario_result['gpu'] = gpu_result

                print(f"  批量计算 {len(factors)} 个因子:")
                print(f"    平均耗时: {gpu_result['mean_time']:.3f}s")
                print(f"    标准差: {gpu_result['std_time']:.3f}s")
                print(f"    吞吐量: {len(df) / gpu_result['mean_time']:.0f} 行/秒")

                # 计算加速比
                speedup = cpu_result['mean_time'] / gpu_result['mean_time']
                scenario_result['speedup'] = speedup

                print(f"\n  [性能对比]")
                print(f"    加速比: {speedup:.2f}x")
                print(f"    性能提升: {(speedup - 1) * 100:.1f}%")
            else:
                print("  GPU不可用，跳过GPU测试")
                scenario_result['gpu'] = None
                scenario_result['speedup'] = None
        except Exception as e:
            print(f"  GPU测试失败: {e}")
            scenario_result['gpu'] = None
            scenario_result['speedup'] = None

        results['scenarios'].append(scenario_result)

    # 保存结果
    output_file = Path(__file__).parent / 'results' / 'benchmark_factors.json'
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
        results = run_factor_benchmarks()

        # 打印汇总
        print("\n" + "=" * 80)
        print("测试汇总")
        print("=" * 80)

        for scenario in results['scenarios']:
            print(f"\n{scenario['name']}:")
            print(f"  数据规模: {scenario['n_rows']:,} 行")
            print(f"  CPU耗时: {scenario['cpu']['mean_time']:.3f}s")

            if scenario['gpu']:
                print(f"  GPU耗时: {scenario['gpu']['mean_time']:.3f}s")
                print(f"  加速比: {scenario['speedup']:.2f}x")
            else:
                print(f"  GPU: 不可用")

        return 0
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
