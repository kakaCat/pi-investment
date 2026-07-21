"""
QuantLib Basic Validation Test
===============================

Tests basic functionality of QuantLib modules without requiring
complex calculations or external dependencies.

Tests:
    1. Module imports
    2. Class instantiation
    3. Basic validation methods
    4. Exception handling
    5. Data validator basic checks
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")

    try:
        from quantlib import (
            BaseCalculator,
            CalculatorFactory,
            CalculationResult,
            DataValidator,
            DataQualityReport,
            QuantAnalyticsError,
            DataValidationError,
            CalculationError
        )
        print("  ✓ All imports successful")
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False


def test_base_calculator():
    """Test BaseCalculator abstract class."""
    print("\nTesting BaseCalculator...")

    try:
        from quantlib import BaseCalculator

        # Create a simple concrete implementation
        class SimpleCalculator(BaseCalculator):
            def calculate(self, data):
                validated = self._validate_numeric_input(data, 'data')
                return self._create_result_dict(validated, 'simple')

        # Test instantiation
        calc = SimpleCalculator(precision=4, risk_free_rate=0.02)
        print("  ✓ Calculator instantiated")

        # Test validation methods
        result = calc._validate_numeric_input(5.0, 'test')
        assert result == 5.0
        print("  ✓ Numeric validation works")

        # Test positive validation
        result = calc._validate_positive(10.0, 'test')
        assert result == 10.0
        print("  ✓ Positive validation works")

        # Test probability validation
        result = calc._validate_probability(0.5, 'test')
        assert result == 0.5
        print("  ✓ Probability validation works")

        # Test calculate method
        result = calc.calculate(42.123456)
        assert 'value' in result
        assert 'method' in result
        print("  ✓ Calculate method works")

        return True
    except Exception as e:
        print(f"  ✗ BaseCalculator test failed: {e}")
        return False


def test_exceptions():
    """Test custom exceptions."""
    print("\nTesting Exceptions...")

    try:
        from quantlib import (
            QuantAnalyticsError,
            DataValidationError,
            InsufficientDataError,
            CalculationError
        )

        # Test base exception
        try:
            raise QuantAnalyticsError("Test error", error_code="TEST_001")
        except QuantAnalyticsError as e:
            assert e.error_code == "TEST_001"
            print("  ✓ QuantAnalyticsError works")

        # Test DataValidationError
        try:
            raise DataValidationError("Invalid value", field_name="price")
        except DataValidationError as e:
            assert "price" in str(e)
            print("  ✓ DataValidationError works")

        # Test InsufficientDataError
        try:
            raise InsufficientDataError(required=100, provided=50, calculation="volatility")
        except InsufficientDataError as e:
            assert e.required == 100
            assert e.provided == 50
            print("  ✓ InsufficientDataError works")

        # Test CalculationError
        try:
            raise CalculationError("Division by zero", calculation_type="sharpe_ratio")
        except CalculationError as e:
            assert "sharpe_ratio" in str(e)
            print("  ✓ CalculationError works")

        return True
    except Exception as e:
        print(f"  ✗ Exception test failed: {e}")
        return False


def test_data_validator():
    """Test DataValidator class."""
    print("\nTesting DataValidator...")

    try:
        import numpy as np
        import pandas as pd
        from quantlib import DataValidator, DataQualityReport

        # Test DataQualityReport
        report = DataQualityReport("test_data")
        report.add_issue("test_issue", "Test description", "medium")
        report.add_warning("test_warning", "Test warning message")
        report.add_recommendation("Test recommendation")

        assert len(report.issues) == 1
        assert len(report.warnings) == 1
        assert len(report.recommendations) == 1
        print("  ✓ DataQualityReport works")

        # Test DataValidator instantiation
        validator = DataValidator(strict_mode=False)
        print("  ✓ DataValidator instantiated")

        # Test validation with simple data
        test_data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        cleaned_data, report = validator.validate_financial_data(
            test_data,
            data_type='general',
            data_name='test_series'
        )

        assert len(cleaned_data) == 5
        assert report.data_name == 'test_series'
        print("  ✓ Financial data validation works")

        # Test with returns data
        returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        cleaned_returns, report = validator.validate_financial_data(
            returns,
            data_type='returns',
            data_name='test_returns'
        )

        assert len(cleaned_returns) == 5
        print("  ✓ Returns validation works")

        return True
    except Exception as e:
        print(f"  ✗ DataValidator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_calculator_factory():
    """Test CalculatorFactory."""
    print("\nTesting CalculatorFactory...")

    try:
        from quantlib import BaseCalculator, CalculatorFactory

        # Create a test calculator
        class TestCalculator(BaseCalculator):
            def calculate(self, x):
                return self._create_result_dict(x * 2, 'double')

        # Register calculator
        CalculatorFactory.register_calculator('test', TestCalculator)
        print("  ✓ Calculator registered")

        # List calculators
        calculators = CalculatorFactory.list_calculators()
        assert 'test' in calculators
        print("  ✓ Calculator listed")

        # Create calculator instance
        calc = CalculatorFactory.create_calculator('test', precision=4)
        assert isinstance(calc, TestCalculator)
        print("  ✓ Calculator created via factory")

        return True
    except Exception as e:
        print(f"  ✗ CalculatorFactory test failed: {e}")
        return False


def test_calculation_result():
    """Test CalculationResult wrapper."""
    print("\nTesting CalculationResult...")

    try:
        from quantlib import CalculationResult

        # Create result
        result_dict = {
            'value': 0.25,
            'method': 'test_method',
            'timestamp': '2026-05-24T12:00:00',
            'calculator': 'TestCalculator'
        }

        result = CalculationResult(result_dict)

        assert result.value == 0.25
        assert result.method == 'test_method'
        print("  ✓ CalculationResult created")

        # Test conversion to float
        float_val = float(result)
        assert float_val == 0.25
        print("  ✓ Float conversion works")

        # Test to_dict
        result_dict_copy = result.to_dict()
        assert result_dict_copy['value'] == 0.25
        print("  ✓ to_dict() works")

        return True
    except Exception as e:
        print(f"  ✗ CalculationResult test failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("QuantLib Basic Validation Test Suite")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("BaseCalculator", test_base_calculator),
        ("Exceptions", test_exceptions),
        ("DataValidator", test_data_validator),
        ("CalculatorFactory", test_calculator_factory),
        ("CalculationResult", test_calculation_result),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
