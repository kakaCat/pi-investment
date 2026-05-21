"""Example usage of the unified data service with multi-source support.

This example demonstrates how to use the DataService with automatic
fallback between Tushare and AkShare.

Setup:
    1. Install dependencies:
       pip install tushare akshare

    2. (Optional) Set Tushare token:
       export TUSHARE_TOKEN="your_token_here"
       Get token at: https://tushare.pro/register

    3. Run this script:
       python -m quantsys.data.data.examples.multi_source_example
"""

from quantsys.data.data.data_service import DataService


def example_basic_usage():
    """Basic usage: fetch daily K-lines with automatic fallback."""
    print("=" * 60)
    print("Example 1: Basic Usage - Fetch Daily K-lines")
    print("=" * 60)

    # Initialize service (automatically configures all available sources)
    service = DataService()

    # Fetch data - will try Tushare first, fall back to AkShare if needed
    symbol = "000001"
    df = service.get_daily_klines(symbol, days=30)

    print(f"\nFetched {len(df)} rows for {symbol}")
    print(df.head())
    print(f"\nDate range: {df['date'].min()} to {df['date'].max()}")


def example_cache_usage():
    """Demonstrate caching - second request is instant."""
    print("\n" + "=" * 60)
    print("Example 2: Caching - Second Request is Instant")
    print("=" * 60)

    service = DataService(cache_enabled=True)

    symbol = "600519"

    # First request - fetches from data source
    print(f"\n1st request for {symbol}:")
    df1 = service.get_daily_klines(symbol, days=30)
    print(f"Fetched {len(df1)} rows")

    # Second request - returns from cache
    print(f"\n2nd request for {symbol}:")
    df2 = service.get_daily_klines(symbol, days=30)
    print(f"Fetched {len(df2)} rows (from cache)")

    # Check cache stats
    stats = service.get_cache_stats()
    print(f"\nCache stats: {stats}")


def example_stock_list():
    """Fetch stock list with automatic fallback."""
    print("\n" + "=" * 60)
    print("Example 3: Fetch Stock List")
    print("=" * 60)

    service = DataService()

    # Fetch A-share stock list
    df = service.get_stock_list(market="A")

    print(f"\nFetched {len(df)} A-share stocks")
    print(df.head(10))


def example_health_status():
    """Check health status of data sources."""
    print("\n" + "=" * 60)
    print("Example 4: Health Status Monitoring")
    print("=" * 60)

    service = DataService()

    # Fetch some data to trigger health checks
    service.get_daily_klines("000001", days=30)
    service.get_daily_klines("600519", days=30)

    # Check health status
    health = service.get_health_status()

    print("\nData Source Health Status:")
    for source, status in health.items():
        print(f"\n{source}:")
        print(f"  Available: {status['available']}")
        print(f"  Success count: {status['success_count']}")
        print(f"  Failure count: {status['failure_count']}")
        if status['last_success']:
            print(f"  Last success: {status['last_success']}")


def example_batch_fetch():
    """Fetch data for multiple symbols."""
    print("\n" + "=" * 60)
    print("Example 5: Batch Fetch Multiple Symbols")
    print("=" * 60)

    service = DataService()

    symbols = ["000001", "000002", "600000", "600519"]

    print(f"\nFetching data for {len(symbols)} symbols...")

    results = {}
    for symbol in symbols:
        try:
            df = service.get_daily_klines(symbol, days=30)
            results[symbol] = df
            print(f"✓ {symbol}: {len(df)} rows")
        except Exception as exc:
            print(f"✗ {symbol}: {exc}")

    print(f"\nSuccessfully fetched {len(results)}/{len(symbols)} symbols")


def example_data_validation():
    """Demonstrate data validation."""
    print("\n" + "=" * 60)
    print("Example 6: Data Validation")
    print("=" * 60)

    # Enable validation
    service = DataService(validate_data=True)

    symbol = "000001"
    df = service.get_daily_klines(symbol, days=365)

    print(f"\nFetched {len(df)} rows for {symbol}")
    print("Data validation is automatically performed")
    print("Check console output for any validation warnings")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Multi-Source Data Service Examples")
    print("=" * 60)

    try:
        example_basic_usage()
        example_cache_usage()
        example_stock_list()
        example_health_status()
        example_batch_fetch()
        example_data_validation()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
