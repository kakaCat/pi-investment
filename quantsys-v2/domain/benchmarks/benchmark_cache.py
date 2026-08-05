#!/usr/bin/env python3
"""
缓存性能基准测试

测试场景：
- Redis缓存 vs 内存缓存
- 缓存命中 vs 未命中
- 不同数据大小
- 真实场景模拟

架构豁免说明（2026-08-05）：
本文件是可独立执行的基准测试脚本（__main__ 入口），不是 domain 业务逻辑，
历史上误置在 domain/benchmarks/ 下（同目录 benchmark_ml.py 等同样引用外层）。
脚本本身就是 composition root，其职责正是装配并压测 infrastructure 的
CacheService，因此对 infrastructure.config / infrastructure.cache 的 import
予以豁免。真正的修复方向是把整个 domain/benchmarks/ 脚本目录迁出 domain
（如顶层 benchmarks/），需同步调整 application/services/benchmark_service.py
的 benchmarks_dir 解析（当前指向 application/benchmarks，已是断链状态），
属于独立工作线，本次不做。
"""
import sys
import time
from pathlib import Path
import numpy as np
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.config import create_cache_service
from infrastructure.cache import CacheService


def benchmark_write(cache: CacheService, count: int = 1000, repeat: int = 3):
    """测试写入性能"""
    times = []

    for _ in range(repeat):
        start = time.perf_counter()
        for i in range(count):
            cache.set('benchmark', f'key{i}', {'data': f'value{i}', 'index': i}, ttl=300)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return {
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'ops_per_sec': count / np.mean(times)
    }


def benchmark_read(cache: CacheService, count: int = 1000, repeat: int = 3):
    """测试读取性能"""
    # 预先写入数据
    for i in range(count):
        cache.set('benchmark', f'key{i}', {'data': f'value{i}', 'index': i}, ttl=300)

    times = []

    for _ in range(repeat):
        start = time.perf_counter()
        for i in range(count):
            cache.get('benchmark', f'key{i}')
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return {
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'ops_per_sec': count / np.mean(times)
    }


def benchmark_hit_rate(cache: CacheService, count: int = 1000):
    """测试缓存命中率"""
    # 写入一半数据
    for i in range(count // 2):
        cache.set('benchmark', f'key{i}', f'value{i}', ttl=300)

    # 读取所有数据（一半命中，一半未命中）
    hits = 0
    misses = 0
    for i in range(count):
        result = cache.get('benchmark', f'key{i}')
        if result:
            hits += 1
        else:
            misses += 1

    return {
        'hits': hits,
        'misses': misses,
        'hit_rate': hits / count
    }


def simulate_data_access(cache: CacheService, with_cache: bool = True, repeat: int = 3):
    """模拟真实数据访问场景"""
    symbols = [f'00000{i}.SZ' for i in range(1, 11)]  # 10只股票

    times = []

    for _ in range(repeat):
        start = time.perf_counter()

        for _ in range(100):  # 100次查询
            for symbol in symbols:
                if with_cache:
                    # 先查缓存
                    cached = cache.get('klines', f'latest:{symbol}')
                    if not cached:
                        # 模拟数据库查询（耗时操作）
                        time.sleep(0.001)  # 1ms
                        data = {'symbol': symbol, 'close': 100.0}
                        cache.set('klines', f'latest:{symbol}', data, ttl=60)
                else:
                    # 直接查询数据库
                    time.sleep(0.001)  # 1ms
                    data = {'symbol': symbol, 'close': 100.0}

        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return {
        'mean_time': np.mean(times),
        'std_time': np.std(times)
    }


def run_cache_benchmarks():
    """运行缓存基准测试"""
    print("=" * 80)
    print("缓存性能基准测试")
    print("=" * 80)

    results = {
        'test_name': 'cache_performance',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'backends': []
    }

    # 测试内存缓存
    print("\n【内存缓存】")
    memory_cache = create_cache_service(use_redis=False)

    memory_result = {
        'backend': 'memory',
        'write': {},
        'read': {},
        'hit_rate': {}
    }

    write_result = benchmark_write(memory_cache, 1000, repeat=3)
    memory_result['write'] = write_result
    print(f"写入1000条: {write_result['mean_time']*1000:.2f}ms ± {write_result['std_time']*1000:.2f}ms ({write_result['ops_per_sec']:.0f} ops/s)")

    read_result = benchmark_read(memory_cache, 1000, repeat=3)
    memory_result['read'] = read_result
    print(f"读取1000条: {read_result['mean_time']*1000:.2f}ms ± {read_result['std_time']*1000:.2f}ms ({read_result['ops_per_sec']:.0f} ops/s)")

    hit_rate_result = benchmark_hit_rate(memory_cache, 1000)
    memory_result['hit_rate'] = hit_rate_result
    print(f"缓存命中率: {hit_rate_result['hit_rate']*100:.1f}% (命中:{hit_rate_result['hits']}, 未命中:{hit_rate_result['misses']})")

    results['backends'].append(memory_result)

    # 测试Redis缓存（如果可用）
    print("\n【Redis缓存】")
    redis_cache = create_cache_service(use_redis=True)
    stats = redis_cache.get_stats()

    if stats['backend'] == 'redis':
        redis_result = {
            'backend': 'redis',
            'write': {},
            'read': {},
            'hit_rate': {}
        }

        write_result = benchmark_write(redis_cache, 1000, repeat=3)
        redis_result['write'] = write_result
        print(f"写入1000条: {write_result['mean_time']*1000:.2f}ms ± {write_result['std_time']*1000:.2f}ms ({write_result['ops_per_sec']:.0f} ops/s)")

        read_result = benchmark_read(redis_cache, 1000, repeat=3)
        redis_result['read'] = read_result
        print(f"读取1000条: {read_result['mean_time']*1000:.2f}ms ± {read_result['std_time']*1000:.2f}ms ({read_result['ops_per_sec']:.0f} ops/s)")

        hit_rate_result = benchmark_hit_rate(redis_cache, 1000)
        redis_result['hit_rate'] = hit_rate_result
        print(f"缓存命中率: {hit_rate_result['hit_rate']*100:.1f}% (命中:{hit_rate_result['hits']}, 未命中:{hit_rate_result['misses']})")

        results['backends'].append(redis_result)
    else:
        print("Redis不可用，跳过测试")

    # 模拟真实场景
    print("\n【真实场景模拟】")
    print("场景: 100次查询 × 10只股票 = 1000次数据访问")

    real_scenario = {}

    # 无缓存
    print("\n无缓存:")
    no_cache = create_cache_service(use_redis=False)
    no_cache_result = simulate_data_access(no_cache, with_cache=False, repeat=3)
    real_scenario['no_cache_time'] = no_cache_result['mean_time']
    real_scenario['no_cache_std'] = no_cache_result['std_time']
    print(f"总耗时: {no_cache_result['mean_time']:.2f}s ± {no_cache_result['std_time']:.2f}s")

    # 有缓存
    print("\n有缓存:")
    with_cache = create_cache_service(use_redis=False)
    with_cache_result = simulate_data_access(with_cache, with_cache=True, repeat=3)
    real_scenario['with_cache_time'] = with_cache_result['mean_time']
    real_scenario['with_cache_std'] = with_cache_result['std_time']
    print(f"总耗时: {with_cache_result['mean_time']:.2f}s ± {with_cache_result['std_time']:.2f}s")

    # 性能提升
    speedup = no_cache_result['mean_time'] / with_cache_result['mean_time']
    real_scenario['speedup'] = speedup
    print(f"\n性能提升: {speedup:.1f}x")
    print(f"时间节省: {(1 - 1/speedup)*100:.1f}%")

    results['real_scenario'] = real_scenario

    # 保存结果
    output_file = Path(__file__).parent / 'results' / 'benchmark_cache.json'
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"测试完成！结果已保存到: {output_file}")
    print("=" * 80)

    return results


def main():
    """主函数"""
    try:
        results = run_cache_benchmarks()

        # 打印汇总
        print("\n" + "=" * 80)
        print("测试汇总")
        print("=" * 80)

        for backend in results['backends']:
            print(f"\n{backend['backend'].upper()}:")
            print(f"  写入: {backend['write']['ops_per_sec']:.0f} ops/s")
            print(f"  读取: {backend['read']['ops_per_sec']:.0f} ops/s")
            print(f"  命中率: {backend['hit_rate']['hit_rate']*100:.1f}%")

        if 'real_scenario' in results:
            scenario = results['real_scenario']
            print(f"\n真实场景:")
            print(f"  无缓存: {scenario['no_cache_time']:.2f}s")
            print(f"  有缓存: {scenario['with_cache_time']:.2f}s")
            print(f"  加速比: {scenario['speedup']:.1f}x")

        return 0
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
