"""
Unit Tests for Base Calculator and Derivatives Pricing
=======================================================

Tests the fusion of FinceptTerminal's design patterns into QuantSys V2.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from domain.quantlib.core.base_calculator import (
    BaseCalculator,
    validate_inputs,
    timing_decorator,
    handle_calculation_error,
    CalculatorFactory
)
from domain.quantlib.core.exceptions import (
    DataValidationError as CoreDataValidationError,
    InsufficientDataError as CoreInsufficientDataError,
    CalculationError as CoreCalculationError,
    ConvergenceError as CoreConvergenceError
)
from domain.quantlib.exceptions import (
    DataValidationError as QLDataValidationError,
    InsufficientDataError as QLInsufficientDataError,
    CalculationError as QLCalculationError,
    ConvergenceError as QLConvergenceError
)
# Accept either exception type (core or quantlib)
DataValidationError = (CoreDataValidationError, QLDataValidationError)
InsufficientDataError = (CoreInsufficientDataError, QLInsufficientDataError)
CalculationError = (CoreCalculationError, QLCalculationError)
ConvergenceError = (CoreConvergenceError, QLConvergenceError)
from domain.quantlib.core.data_validator import DataValidator, DataQualityReport
from domain.quantlib.derivatives.black_scholes import BlackScholesCalculator
from domain.quantlib.derivatives.greeks import GreeksCalculator


class TestBaseCalculator:
    """Test BaseCalculator abstract class and validation methods."""

    def test_validate_numeric_input_float(self):
        """Test validation of float input."""
        calc = BlackScholesCalculator()
        result = calc._validate_numeric_input(3.14, "test")
        assert result == 3.14

    def test_validate_numeric_input_list(self):
        """Test validation of list input."""
        calc = BlackScholesCalculator()
        result = calc._validate_numeric_input([1, 2, 3], "test")
        assert isinstance(result, np.ndarray)
        assert len(result) == 3

    def test_validate_numeric_input_nan(self):
        """Test that NaN values are rejected."""
        calc = BlackScholesCalculator()
        with pytest.raises(ValueError, match="invalid values"):
            calc._validate_numeric_input(np.nan, "test")

    def test_validate_positive(self):
        """Test positive number validation."""
        calc = BlackScholesCalculator()
        assert calc._validate_positive(5.0, "test") == 5.0

        with pytest.raises(ValueError, match="must be positive"):
            calc._validate_positive(-1.0, "test")

    def test_validate_probability(self):
        """Test probability validation."""
        calc = BlackScholesCalculator()
        assert calc._validate_probability(0.5, "test") == 0.5

        with pytest.raises(ValueError, match="between 0 and 1"):
            calc._validate_probability(1.5, "test")

    def test_check_data_length(self):
        """Test data length checking."""
        calc = BlackScholesCalculator()
        data = [1, 2, 3, 4, 5]
        calc._check_data_length(data, min_length=3)  # Should pass

        with pytest.raises(ValueError, match="Insufficient data"):
            calc._check_data_length(data, min_length=10)

    def test_create_result_dict(self):
        """Test standardized result dictionary creation."""
        calc = BlackScholesCalculator()
        result = calc._create_result_dict(
            value=100.0,
            method="test_method",
            parameters={"param1": 1},
            metadata={"info": "test"}
        )

        assert result["value"] == 100.0
        assert result["method"] == "test_method"
        assert result["parameters"]["param1"] == 1
        assert result["metadata"]["info"] == "test"
        assert "timestamp" in result
        assert result["calculator"] == "BlackScholesCalculator"


class TestDataValidator:
    """Test DataValidator class."""

    def test_validate_returns_series_valid(self):
        """Test validation of valid returns series."""
        returns = np.random.randn(100) * 0.02  # 2% daily volatility
        result = DataValidator.validate_returns_series(returns, min_length=30)
        assert len(result) == 100

    def test_validate_returns_series_too_short(self):
        """Test that short series are rejected."""
        returns = [0.01, 0.02]
        with pytest.raises(InsufficientDataError):
            DataValidator.validate_returns_series(returns, min_length=30)

    def test_validate_returns_series_with_nan(self):
        """Test that NaN values are rejected."""
        returns = [0.01, np.nan, 0.02]
        with pytest.raises(DataValidationError, match="NaN"):
            DataValidator.validate_returns_series(returns, min_length=2)

    def test_validate_positive(self):
        """Test positive number validation."""
        assert DataValidator.validate_positive_number(5.0, "test") == 5.0

        with pytest.raises(DataValidationError):
            DataValidator.validate_positive_number(-1.0, "test")

    def test_validate_probability(self):
        """Test probability validation."""
        assert DataValidator.validate_probability(0.75, "test") == 0.75

        with pytest.raises(DataValidationError):
            DataValidator.validate_probability(1.5, "test")

    def test_detect_outliers_iqr(self):
        """Test outlier detection using IQR method."""
        data = np.concatenate([
            np.random.randn(100),
            [10, -10]  # Outliers
        ])
        mask, indices = DataValidator.detect_outliers(data, method="iqr")
        assert len(indices) >= 2  # Should detect at least the 2 outliers

    def test_detect_outliers_zscore(self):
        """Test outlier detection using z-score method."""
        data = np.concatenate([
            np.random.randn(100),
            [5, -5]  # Outliers
        ])
        mask, indices = DataValidator.detect_outliers(data, method="zscore", threshold=3.0)
        assert len(indices) >= 2

    def test_generate_quality_report(self):
        """Test data quality report generation."""
        df = pd.DataFrame({
            'price': [100, 101, np.nan, 103, 104],
            'volume': [1000, 1100, 1200, 1300, 1400],
            'date': pd.date_range('2024-01-01', periods=5)
        })

        validator = DataValidator()
        report = validator.generate_quality_report(df, date_column='date')

        assert isinstance(report, DataQualityReport)
        assert report.total_records == 5
        assert report.missing_values['price'] == 1
        assert report.date_range is not None
        assert 0 <= report.quality_score <= 100


class TestBlackScholesCalculator:
    """Test derivatives pricing functionality."""

    def test_black_scholes_call_price(self):
        """Test Black-Scholes call option pricing."""
        pricer = BlackScholesCalculator()
        result = pricer.calculate(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="call"
        )

        assert "value" in result
        assert result["value"] > 0
        assert result["method"] in ["black_scholes", "black_scholes_price"]
        assert "metadata" in result
        assert "d1" in result["metadata"]

    def test_black_scholes_put_price(self):
        """Test Black-Scholes put option pricing."""
        pricer = BlackScholesCalculator()
        result = pricer.calculate(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="put"
        )

        assert result["value"] > 0
        assert result["parameters"]["option_type"] == "put"

    def test_black_scholes_put_call_parity(self):
        """Test put-call parity relationship."""
        pricer = BlackScholesCalculator()
        S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2

        call = pricer.calculate(S, K, T, r, sigma, option_type="call")
        put = pricer.calculate(S, K, T, r, sigma, option_type="put")

        # Put-Call Parity: C - P = S - K*e^(-rT)
        parity_lhs = call["value"] - put["value"]
        parity_rhs = S - K * np.exp(-r * T)

        assert abs(parity_lhs - parity_rhs) < 0.01

    def test_greeks_calculation(self):
        """Test Greeks calculation."""
        pricer = BlackScholesCalculator()
        result = GreeksCalculator().calculate(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="call"
        )

        greeks = result["value"]
        assert "delta" in greeks
        assert "gamma" in greeks
        assert "theta" in greeks
        assert "vega" in greeks
        assert "rho" in greeks

        # Delta should be between 0 and 1 for ATM call
        assert 0 < greeks["delta"] < 1

        # Gamma should be positive
        assert greeks["gamma"] > 0

        # Vega should be positive
        assert greeks["vega"] > 0

    def test_greeks_put_delta(self):
        """Test that put delta is negative."""
        pricer = BlackScholesCalculator()
        result = GreeksCalculator().calculate(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="put"
        )

        assert result["value"]["delta"] < 0

    def test_implied_volatility(self):
        """Test implied volatility calculation."""
        pricer = BlackScholesCalculator()

        # First, calculate a theoretical price
        S, K, T, r, sigma_true = 100, 100, 1.0, 0.05, 0.25
        price_result = pricer.calculate(S, K, T, r, sigma_true, option_type="call")
        market_price = price_result["value"]

        # Now recover the volatility
        from domain.quantlib.derivatives.implied_volatility import ImpliedVolatilityCalculator
        iv_calc = ImpliedVolatilityCalculator()
        iv_result = iv_calc.calculate(
            S=S, K=K, T=T, r=r, option_price=market_price, option_type="call"
        )

        # Should recover the original volatility
        assert abs(iv_result["value"] - sigma_true) < 0.001

    def test_bond_price_calculation(self):
        """Test bond price calculation."""
        pricer = BlackScholesCalculator()
        from domain.quantlib.fixed_income.bond_pricing import BondPricingCalculator
        bond_calc = BondPricingCalculator()
        result = bond_calc.calculate(
            face_value=1000,
            coupon_rate=0.05,
            ytm=0.05,
            years_to_maturity=10,
            frequency=2
        )

        # When coupon rate equals YTM, price should equal face value
        assert abs(result["value"] - 1000) < 1.0

    def test_expired_option(self):
        """Test that expired options (T=0) are rejected."""
        pricer = BlackScholesCalculator()
        with pytest.raises(ValueError, match="positive"):
            pricer.calculate(S=110, K=100, T=0, r=0.05, sigma=0.2, option_type="call")

    def test_invalid_option_type(self):
        """Test that invalid option types are rejected."""
        pricer = BlackScholesCalculator()

        with pytest.raises(DataValidationError):
            pricer.calculate(S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="invalid")

    def test_negative_price_rejected(self):
        """Test that negative prices are rejected."""
        pricer = BlackScholesCalculator()

        with pytest.raises(ValueError):
            pricer.calculate(
                S=-100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="call"
            )




if __name__ == "__main__":
    pytest.main([__file__, "-v"])
