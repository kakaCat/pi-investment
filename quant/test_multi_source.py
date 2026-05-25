#!/usr/bin/env python3
"""Test multi-source data service."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from quantsys.data.data.data_service import DataService


def test_basic_fetch():
    """Test basic data fetching with automatic fallback."""
    print("=" * 60)
    print("Test 1: Basic Fetch with Automatic Fallback")
    print("=" * 60)

    service = DataService()

    # Test fetching data
    symbol = "000001"
    print(f"\nFetching data for {symbol}...")

    try:
        df = service.get_daily_klines(symbol, days=30)
        print(f"✓ Success: Fetched {len(df)} rows")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"  Columns: {list(df.columns)}")
        print("\nFirst 3 rows:")
        print(df.head(3))
        return True
    except Exception as exc:
        print(f"✗ Failed: {exc}")
        return False


def test_health_status():
    """Test health status monitoring."""
    print("\n" + "=" * 60)
    print("Test 2: Health Status Monitoring")
    print("=" * 60)

    service = DataService()

    # Fetch some data to trigger health checks
    try:
        service.get_daily_klines("000001", days=10)
    except:
        pass

    # Check health status
    health = service.get_health_status()

    print("\nData Source Health Status:")
    for source, status in health.items():
        print(f"\n{source}:")
        print(f"  Available: {status['available']}")
        print(f"  Success count: {status['success_count']}")
        print(f"  Failure count: {status['failure_count']}")

    return True


def test_cache():
    """Test caching functionality."""
    print("\n" + "=" * 60)
    print("Test 3: Caching")
    print("=" * 60)

    service = DataService(cache_enabled=True)

    symbol = "600519"

    # First request
    print(f"\n1st request for {symbol}:")
    try:
        df1 = service.get_daily_klines(symbol, days=10)
        print(f"✓ Fetched {len(df1)} rows")
    except Exception as exc:
        print(f"✗ Failed: {exc}")
        return False

    # Second request (should be cached)
    print(f"\n2nd request for {symbol}:")
    try:
        df2 = service.get_daily_klines(symbol, days=10)
        print(f"✓ Fetched {len(df2)} rows (from cache)")
    except Exception as exc:
        print(f"✗ Failed: {exc}")
        return False

    # Check cache stats
    stats = service.get_cache_stats()
    print(f"\nCache stats: {stats}")

    return True


def test_stock_list():
    """Test stock list fetching."""
    print("\n" + "=" * 60)
    print("Test 4: Stock List")
    print("=" * 60)

    service = DataService()

    print("\nFetching A-share stock list...")

    try:
        df = service.get_stock_list(market="A")
        print(f"✓ Success: Fetched {len(df)} stocks")
        print("\nFirst 5 stocks:")
        print(df.head(5))
        return True
    except Exception as exc:
        print(f"✗ Failed: {exc}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Multi-Source Data Service Tests")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Basic Fetch", test_basic_fetch()))
    results.append(("Health Status", test_health_status()))
    results.append(("Caching", test_cache()))
    results.append(("Stock List", test_stock_list()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
