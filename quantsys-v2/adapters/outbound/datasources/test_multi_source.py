"""Test multi-source failover with all data sources."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.outbound.datasources.manager import DataSourceManager


def test_multi_source_failover():
    """Test automatic failover across multiple data sources."""
    print("=" * 60)
    print("测试多数据源自动 Failover")
    print("=" * 60)

    manager = DataSourceManager()

    # Test 1: Get real-time quotes
    print("\n1. 获取实时行情（会尝试多个数据源）...")
    symbols = ["600000.SH", "000001.SZ"]
    result = manager.get_realtime_quote(symbols)

    if result.success:
        print(f"✓ 成功获取 {len(result.data)} 个股票行情:")
        for symbol, quote in result.data.items():
            print(f"  {symbol}: {quote.get('name')} - ¥{quote.get('price')} ({quote.get('change_pct')}%)")
    else:
        print(f"✗ 失败: {result.error}")

    # Test 2: Check which source was used
    print("\n2. 查看数据源统计...")
    stats = manager.get_stats()

    print(f"总请求数: {stats['total_requests']}")
    print(f"缓存命中: {stats['cache_hits']}")
    print(f"缓存未命中: {stats['cache_misses']}")

    print("\n各数据源成功率:")
    for source_name in stats['source_success']:
        success = stats['source_success'][source_name]
        failures = stats['source_failures'][source_name]
        total = success + failures
        if total > 0:
            rate = success / total * 100
            print(f"  {source_name}: {success}/{total} ({rate:.1f}%)")

    # Test 3: Test cache hit
    print("\n3. 测试缓存（再次请求相同数据）...")
    result2 = manager.get_realtime_quote(symbols)

    stats2 = manager.get_stats()
    if stats2['cache_hits'] > stats['cache_hits']:
        print(f"✓ 缓存命中! 缓存命中次数: {stats2['cache_hits']}")
    else:
        print(f"✗ 未命中缓存")

    # Test 4: Circuit breaker status
    print("\n4. 熔断器状态:")
    for name, state in stats2['circuit_breakers'].items():
        status = "🟢" if state['state'] == 'closed' else "🔴"
        print(f"  {status} {name}: {state['state']} (失败: {state['failure_count']})")

    # Test 5: Get stock info
    print("\n5. 获取股票信息...")
    result = manager.get_stock_info("600000.SH")
    if result.success:
        print(f"✓ {result.data}")
    else:
        print(f"✗ {result.error}")


if __name__ == "__main__":
    try:
        test_multi_source_failover()

        print("\n" + "=" * 60)
        print("✓ 所有测试完成!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
