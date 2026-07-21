"""Test Sina adapter and source."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.quantlib.adapters.sina_adapter import SinaAdapter
from adapters.outbound.datasources.sources.sina_source import SinaSource


def test_sina_adapter():
    """Test SinaAdapter directly."""
    print("=" * 60)
    print("Testing SinaAdapter")
    print("=" * 60)

    adapter = SinaAdapter()

    # Test real-time quotes
    print("\n1. Testing real-time quotes...")
    symbols = ["600000.SH", "000001.SZ", "00700.HK"]
    quotes = adapter.get_realtime_quote(symbols)

    if quotes:
        print(f"✓ Got {len(quotes)} quotes")
        for symbol, quote in quotes.items():
            print(f"  {symbol}: {quote.get('name')} - ¥{quote.get('price')} ({quote.get('change_pct')}%)")
    else:
        print("✗ No quotes returned")

    # Test stock info
    print("\n2. Testing stock info...")
    info = adapter.get_stock_info("600000.SH")
    if info:
        print(f"✓ Stock info: {info}")
    else:
        print("✗ No stock info")


def test_sina_source():
    """Test SinaSource with DataSourceResponse."""
    print("\n" + "=" * 60)
    print("Testing SinaSource")
    print("=" * 60)

    source = SinaSource()

    # Test connection
    print("\n1. Testing connection...")
    result = source.test_connection()
    if result.success:
        print(f"✓ Connection test passed: {result.data}")
    else:
        print(f"✗ Connection test failed: {result.error}")

    # Test real-time quotes
    print("\n2. Testing real-time quotes...")
    result = source.get_realtime_quote(["600000.SH", "000001.SZ"])
    if result.success:
        print(f"✓ Got quotes: {len(result.data)} symbols")
        for symbol, quote in result.data.items():
            print(f"  {symbol}: {quote.get('name')} - ¥{quote.get('price')}")
    else:
        print(f"✗ Failed: {result.error}")

    # Test unsupported method
    print("\n3. Testing unsupported method (klines)...")
    result = source.get_klines("600000.SH")
    if not result.success:
        print(f"✓ Correctly returns error: {result.error}")
    else:
        print("✗ Should have returned error")


def test_manager_with_sina():
    """Test DataSourceManager with Sina."""
    print("\n" + "=" * 60)
    print("Testing DataSourceManager with Sina")
    print("=" * 60)

    from adapters.outbound.datasources.manager import DataSourceManager

    # Create manager with sina enabled
    manager = DataSourceManager()

    print("\n1. Testing real-time quotes through manager...")
    result = manager.get_realtime_quote(["600000.SH"])

    if result.success:
        print(f"✓ Manager returned quotes: {result.data}")
    else:
        print(f"✗ Manager failed: {result.error}")

    # Check stats
    print("\n2. Checking stats...")
    stats = manager.get_stats()
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Source stats:")
    for name in stats['source_success']:
        success = stats['source_success'][name]
        failures = stats['source_failures'][name]
        print(f"    {name}: {success} success, {failures} failures")


if __name__ == "__main__":
    try:
        test_sina_adapter()
        test_sina_source()
        test_manager_with_sina()

        print("\n" + "=" * 60)
        print("✓ All Sina tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
