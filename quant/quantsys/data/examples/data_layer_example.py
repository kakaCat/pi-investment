"""Example usage of the data layer modules.

This script demonstrates how to use the data layer components:
- AkShareAdapter: Fetch data from AkShare
- PriceAdjuster: Adjust prices for corporate actions
- DataValidator: Validate data quality
- DBManager: Store and retrieve data
- CacheManager: Cache frequently accessed data
"""

from datetime import datetime, timedelta

import pandas as pd

from pipeline.data.sources.akshare_adapter import AkShareAdapter
from pipeline.data.cleaner.adjuster import PriceAdjuster
from pipeline.data.cleaner.validator import DataValidator
from pipeline.data.storage.db_manager import DBManager
from pipeline.data.storage.cache_manager import CacheManager


def example_fetch_and_validate():
    """Example: Fetch data and validate quality."""
    print("=" * 60)
    print("Example 1: Fetch and Validate Data")
    print("=" * 60)

    # Initialize adapter and validator
    adapter = AkShareAdapter()
    validator = DataValidator()

    # Fetch recent data for a symbol
    symbol = "000001"
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    print(f"\nFetching data for {symbol} from {start_date} to {end_date}...")

    try:
        df = adapter.fetch_daily_klines(symbol, start_date, end_date, adjust="qfq")
        print(f"Fetched {len(df)} rows")
        print(f"\nFirst 5 rows:\n{df.head()}")

        # Validate data quality
        print("\nValidating data quality...")
        result = validator.validate(df)

        print(f"Valid: {result['is_valid']}")
        print(f"Errors: {result['errors']}")
        print(f"Warnings: {result['warnings']}")

    except Exception as exc:
        print(f"Error: {exc}")


def example_price_adjustment():
    """Example: Adjust prices for corporate actions."""
    print("\n" + "=" * 60)
    print("Example 2: Price Adjustment")
    print("=" * 60)

    # Create sample data with a stock split
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": [100, 100, 100, 100, 50, 50, 50, 50, 50, 50],
        "high": [105, 105, 105, 105, 52, 52, 52, 52, 52, 52],
        "low": [95, 95, 95, 95, 48, 48, 48, 48, 48, 48],
        "close": [100, 100, 100, 100, 50, 50, 50, 50, 50, 50],
        "volume": [1000, 1000, 1000, 1000, 2000, 2000, 2000, 2000, 2000, 2000],
    })

    print("\nOriginal data (with stock split on day 5):")
    print(df[["date", "close", "volume"]])

    # Detect corporate actions
    adjuster = PriceAdjuster()
    actions = adjuster.detect_corporate_actions(df)
    print(f"\nDetected {len(actions)} corporate actions:")
    print(actions)

    # Apply forward adjustment
    adjusted = adjuster.adjust_prices(df, adjust_type="qfq")
    print("\nAdjusted data (forward adjustment):")
    print(adjusted[["date", "close", "volume"]])


def example_database_operations():
    """Example: Store and retrieve data from database."""
    print("\n" + "=" * 60)
    print("Example 3: Database Operations")
    print("=" * 60)

    # Initialize database manager
    db = DBManager()

    # Create sample data
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": [100, 101, 102, 103, 104],
        "high": [105, 106, 107, 108, 109],
        "low": [95, 96, 97, 98, 99],
        "close": [100, 101, 102, 103, 104],
        "volume": [1000, 1000, 1000, 1000, 1000],
        "amount": [100000, 101000, 102000, 103000, 104000],
    })

    # Save to database
    symbol = "TEST001"
    print(f"\nSaving {len(df)} rows for {symbol}...")
    count = db.save_klines(symbol, df)
    print(f"Saved {count} rows")

    # Load from database
    print(f"\nLoading data for {symbol}...")
    loaded = db.load_klines(symbol)
    print(f"Loaded {len(loaded)} rows")
    print(loaded.head())

    # Get statistics
    print("\nDatabase statistics:")
    stats = db.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    db.close()


def example_caching():
    """Example: Cache frequently accessed data."""
    print("\n" + "=" * 60)
    print("Example 4: Caching")
    print("=" * 60)

    # Initialize cache
    cache = CacheManager(max_size=100, default_ttl=300)

    # Create sample data
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "close": [100, 101],
    })

    # Cache data
    symbol = "000001"
    print(f"\nCaching data for {symbol}...")
    cache.set_klines(symbol, df, "20240101", "20240102")

    # Retrieve from cache
    print(f"Retrieving from cache...")
    cached = cache.get_klines(symbol, "20240101", "20240102")
    print(f"Cache hit: {cached is not None}")
    if cached is not None:
        print(cached)

    # Cache statistics
    print("\nCache statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Invalidate symbol
    print(f"\nInvalidating {symbol}...")
    count = cache.invalidate_symbol(symbol)
    print(f"Invalidated {count} entries")

    # Try to retrieve again
    cached = cache.get_klines(symbol, "20240101", "20240102")
    print(f"Cache hit after invalidation: {cached is not None}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Data Layer Usage Examples")
    print("=" * 60)

    # Run examples
    example_fetch_and_validate()
    example_price_adjustment()
    example_database_operations()
    example_caching()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
