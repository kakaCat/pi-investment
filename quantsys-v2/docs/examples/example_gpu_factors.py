"""
GPU加速因子计算完整示例

演示如何使用GPU加速技术指标计算：
1. GPU环境检测
2. 单个因子计算对比
3. 批量因子计算
4. 性能基准测试
5. 大规模数据处理
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import numpy as np
import pandas as pd
import time
from domain.quantlib.gpu_acceleration.gpu_factors import GPUFactorCalculator, GPU_AVAILABLE


def check_gpu_environment():
    """检测GPU环境"""
    print("=" * 60)
    print("步骤1: GPU环境检测")
    print("=" * 60)

    if GPU_AVAILABLE:
        import cupy as cp
        print("\n✓ GPU加速可用")
        print(f"  CuPy版本: {cp.__version__}")

        # 获取GPU信息
        try:
            device = cp.cuda.Device()
            print(f"  GPU设备: {device.compute_capability}")
            mem_info = cp.cuda.runtime.memGetInfo()
            print(f"  显存: {mem_info[1] / 1024**3:.2f} GB")
            print(f"  可用显存: {mem_info[0] / 1024**3:.2f} GB")
        except:
            print("  无法获取详细GPU信息")
    else:
        print("\n✗ GPU加速不可用")
        print("  将使用CPU计算")
        print("\n安装GPU支持:")
        print("  pip install cupy-cuda11x  # CUDA 11.x")
        print("  pip install cupy-cuda12x  # CUDA 12.x")


def single_factor_comparison():
    """单个因子计算对比"""
    print("\n" + "=" * 60)
    print("步骤2: 单个因子计算对比 (CPU vs GPU)")
    print("=" * 60)

    # 准备测试数据
    np.random.seed(42)
    n_samples = 10000
    prices = 100 + np.cumsum(np.random.randn(n_samples) * 0.5)

    print(f"\n数据规模: {n_samples} 个数据点")

    # CPU计算
    cpu_calculator = GPUFactorCalculator(use_gpu=False)

    print("\nCPU计算:")
    cpu_results = {}

    start = time.time()
    cpu_results['sma'] = cpu_calculator.calculate_sma(prices, 20)
    cpu_time_sma = time.time() - start
    print(f"  SMA(20): {cpu_time_sma*1000:.2f}ms")

    start = time.time()
    cpu_results['ema'] = cpu_calculator.calculate_ema(prices, 12)
    cpu_time_ema = time.time() - start
    print(f"  EMA(12): {cpu_time_ema*1000:.2f}ms")

    start = time.time()
    cpu_results['rsi'] = cpu_calculator.calculate_rsi(prices, 14)
    cpu_time_rsi = time.time() - start
    print(f"  RSI(14): {cpu_time_rsi*1000:.2f}ms")

    start = time.time()
    cpu_results['macd'] = cpu_calculator.calculate_macd(prices)
    cpu_time_macd = time.time() - start
    print(f"  MACD: {cpu_time_macd*1000:.2f}ms")

    cpu_total = cpu_time_sma + cpu_time_ema + cpu_time_rsi + cpu_time_macd
    print(f"  总计: {cpu_total*1000:.2f}ms")

    # GPU计算
    if GPU_AVAILABLE:
        gpu_calculator = GPUFactorCalculator(use_gpu=True)

        print("\nGPU计算:")
        gpu_results = {}

        start = time.time()
        gpu_results['sma'] = gpu_calculator.calculate_sma(prices, 20)
        gpu_time_sma = time.time() - start
        print(f"  SMA(20): {gpu_time_sma*1000:.2f}ms")

        start = time.time()
        gpu_results['ema'] = gpu_calculator.calculate_ema(prices, 12)
        gpu_time_ema = time.time() - start
        print(f"  EMA(12): {gpu_time_ema*1000:.2f}ms")

        start = time.time()
        gpu_results['rsi'] = gpu_calculator.calculate_rsi(prices, 14)
        gpu_time_rsi = time.time() - start
        print(f"  RSI(14): {gpu_time_rsi*1000:.2f}ms")

        start = time.time()
        gpu_results['macd'] = gpu_calculator.calculate_macd(prices)
        gpu_time_macd = time.time() - start
        print(f"  MACD: {gpu_time_macd*1000:.2f}ms")

        gpu_total = gpu_time_sma + gpu_time_ema + gpu_time_rsi + gpu_time_macd
        print(f"  总计: {gpu_total*1000:.2f}ms")

        # 加速比
        print(f"\n加速比:")
        print(f"  SMA: {cpu_time_sma/gpu_time_sma:.2f}x")
        print(f"  EMA: {cpu_time_ema/gpu_time_ema:.2f}x")
        print(f"  RSI: {cpu_time_rsi/gpu_time_rsi:.2f}x")
        print(f"  MACD: {cpu_time_macd/gpu_time_macd:.2f}x")
        print(f"  总体: {cpu_total/gpu_total:.2f}x")

        # 验证结果一致性
        print(f"\n结果一致性验证:")
        for key in cpu_results:
            if isinstance(cpu_results[key], dict):
                # MACD返回字典
                for subkey in cpu_results[key]:
                    diff = np.nanmean(np.abs(cpu_results[key][subkey] - gpu_results[key][subkey]))
                    print(f"  {key}.{subkey} 差异: {diff:.8f}")
            else:
                diff = np.nanmean(np.abs(cpu_results[key] - gpu_results[key]))
                print(f"  {key} 差异: {diff:.8f}")
    else:
        print("\nGPU不可用，跳过GPU计算")


def batch_factor_calculation():
    """批量因子计算"""
    print("\n" + "=" * 60)
    print("步骤3: 批量因子计算")
    print("=" * 60)

    # 准备OHLC数据
    np.random.seed(42)
    n = 5000

    base_price = 100
    returns = np.random.randn(n) * 0.02
    close = base_price * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(np.random.randn(n) * 0.01))
    low = close * (1 - np.abs(np.random.randn(n) * 0.01))
    volume = np.random.randint(1000000, 10000000, n)

    df = pd.DataFrame({
        'close': close,
        'high': high,
        'low': low,
        'volume': volume
    })

    print(f"\n数据规模: {len(df)} 行")
    print(f"数据范围: {df.index[0]} 到 {df.index[-1]}")

    # 要计算的因子
    factors = ['sma_20', 'ema_12', 'rsi_14', 'macd', 'bollinger', 'atr_14']
    print(f"\n计算因子: {factors}")

    # 使用GPU计算（如果可用）
    calculator = GPUFactorCalculator(use_gpu=GPU_AVAILABLE)

    start = time.time()
    result = calculator.batch_calculate_factors(df, factors)
    elapsed = time.time() - start

    print(f"\n计算完成！")
    print(f"  耗时: {elapsed*1000:.2f}ms")
    print(f"  平均每个因子: {elapsed*1000/len(factors):.2f}ms")

    print(f"\n结果数据形状: {result.shape}")
    print(f"新增列: {[col for col in result.columns if col not in df.columns]}")

    print(f"\n最新数据预览:")
    print(result.tail())

    # 统计信息
    print(f"\n因子统计:")
    for col in result.columns:
        if col not in df.columns:
            print(f"  {col}:")
            print(f"    均值: {result[col].mean():.4f}")
            print(f"    标准差: {result[col].std():.4f}")
            print(f"    缺失值: {result[col].isna().sum()}")


def performance_benchmark():
    """性能基准测试"""
    print("\n" + "=" * 60)
    print("步骤4: 性能基准测试")
    print("=" * 60)

    data_sizes = [1000, 5000, 10000, 50000]
    factors = ['sma_20', 'ema_12', 'rsi_14', 'macd']

    print(f"\n测试配置:")
    print(f"  数据规模: {data_sizes}")
    print(f"  因子数量: {len(factors)}")

    results = []

    for n in data_sizes:
        # 生成数据
        np.random.seed(42)
        df = pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(n) * 0.5),
            'high': 100 + np.cumsum(np.random.randn(n) * 0.5) + 1,
            'low': 100 + np.cumsum(np.random.randn(n) * 0.5) - 1,
            'volume': np.random.randint(1000, 10000, n)
        })

        # CPU计算
        cpu_calculator = GPUFactorCalculator(use_gpu=False)
        start = time.time()
        cpu_calculator.batch_calculate_factors(df, factors)
        cpu_time = time.time() - start

        result = {
            'data_size': n,
            'cpu_time': cpu_time * 1000,
            'gpu_time': None,
            'speedup': None
        }

        # GPU计算
        if GPU_AVAILABLE:
            gpu_calculator = GPUFactorCalculator(use_gpu=True)
            start = time.time()
            gpu_calculator.batch_calculate_factors(df, factors)
            gpu_time = time.time() - start

            result['gpu_time'] = gpu_time * 1000
            result['speedup'] = cpu_time / gpu_time

        results.append(result)

    # 显示结果
    results_df = pd.DataFrame(results)
    print("\n性能测试结果:")
    print(results_df.to_string(index=False))

    if GPU_AVAILABLE:
        print(f"\n平均加速比: {results_df['speedup'].mean():.2f}x")
        print(f"最大加速比: {results_df['speedup'].max():.2f}x")


def large_scale_processing():
    """大规模数据处理"""
    print("\n" + "=" * 60)
    print("步骤5: 大规模数据处理示例")
    print("=" * 60)

    print("\n场景: 计算100只股票的技术指标")

    n_stocks = 100
    n_days = 1000
    factors = ['sma_20', 'ema_12', 'rsi_14', 'macd', 'bollinger']

    print(f"  股票数量: {n_stocks}")
    print(f"  交易日数: {n_days}")
    print(f"  因子数量: {len(factors)}")
    print(f"  总计算量: {n_stocks * n_days * len(factors)} 个数据点")

    calculator = GPUFactorCalculator(use_gpu=GPU_AVAILABLE)

    all_results = []
    start_total = time.time()

    for i in range(n_stocks):
        # 生成股票数据
        np.random.seed(42 + i)
        df = pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(n_days) * 0.5),
            'high': 100 + np.cumsum(np.random.randn(n_days) * 0.5) + 1,
            'low': 100 + np.cumsum(np.random.randn(n_days) * 0.5) - 1,
            'volume': np.random.randint(1000, 10000, n_days)
        })

        # 计算因子
        result = calculator.batch_calculate_factors(df, factors)
        result['symbol'] = f'stock_{i:03d}'
        all_results.append(result)

        if (i + 1) % 20 == 0:
            print(f"  进度: {i+1}/{n_stocks}")

    total_time = time.time() - start_total

    print(f"\n处理完成！")
    print(f"  总耗时: {total_time:.2f}秒")
    print(f"  平均每只股票: {total_time/n_stocks*1000:.2f}ms")
    print(f"  吞吐量: {n_stocks/total_time:.2f} 股票/秒")

    # 合并结果
    combined_df = pd.concat(all_results, ignore_index=True)
    print(f"\n结果数据集:")
    print(f"  总行数: {len(combined_df)}")
    print(f"  总列数: {len(combined_df.columns)}")
    print(f"  内存占用: {combined_df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")


def practical_tips():
    """实用技巧"""
    print("\n" + "=" * 60)
    print("实用技巧")
    print("=" * 60)

    print("\n1. 何时使用GPU加速？")
    print("  ✓ 数据量大 (>10000个数据点)")
    print("  ✓ 需要计算多个因子")
    print("  ✓ 需要频繁重复计算")
    print("  ✗ 数据量小 (<1000个数据点)")
    print("  ✗ 只计算单个简单因子")

    print("\n2. 性能优化建议:")
    print("  - 批量处理多个股票")
    print("  - 复用计算器对象")
    print("  - 避免频繁CPU-GPU数据传输")
    print("  - 使用合适的数据类型 (float32 vs float64)")

    print("\n3. 内存管理:")
    print("  - 监控GPU显存使用")
    print("  - 分批处理超大数据集")
    print("  - 及时释放不需要的GPU数组")

    print("\n4. 错误处理:")
    print("  - 检测GPU可用性")
    print("  - 提供CPU回退方案")
    print("  - 处理显存不足异常")

    # 示例代码
    print("\n5. 推荐使用模式:")
    print("""
    # 自动选择最佳计算方式
    calculator = GPUFactorCalculator(use_gpu=True)  # 自动检测GPU

    # 批量计算
    factors = ['sma_20', 'ema_12', 'rsi_14', 'macd']
    result = calculator.batch_calculate_factors(df, factors)

    # 对于小数据集，GPU可能更慢
    if len(df) < 1000:
        calculator = GPUFactorCalculator(use_gpu=False)
    """)


def main():
    """主函数"""
    print("GPU加速因子计算完整示例")
    print("=" * 60)

    # 1. 检测GPU环境
    check_gpu_environment()

    # 2. 单个因子对比
    single_factor_comparison()

    # 3. 批量因子计算
    batch_factor_calculation()

    # 4. 性能基准测试
    performance_benchmark()

    # 5. 大规模数据处理
    large_scale_processing()

    # 6. 实用技巧
    practical_tips()

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)
    print("\n关键要点:")
    print("1. GPU加速适合大规模数据计算")
    print("2. 小数据集使用CPU可能更快")
    print("3. 批量计算可以最大化GPU利用率")
    print("4. 框架自动处理CPU/GPU切换")
    print("5. 性能提升取决于数据规模和计算复杂度")


if __name__ == "__main__":
    main()
