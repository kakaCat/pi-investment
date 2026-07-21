#!/usr/bin/env python
"""
Test MA120 fallback logic with insufficient data
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from domain.quantlib.factors.moving_average import MovingAverageFactors

def test_ma120_with_insufficient_data():
    """Test MA120 with only 115 data points (less than 120)"""
    print("🔧 Testing MA120 fallback logic...")

    # Create 115 data points (insufficient for MA120)
    klines = []
    for i in range(115):
        klines.append({
            'open': 10.0 + i * 0.1,
            'high': 10.5 + i * 0.1,
            'low': 9.5 + i * 0.1,
            'close': 10.0 + i * 0.1,
            'volume': 1000000
        })

    calc = MovingAverageFactors()

    try:
        result = calc.ma120(klines)
        print(f"✅ MA120 calculation succeeded!")
        print(f"   Value: {result['value']}")
        print(f"   Parameters: {result['parameters']}")
        print(f"   Fallback used: {result['parameters'].get('fallback_used', False)}")
        print(f"   Effective period: {result['parameters'].get('effective_period', 120)}")

        # Verify no NaN
        if result['value'] is None or (isinstance(result['value'], float) and result['value'] != result['value']):
            print("❌ FAILED: Result is NaN!")
            return False

        print("✅ No NaN values detected")
        return True

    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ma120_with_sufficient_data():
    """Test MA120 with 150 data points (sufficient)"""
    print("\n🔧 Testing MA120 with sufficient data...")

    # Create 150 data points
    klines = []
    for i in range(150):
        klines.append({
            'open': 10.0 + i * 0.1,
            'high': 10.5 + i * 0.1,
            'low': 9.5 + i * 0.1,
            'close': 10.0 + i * 0.1,
            'volume': 1000000
        })

    calc = MovingAverageFactors()

    try:
        result = calc.ma120(klines)
        print(f"✅ MA120 calculation succeeded!")
        print(f"   Value: {result['value']}")
        print(f"   Fallback used: {result['parameters'].get('fallback_used', False)}")

        if result['parameters'].get('fallback_used', False):
            print("❌ FAILED: Fallback should not be used with sufficient data!")
            return False

        print("✅ Normal calculation (no fallback)")
        return True

    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MA120 Fix Verification Test")
    print("=" * 60)

    test1 = test_ma120_with_insufficient_data()
    test2 = test_ma120_with_sufficient_data()

    print("\n" + "=" * 60)
    if test1 and test2:
        print("✅ ALL TESTS PASSED - MA120 fix is working!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
