#!/usr/bin/env python3
"""
Phase 3 - Unified Crypto Exchange Basic Validation Test

Tests that the unified crypto exchange source can be instantiated
and has the required abstract methods implemented.

This test does NOT require network connectivity or API keys.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from adapters.outbound.datasources.sources.crypto_exchange_source import CryptoExchangeSource


def test_crypto_exchange():
    """Test that crypto exchange source can be instantiated and has required methods."""
    print("\n" + "="*60)
    print("Testing: Unified Crypto Exchange Source (CCXT)")
    print("="*60)

    try:
        # Test instantiation with different exchanges
        exchanges_to_test = ['binance', 'kraken', 'coinbase', 'huobi', 'bitfinex']

        for exchange_id in exchanges_to_test:
            print(f"\n{'='*60}")
            print(f"Testing Exchange: {exchange_id}")
            print('='*60)

            # Test instantiation
            print(f"✓ Instantiating {exchange_id}...")
            source = CryptoExchangeSource(exchange_id=exchange_id)
            print(f"  ✓ Successfully created {exchange_id} instance")

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

            # Check additional crypto-specific methods
            crypto_methods = [
                'get_order_book',
                'get_recent_trades',
                'list_markets',
                'search_symbols'
            ]

            print(f"\n✓ Checking crypto-specific methods...")
            for method in crypto_methods:
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

            # Check exchange ID
            print(f"\n✓ Verifying exchange ID...")
            print(f"  ✓ Exchange ID: {source.exchange_id}")
            print(f"  ✓ Exchange name: {source.exchange.name if hasattr(source.exchange, 'name') else 'N/A'}")

            print(f"\n✅ {exchange_id} passed all basic validation tests!")

        # Test static methods
        print(f"\n{'='*60}")
        print("Testing Static Methods")
        print('='*60)

        print("\n✓ Testing list_supported_exchanges()...")
        exchanges = CryptoExchangeSource.list_supported_exchanges()
        print(f"  ✓ Found {len(exchanges)} supported exchanges")
        print(f"  ✓ Sample exchanges: {', '.join(exchanges[:10])}...")

        print("\n✓ Testing get_popular_exchanges()...")
        popular = CryptoExchangeSource.get_popular_exchanges()
        print(f"  ✓ Found {len(popular)} popular exchanges")
        for ex_id, ex_name in list(popular.items())[:5]:
            print(f"    - {ex_id}: {ex_name}")

        print(f"\n✅ All static methods passed!")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run crypto exchange validation test."""
    print("="*60)
    print("Phase 3 - Unified Crypto Exchange Basic Validation Test")
    print("="*60)
    print("\nThis test validates that the unified crypto exchange source:")
    print("  1. Can be instantiated with different exchange IDs")
    print("  2. Has all required abstract methods implemented")
    print("  3. Has crypto-specific methods")
    print("  4. Methods are callable")
    print("  5. Static methods work correctly")
    print("\nNote: This test does NOT require network connectivity or API keys.")
    print("      It only validates the class structure and method signatures.")

    success = test_crypto_exchange()

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if success:
        print("✅ PASS: Unified Crypto Exchange Source")
        print("\n🎉 Crypto exchange source passed basic validation!")
        print("\nSupported exchanges: 100+ via CCXT library")
        print("Popular exchanges: Binance, Kraken, Coinbase Pro, Huobi, Bitfinex, OKX, Bybit, and more")
        return 0
    else:
        print("❌ FAIL: Unified Crypto Exchange Source")
        print("\n⚠️  Crypto exchange source failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
