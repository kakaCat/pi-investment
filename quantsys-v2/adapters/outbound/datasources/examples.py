"""Example usage of the new data sources.

Demonstrates how to use AkShare, FRED, and World Bank data sources.
"""

import os
from adapters.outbound.datasources.sources import AkShareSource, FREDSource, WorldBankSource
from adapters.outbound.datasources.config import DataSourceConfig


def example_akshare():
    """Example: Using AkShare data source."""
    print("\n=== AkShare Example ===")

    source = AkShareSource()

    # Test connection
    result = source.test_connection()
    print(f"Connection test: {result.success}")

    # Get stock info
    result = source.get_stock_info("000001.SZ")
    if result.success:
        print(f"Stock info: {result.data}")
    else:
        print(f"Error: {result.error}")

    # Get klines
    result = source.get_klines("000001.SZ", period="daily", start_date="20240101", end_date="20240131")
    if result.success:
        print(f"Got {result.count} klines")
        if result.data:
            print(f"First kline: {result.data[0]}")
    else:
        print(f"Error: {result.error}")

    # Get realtime quote
    result = source.get_realtime_quote(["000001.SZ", "600000.SH"])
    if result.success:
        print(f"Quotes: {result.data}")
    else:
        print(f"Error: {result.error}")


def example_fred():
    """Example: Using FRED data source."""
    print("\n=== FRED Example ===")

    # Check if API key is configured
    if not DataSourceConfig.is_configured("fred"):
        print("FRED API key not configured. Set FRED_API_KEY environment variable.")
        print("Get your free key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        return

    source = FREDSource()

    # Test connection
    result = source.test_connection()
    print(f"Connection test: {result.success}")

    # Get GDP series
    result = source.get_series("GDP", start_date="2020-01-01", end_date="2024-01-01")
    if result.success:
        print(f"Series: {result.data['title']}")
        print(f"Got {result.data['observation_count']} observations")
        if result.data['observations']:
            print(f"Latest: {result.data['observations'][-1]}")
    else:
        print(f"Error: {result.error}")

    # Search for series
    result = source.search_series("unemployment", limit=5)
    if result.success:
        print(f"Found {result.count} series:")
        for series in result.data[:3]:
            print(f"  - {series['id']}: {series['title']}")
    else:
        print(f"Error: {result.error}")


def example_world_bank():
    """Example: Using World Bank data source."""
    print("\n=== World Bank Example ===")

    source = WorldBankSource()

    # Test connection
    result = source.test_connection()
    print(f"Connection test: {result.success}")

    # List commodities
    result = source.list_commodities()
    if result.success:
        print(f"Available commodities: {result.count}")
        print(f"Sample: {[c['name'] for c in result.data[:5]]}")
    else:
        print(f"Error: {result.error}")

    # Get oil prices
    result = source.get_oil_prices(start_year=2023, end_year=2024)
    if result.success:
        print(f"Oil prices data: {result.data['category']}")
        for oil_type, data in result.data['data'].items():
            if data:
                print(f"  {oil_type}: {len(data)} records")
    else:
        print(f"Error: {result.error}")

    # Get specific commodity
    result = source.get_commodity_price("gold", start_year=2023, end_year=2024)
    if result.success:
        print(f"Gold price data: {result.data['commodity']}")
        if result.data['data']:
            print(f"  Records: {len(result.data['data'])}")
    else:
        print(f"Error: {result.error}")

    # Search commodities
    result = source.search_series("copper", limit=5)
    if result.success:
        print(f"Search results for 'copper': {result.count}")
        for item in result.data:
            print(f"  - {item['name']} ({item['category']})")
    else:
        print(f"Error: {result.error}")


def check_configuration():
    """Check configuration status for all data sources."""
    print("\n=== Data Source Configuration ===")

    status = DataSourceConfig.validate_all()
    for source, message in status.items():
        print(f"{source:20s}: {message}")


if __name__ == "__main__":
    print("Data Sources Example Usage")
    print("=" * 50)

    # Check configuration
    check_configuration()

    # Run examples
    example_akshare()
    example_fred()
    example_world_bank()

    print("\n" + "=" * 50)
    print("Examples completed!")
