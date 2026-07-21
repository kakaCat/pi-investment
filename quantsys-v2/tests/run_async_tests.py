#!/usr/bin/env python3
"""
异步测试运行脚本

用于快速验证异步数据库基础设施是否正常工作。
包含连接池、基础仓库和K线仓库的基本测试。
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.persistence.database.async_base_repository import init_async_pool, close_async_pool
from adapters.outbound.repositories import AsyncKlineRepository


async def test_connection_pool():
    """测试连接池初始化"""
    print("=" * 60)
    print("测试1: 连接池初始化")
    print("=" * 60)

    try:
        pool = await init_async_pool(min_size=5, max_size=20)
        print(f"✓ 连接池创建成功: min_size={pool.min_size}, max_size={pool.max_size}")

        # 测试简单查询
        result = await pool.fetchval("SELECT 1 + 1")
        print(f"✓ 数据库连接正常: SELECT 1 + 1 = {result}")

        return True
    except Exception as e:
        print(f"✗ 连接池测试失败: {e}")
        return False


async def test_concurrent_queries():
    """测试并发查询"""
    print("\n" + "=" * 60)
    print("测试2: 并发查询性能")
    print("=" * 60)

    try:
        pool = await init_async_pool()

        async def query_task(i):
            return await pool.fetchval(f"SELECT {i} * 2")

        import time
        start = time.time()

        # 并发执行20个查询
        tasks = [query_task(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start

        print(f"✓ 并发执行20个查询")
        print(f"✓ 耗时: {elapsed:.3f}秒")
        print(f"✓ 结果验证: {results[:5]}... (前5个)")

        return True
    except Exception as e:
        print(f"✗ 并发查询测试失败: {e}")
        return False


async def test_kline_repository():
    """测试K线仓库基本功能"""
    print("\n" + "=" * 60)
    print("测试3: K线仓库基本功能")
    print("=" * 60)

    try:
        pool = await init_async_pool()
        repo = AsyncKlineORMRepository(pool=pool)

        # 测试1: 查询最新K线
        print("\n[3.1] 查询最新K线")
        kline = await repo.get_latest_daily_kline("000001.SZ")
        if kline:
            print(f"✓ 股票: {kline['symbol']}")
            print(f"✓ 日期: {kline['trade_date']}")
            print(f"✓ 收盘价: {kline.get('close', 'N/A')}")
        else:
            print("⚠ 未找到数据（数据库可能为空）")

        # 测试2: 查询日期范围
        print("\n[3.2] 查询日期范围")
        date_range = await repo.get_available_date_range("000001.SZ")
        if date_range:
            print(f"✓ 数据范围: {date_range[0]} 至 {date_range[1]}")
        else:
            print("⚠ 未找到数据范围")

        # 测试3: 批量查询
        print("\n[3.3] 批量查询多只股票")
        symbols = ["000001.SZ", "000002.SZ", "600000.SH"]
        import time
        start = time.time()

        klines_dict = await repo.get_daily_klines_batch(
            symbols, "2024-01-01", "2024-01-31"
        )

        elapsed = time.time() - start

        print(f"✓ 查询股票数: {len(symbols)}")
        print(f"✓ 返回数据: {len(klines_dict)} 只股票")
        print(f"✓ 耗时: {elapsed:.3f}秒")

        for symbol, klines in klines_dict.items():
            print(f"  - {symbol}: {len(klines)} 条K线")

        # 测试4: 统计信息
        print("\n[3.4] 查询统计信息")
        stats = await repo.get_kline_stats("000001.SZ", "2024-01-01", "2024-01-31")
        if stats and stats.get('count', 0) > 0:
            print(f"✓ K线数量: {stats['count']}")
            print(f"✓ 最高价: {stats.get('max_high', 'N/A')}")
            print(f"✓ 最低价: {stats.get('min_low', 'N/A')}")
            print(f"✓ 平均收盘价: {stats.get('avg_close', 'N/A')}")
        else:
            print("⚠ 未找到统计数据")

        await repo.close()
        return True

    except Exception as e:
        print(f"✗ K线仓库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_batch_query_performance():
    """测试批量查询性能（100只股票）"""
    print("\n" + "=" * 60)
    print("测试4: 批量查询性能测试（100只股票）")
    print("=" * 60)

    try:
        pool = await init_async_pool(min_size=10, max_size=50)
        repo = AsyncKlineORMRepository(pool=pool)

        # 生成100只股票代码
        symbols = [f"{str(i).zfill(6)}.SZ" for i in range(1, 101)]

        import time
        start = time.time()

        klines_dict = await repo.get_daily_klines_batch(
            symbols, "2024-01-01", "2024-01-31"
        )

        elapsed = time.time() - start

        total_klines = sum(len(klines) for klines in klines_dict.values())

        print(f"✓ 查询股票数: {len(symbols)}")
        print(f"✓ 返回股票数: {len(klines_dict)}")
        print(f"✓ 总K线数: {total_klines}")
        print(f"✓ 耗时: {elapsed:.3f}秒")
        print(f"✓ 平均每只股票: {elapsed/len(symbols)*1000:.2f}毫秒")

        if elapsed < 5.0:
            print(f"✓ 性能测试通过（<5秒）")
        else:
            print(f"⚠ 性能需要优化（>{elapsed:.1f}秒）")

        await repo.close()
        return True

    except Exception as e:
        print(f"✗ 批量查询性能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("异步数据库基础设施测试")
    print("=" * 60)
    print()

    results = []

    # 运行所有测试
    results.append(("连接池初始化", await test_connection_pool()))
    results.append(("并发查询", await test_concurrent_queries()))
    results.append(("K线仓库", await test_kline_repository()))
    results.append(("批量查询性能", await test_batch_query_performance()))

    # 清理
    await close_async_pool()

    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")

    print()
    print(f"总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！异步数据库基础设施工作正常。")
        return 0
    else:
        print(f"\n⚠ {total - passed} 个测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
