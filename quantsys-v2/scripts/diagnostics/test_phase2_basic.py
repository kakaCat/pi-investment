#!/usr/bin/env python3
"""
Phase 2 Migration Basic Validation Test

Tests that all Phase 2 market data sources can be instantiated
and have the required abstract methods implemented.

This test does NOT require network connectivity or API keys.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from adapters.outbound.datasources.sources.alphavantage_source import AlphaVantageSource
from adapters.outbound.datasources.sources.finnhub_source import FinnhubSource
from adapters.outbound.datasources.sources.iexcloud_source import IEXCloudSource
from adapters.outbound.datasources.sources.tiingo_source import TiingoSource
from adapters.outbound.datasources.sources.nasdaqdatalink_source import NasdaqDataLinkSource


def test_data_source(source_class, name):
    """Test that a data source can be instantiated and has required methods."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print('='*60)

    try:
        # Test instantiation
        print(f"✓ Instantiating {name}...")
        source = source_class(api_key="test_key_12345")
        print(f"  ✓ Successfully created {name} instance")

        # Check required MarketDataSource methods
        required_methods = [
            'get_stock_info',
            'get_klines',
            'get_realtime_quote',
            'validate_config',
            'test_connection'
        ]

        print(f"\n✓ Checking required methods...")
        for method in required_methods:
            if not hasattr(source, method):
                print(f"  ✗ Missing method: {method}")
                return False
            if not callable(getattr(source, method)):
                print(f"  ✗ {method} is not callable")
                return False
            print(f"  ✓ {method} exists and is callable")

        # Check that validate_config works
        print(f"\n✓ Testing validate_config()...")
        is_valid = source.validate_config()
        print(f"  ✓ validate_config() returned: {is_valid}")

        print(f"\n✅ {name} passed all basic validation tests!")
        return True

    except Exception as e:
        print(f"\n❌ {name} failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 2 data source tests."""
    print("="*60)
    print("Phase 2 Migration - Basic Validation Test")
    print("="*60)
    print("\nThis test validates that all Phase 2 market data sources:")
    print("  1. Can be instantiated")
    print("  2. Have all required abstract methods implemented")
    print("  3. Methods are callable")
    print("\nNote: This test does NOT require network connectivity or API keys.")

    data_sources = [
        (AlphaVantageSource, "Alpha Vantage"),
        (FinnhubSource, "Finnhub"),
        (IEXCloudSource, "IEX Cloud"),
        (TiingoSource, "Tiingo"),
        (NasdaqDataLinkSource, "Nasdaq Data Link (Quandl)"),
    ]

    results = {}

    for source_class, name in data_sources:
        results[name] = test_data_source(source_class, name)

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} data sources passed")

    if passed == total:
        print("\n🎉 All Phase 2 data sources passed basic validation!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} data source(s) failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
