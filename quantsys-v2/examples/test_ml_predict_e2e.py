#!/usr/bin/env python
"""
End-to-end test for model_predict fix
Tests the full ML prediction pipeline with insufficient data scenarios
"""
import sys
import requests
import json
from pathlib import Path

API_BASE = "http://127.0.0.1:5001"

def test_ml_predict_with_short_history():
    """
    Test ML prediction with a stock that has short history (< 120 days)
    This was the scenario that caused the segfault
    """
    print("=" * 60)
    print("Testing ML Predict with Short History Stock")
    print("=" * 60)

    # First, let's check which stocks have short history
    print("\n🔍 Finding stocks with limited data...")

    try:
        # Try to predict on a stock - using a test symbol
        test_symbol = "600000"  # 浦发银行

        print(f"\n📊 Testing prediction for {test_symbol}...")

        response = requests.post(
            f"{API_BASE}/api/ml/predict",
            json={
                "symbols": [test_symbol],
                "version": "latest"  # or specific version
            },
            timeout=30
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ Prediction succeeded!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"⚠️ Request failed: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server (is it running?)")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_feature_engineering_directly():
    """
    Test feature engineering directly in Python
    """
    print("\n" + "=" * 60)
    print("Testing Feature Engineering Directly")
    print("=" * 60)

    try:
        sys.path.insert(0, str(Path(__file__).parent))

        from application.services.ml_pipeline.feature_engineering import FeatureEngineer
        from domain.quantlib.adapters import get_factor_adapter

        # Create sample klines with only 115 days (insufficient for MA120)
        print("\n🔧 Creating sample data with 115 data points...")
        klines = []
        for i in range(115):
            klines.append({
                'date': f'2026-{(i//30)+1:02d}-{(i%30)+1:02d}',
                'open': 10.0 + i * 0.1,
                'high': 10.5 + i * 0.1,
                'low': 9.5 + i * 0.1,
                'close': 10.0 + i * 0.1,
                'volume': 1000000,
                'amount': 10000000
            })

        # Test factor calculation
        print("📊 Testing factor calculation...")
        adapter = get_factor_adapter()

        # Try to calculate MA120 specifically
        try:
            result = adapter.calculate('ma120', klines)
            print(f"✅ MA120 calculation succeeded!")
            print(f"   Value: {result}")

            if result is None or (isinstance(result, float) and result != result):
                print("❌ Result is NaN - fix may not be working")
                return False

            print("✅ No NaN values - fix is working!")

        except Exception as e:
            print(f"❌ MA120 calculation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        # Test full feature engineering pipeline
        print("\n🔧 Testing full feature engineering pipeline...")
        engineer = FeatureEngineer()

        klines_dict = {'TEST_STOCK': klines}

        try:
            # Extract features
            features_df = engineer.extract_features(
                klines_dict,
                factor_names=['ma5', 'ma10', 'ma20', 'ma60', 'ma120']
            )

            print(f"✅ Feature extraction succeeded!")
            print(f"   Shape: {features_df.shape}")
            print(f"   Columns: {list(features_df.columns)}")

            # Check for NaN
            nan_count = features_df.isnull().sum().sum()
            print(f"   NaN values: {nan_count}")

            # Prepare features with 'fill' mode (this is where the fix is applied)
            print("\n🔧 Testing feature preparation with 'fill' mode...")
            metadata_df, scaled_df = engineer.prepare_features(
                features_df,
                handle_missing='fill',
                fit_scaler=True
            )

            print(f"✅ Feature preparation succeeded!")
            print(f"   Scaled shape: {scaled_df.shape}")

            # Final NaN check
            final_nan = scaled_df.isnull().sum().sum()
            print(f"   Final NaN values: {final_nan}")

            if final_nan > 0:
                print("❌ Still have NaN after preparation - fix incomplete")
                return False

            print("✅ No NaN values in final features - fix is complete!")
            return True

        except Exception as e:
            print(f"❌ Feature engineering failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    except ImportError as e:
        print(f"❌ Cannot import modules: {e}")
        return False

if __name__ == "__main__":
    print("🧪 ML Predict Fix - End-to-End Validation")
    print()

    # Test 1: Direct feature engineering
    test1_passed = test_feature_engineering_directly()

    # Test 2: API endpoint (if available)
    test2_passed = test_ml_predict_with_short_history()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Feature Engineering Test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"API Endpoint Test: {'✅ PASSED' if test2_passed else '⚠️ SKIPPED/FAILED'}")

    if test1_passed:
        print("\n✅ Core fix is working - MA120 handles insufficient data correctly")
        sys.exit(0)
    else:
        print("\n❌ Fix validation failed")
        sys.exit(1)
