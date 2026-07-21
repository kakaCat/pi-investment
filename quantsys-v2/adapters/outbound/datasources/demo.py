"""Demo script for DataSourceManager.

Demonstrates:
- Automatic failover between data sources
- Circuit breaker functionality
- Caching
- Statistics tracking
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.outbound.datasources.manager import DataSourceManager


def demo_basic_usage():
    """Demo basic data source manager usage."""
    print("=" * 60)
    print("Demo 1: Basic Usage")
    print("=" * 60)

    manager = DataSourceManager()

    # Get stock info
    print("\n1. Getting stock info for 600000.SH...")
    result = manager.get_stock_info("600000.SH")

    if result.success:
        print(f"✓ Success: {result.data}")
    else:
        print(f"✗ Failed: {result.error}")

    # Get klines
    print("\n2. Getting klines for 600000.SH...")
    result = manager.get_klines("600000.SH", period="daily", start_date="20240101", end_date="20240110")

    if result.success:
        print(f"✓ Success: Got {len(result.data)} klines")
        if result.data:
            print(f"   First: {result.data[0]}")
    else:
        print(f"✗ Failed: {result.error}")


def demo_caching():
    """Demo caching functionality."""
    print("\n" + "=" * 60)
    print("Demo 2: Caching")
    print("=" * 60)

    manager = DataSourceManager()

    # First call - cache miss
    print("\n1. First call (cache miss)...")
    result1 = manager.get_stock_info("600000.SH")
    stats1 = manager.get_stats()
    print(f"   Cache misses: {stats1['cache_misses']}")
    print(f"   Cache hits: {stats1['cache_hits']}")

    # Second call - cache hit
    print("\n2. Second call (cache hit)...")
    result2 = manager.get_stock_info("600000.SH")
    stats2 = manager.get_stats()
    print(f"   Cache misses: {stats2['cache_misses']}")
    print(f"   Cache hits: {stats2['cache_hits']}")

    print(f"\n✓ Cache saved {stats2['cache_hits']} API call(s)")


def demo_statistics():
    """Demo statistics tracking."""
    print("\n" + "=" * 60)
    print("Demo 3: Statistics")
    print("=" * 60)

    manager = DataSourceManager()

    # Make some calls
    print("\n1. Making 5 API calls...")
    for i in range(5):
        symbol = f"60000{i}.SH"
        result = manager.get_stock_info(symbol)
        print(f"   Call {i+1}: {'✓' if result.success else '✗'}")

    # Show statistics
    print("\n2. Statistics:")
    stats = manager.get_stats()
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Cache hits: {stats['cache_hits']}")
    print(f"   Cache misses: {stats['cache_misses']}")

    print("\n3. Per-source statistics:")
    for source_name in stats['source_success']:
        success = stats['source_success'][source_name]
        failures = stats['source_failures'][source_name]
        total = success + failures
        success_rate = (success / total * 100) if total > 0 else 0
        print(f"   {source_name}: {success}/{total} success ({success_rate:.1f}%)")

    print("\n4. Circuit breaker states:")
    for source_name, state in stats['circuit_breakers'].items():
        print(f"   {source_name}: {state['state']} (failures: {state['failure_count']})")


def demo_realtime_quote():
    """Demo real-time quote fetching."""
    print("\n" + "=" * 60)
    print("Demo 4: Real-time Quotes")
    print("=" * 60)

    manager = DataSourceManager()

    symbols = ["600000.SH", "000001.SZ", "600519.SH"]
    print(f"\n1. Getting real-time quotes for {len(symbols)} stocks...")

    result = manager.get_realtime_quote(symbols)

    if result.success:
        print(f"✓ Success: Got quotes for {len(result.data)} stocks")
        for symbol, quote in result.data.items():
            print(f"   {symbol}: {quote}")
    else:
        print(f"✗ Failed: {result.error}")


def demo_cache_management():
    """Demo cache management."""
    print("\n" + "=" * 60)
    print("Demo 5: Cache Management")
    print("=" * 60)

    manager = DataSourceManager()

    # Fill cache
    print("\n1. Filling cache with 3 items...")
    for i in range(3):
        manager.get_stock_info(f"60000{i}.SH")

    stats = manager.get_stats()
    print(f"   Cache size: {stats['cache_stats']['size']}")

    # Clear cache
    print("\n2. Clearing cache...")
    manager.clear_cache()

    stats = manager.get_stats()
    print(f"   Cache size: {stats['cache_stats']['size']}")

    print("\n✓ Cache cleared successfully")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "DataSourceManager Demo" + " " * 26 + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        demo_basic_usage()
        demo_caching()
        demo_statistics()
        # demo_realtime_quote()  # May fail if data source is unavailable
        demo_cache_management()

        print("\n" + "=" * 60)
        print("✓ All demos completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
