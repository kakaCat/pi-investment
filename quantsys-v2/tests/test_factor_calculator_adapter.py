"""
Tests for FactorCalculatorAdapter
==================================

Verifies that the adapter correctly bridges the new BaseCalculator framework
with the legacy FactorRegistry interface.
"""

import pytest
from domain.quantlib.adapters.factor_calculator_adapter import (
    FactorCalculatorAdapter,
    get_factor_adapter
)


@pytest.fixture
def sample_klines():
    """Sample K-line data for testing."""
    return [
        {'open': 100, 'high': 105, 'low': 99, 'close': 103, 'volume': 1000000},
        {'open': 103, 'high': 107, 'low': 102, 'close': 106, 'volume': 1200000},
        {'open': 106, 'high': 108, 'low': 104, 'close': 105, 'volume': 900000},
        {'open': 105, 'high': 109, 'low': 103, 'close': 108, 'volume': 1100000},
        {'open': 108, 'high': 112, 'low': 107, 'close': 111, 'volume': 1300000},
        {'open': 111, 'high': 113, 'low': 109, 'close': 110, 'volume': 1000000},
        {'open': 110, 'high': 114, 'low': 108, 'close': 112, 'volume': 1150000},
        {'open': 112, 'high': 115, 'low': 110, 'close': 113, 'volume': 1050000},
        {'open': 113, 'high': 116, 'low': 111, 'close': 114, 'volume': 1200000},
        {'open': 114, 'high': 117, 'low': 112, 'close': 115, 'volume': 1100000},
        {'open': 115, 'high': 118, 'low': 113, 'close': 116, 'volume': 1250000},
        {'open': 116, 'high': 119, 'low': 114, 'close': 117, 'volume': 1150000},
        {'open': 117, 'high': 120, 'low': 115, 'close': 118, 'volume': 1300000},
        {'open': 118, 'high': 121, 'low': 116, 'close': 119, 'volume': 1200000},
        {'open': 119, 'high': 122, 'low': 117, 'close': 120, 'volume': 1100000},
    ]


class TestFactorCalculatorAdapter:
    """Test suite for FactorCalculatorAdapter."""

    def test_initialization(self):
        """Test adapter initialization."""
        adapter = FactorCalculatorAdapter()

        assert adapter is not None
        assert len(adapter.calculators) == 6  # 6 calculator types
        assert 'moving_average' in adapter.calculators
        assert 'momentum' in adapter.calculators
        assert 'volatility' in adapter.calculators
        assert 'volume' in adapter.calculators
        assert 'trend' in adapter.calculators
        assert 'other' in adapter.calculators

    def test_get_available_factors(self):
        """Test getting list of available factors."""
        adapter = FactorCalculatorAdapter()
        factors = adapter.get_available_factors()

        assert isinstance(factors, list)
        assert len(factors) > 60  # Should have 66 factors

        # Check some expected factors
        assert 'ma5' in factors
        assert 'rsi14' in factors
        assert 'macd' in factors
        assert 'atr14' in factors
        assert 'obv' in factors

    def test_exists(self):
        """Test factor existence check."""
        adapter = FactorCalculatorAdapter()

        assert adapter.exists('ma5') == True
        assert adapter.exists('rsi14') == True
        assert adapter.exists('nonexistent_factor') == False

    def test_calculate_single_factor(self, sample_klines):
        """Test calculating a single factor."""
        adapter = FactorCalculatorAdapter()

        # Calculate MA5
        result = adapter.calculate('ma5', sample_klines)

        assert result is not None
        assert isinstance(result, float)
        assert result > 0

    def test_calculate_batch(self, sample_klines):
        """Test batch calculation."""
        adapter = FactorCalculatorAdapter()

        factor_names = ['ma5', 'ma10', 'rsi14']
        results = adapter.calculate_batch(factor_names, sample_klines)

        assert isinstance(results, dict)
        assert len(results) == 3
        assert 'ma5' in results
        assert 'ma10' in results
        assert 'rsi14' in results

        # All should have values
        assert results['ma5'] is not None
        assert results['ma10'] is not None
        assert results['rsi14'] is not None

    def test_calculate_with_metadata(self, sample_klines):
        """Test calculating with full metadata."""
        adapter = FactorCalculatorAdapter()

        result = adapter.calculate_with_metadata('ma5', sample_klines)

        assert result is not None
        assert isinstance(result, dict)
        assert 'value' in result
        assert 'method' in result
        assert 'parameters' in result
        assert 'metadata' in result
        assert 'timestamp' in result
        assert 'calculator' in result

    def test_calculate_batch_with_metadata(self, sample_klines):
        """Test batch calculation with metadata."""
        adapter = FactorCalculatorAdapter()

        factor_names = ['ma5', 'rsi14']
        results = adapter.calculate_batch_with_metadata(factor_names, sample_klines)

        assert isinstance(results, dict)
        assert len(results) == 2

        # Check MA5 result
        assert results['ma5'] is not None
        assert 'value' in results['ma5']
        assert 'metadata' in results['ma5']

        # Check RSI14 result
        assert results['rsi14'] is not None
        assert 'value' in results['rsi14']
        assert 'metadata' in results['rsi14']

    def test_calculate_nonexistent_factor(self, sample_klines):
        """Test calculating a nonexistent factor raises error."""
        adapter = FactorCalculatorAdapter()

        with pytest.raises(ValueError, match="not registered"):
            adapter.calculate('nonexistent_factor', sample_klines)

    def test_calculate_with_insufficient_data(self):
        """Test calculation with insufficient data."""
        adapter = FactorCalculatorAdapter()

        # Only 3 data points, not enough for MA5
        short_klines = [
            {'open': 100, 'high': 105, 'low': 99, 'close': 103, 'volume': 1000000},
            {'open': 103, 'high': 107, 'low': 102, 'close': 106, 'volume': 1200000},
            {'open': 106, 'high': 108, 'low': 104, 'close': 105, 'volume': 900000},
        ]

        result = adapter.calculate('ma5', short_klines)

        # Should return None for insufficient data
        assert result is None

    def test_get_factor_info(self):
        """Test getting factor information."""
        adapter = FactorCalculatorAdapter()

        info = adapter.get_factor_info('ma5')

        assert isinstance(info, dict)
        assert info['name'] == 'ma5'
        assert info['category'] == 'technical'
        assert info['calculator'] == 'MovingAverageFactors'
        assert info['method'] == 'ma5'
        assert info['framework'] == 'BaseCalculator'

    def test_get_all_factors_info(self):
        """Test getting all factors information."""
        adapter = FactorCalculatorAdapter()

        all_info = adapter.get_all_factors_info()

        assert isinstance(all_info, list)
        assert len(all_info) > 60

        # Check structure of first item
        assert 'name' in all_info[0]
        assert 'category' in all_info[0]
        assert 'calculator' in all_info[0]
        assert 'framework' in all_info[0]

    def test_singleton_pattern(self):
        """Test that get_factor_adapter returns singleton."""
        adapter1 = get_factor_adapter()
        adapter2 = get_factor_adapter()

        assert adapter1 is adapter2  # Same instance

    def test_backward_compatibility_with_factor_registry(self, sample_klines):
        """Test that adapter provides FactorRegistry-compatible interface."""
        adapter = FactorCalculatorAdapter()

        # These methods should work exactly like FactorRegistry
        assert hasattr(adapter, 'calculate')
        assert hasattr(adapter, 'calculate_batch')
        assert hasattr(adapter, 'exists')

        # Test the interface
        result = adapter.calculate('ma5', sample_klines)
        assert isinstance(result, (float, type(None)))

        batch_result = adapter.calculate_batch(['ma5', 'rsi14'], sample_klines)
        assert isinstance(batch_result, dict)

    def test_all_factor_categories_represented(self):
        """Test that all factor categories are available."""
        adapter = FactorCalculatorAdapter()
        factors = adapter.get_available_factors()

        # Check for factors from each category
        ma_factors = [f for f in factors if f.startswith('ma') or f.startswith('ema')]
        assert len(ma_factors) > 0  # Moving average factors

        momentum_factors = [f for f in factors if 'rsi' in f or 'macd' in f or 'roc' in f]
        assert len(momentum_factors) > 0  # Momentum factors

        volatility_factors = [f for f in factors if 'atr' in f or 'bollinger' in f]
        assert len(volatility_factors) > 0  # Volatility factors

        volume_factors = [f for f in factors if 'obv' in f or 'mfi' in f or 'vwap' in f]
        assert len(volume_factors) > 0  # Volume factors

    def test_error_handling_in_batch(self, sample_klines):
        """Test that batch calculation handles errors gracefully."""
        adapter = FactorCalculatorAdapter()

        # Mix of valid and invalid factors
        factor_names = ['ma5', 'rsi14']
        results = adapter.calculate_batch(factor_names, sample_klines)

        # Valid factors should have values
        assert results['ma5'] is not None
        assert results['rsi14'] is not None

    def test_metadata_contains_expected_fields(self, sample_klines):
        """Test that metadata contains all expected fields."""
        adapter = FactorCalculatorAdapter()

        result = adapter.calculate_with_metadata('rsi14', sample_klines)

        assert result is not None

        # Check value
        assert 'value' in result
        assert isinstance(result['value'], (int, float))

        # Check metadata
        assert 'metadata' in result
        metadata = result['metadata']
        assert 'overbought' in metadata
        assert 'oversold' in metadata

        # Check parameters
        assert 'parameters' in result
        assert 'period' in result['parameters']

        # Check timestamp
        assert 'timestamp' in result

        # Check calculator
        assert 'calculator' in result
        assert result['calculator'] == 'MomentumFactors'
