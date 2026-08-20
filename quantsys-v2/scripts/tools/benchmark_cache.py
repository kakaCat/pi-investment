#!/usr/bin/env python3
"""
缓存性能基准测试

对比有缓存和无缓存的性能差异。
"""
import sys
import time
from pathlib import Path


from infrastructure.config import create_cache_service
from infrastructure.cache import CacheService


def benchmark_write(cache: CacheService, count: int = 1000):
    """测试写入性能"""
    start = time.perf_counter()
    for i in range(count):
        cache.set('benchmark', f'key{i}', {'data': f'value{i}', 'index': i}, ttl=300)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_read(cache: CacheService, count: int = 1000):
    """测试读取性能"""
    # 预先写入数据
    for i in range(count):
        cache.set('benchmark', f'key{i}', {'data': f'value{i}', 'index': i}, ttl=300)

    start = time.perf_counter()
    for i in range(count):
        cache.get('benchmark', f'key{i}')
    elapsed = time.perf_counter() - start
    return elapsed


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

    return hits / count


def simulate_data_access(cache: CacheService, with_cache: bool = True):
    """模拟真实数据访问场景"""
    symbols = [f'00000{i}.SZ' for i in range(1, 11)]  # 10只股票

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
    return elapsed


def main():
    print("=" * 60)
    print("Redis缓存性能基准测试")
    print("=" * 60)

    # 测试内存缓存
    print("\n【内存缓存】")
    memory_cache = create_cache_service(use_redis=False)

    write_time = benchmark_write(memory_cache, 1000)
    print(f"写入1000条: {write_time*1000:.2f}ms ({1000/write_time:.0f} ops/s)")

    read_time = benchmark_read(memory_cache, 1000)
    print(f"读取1000条: {read_time*1000:.2f}ms ({1000/read_time:.0f} ops/s)")

    hit_rate = benchmark_hit_rate(memory_cache, 1000)
    print(f"缓存命中率: {hit_rate*100:.1f}%")

    # 测试Redis缓存（如果可用）
    print("\n【Redis缓存】")
    redis_cache = create_cache_service(use_redis=True)
    stats = redis_cache.get_stats()

    if stats['backend'] == 'redis':
        write_time = benchmark_write(redis_cache, 1000)
        print(f"写入1000条: {write_time*1000:.2f}ms ({1000/write_time:.0f} ops/s)")

        read_time = benchmark_read(redis_cache, 1000)
        print(f"读取1000条: {read_time*1000:.2f}ms ({1000/read_time:.0f} ops/s)")

        hit_rate = benchmark_hit_rate(redis_cache, 1000)
        print(f"缓存命中率: {hit_rate*100:.1f}%")
    else:
        print("Redis不可用，跳过测试")

    # 模拟真实场景
    print("\n【真实场景模拟】")
    print("场景: 100次查询 × 10只股票 = 1000次数据访问")

    # 无缓存
    print("\n无缓存:")
    no_cache = create_cache_service(use_redis=False)
    no_cache_time = simulate_data_access(no_cache, with_cache=False)
    print(f"总耗时: {no_cache_time:.2f}秒")

    # 有缓存
    print("\n有缓存:")
    with_cache = create_cache_service(use_redis=False)
    with_cache_time = simulate_data_access(with_cache, with_cache=True)
    print(f"总耗时: {with_cache_time:.2f}秒")

    # 性能提升
    speedup = no_cache_time / with_cache_time
    print(f"\n性能提升: {speedup:.1f}x")
    print(f"时间节省: {(1 - 1/speedup)*100:.1f}%")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
