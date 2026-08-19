"""
Factor Calculator Adapter
==========================

Adapter layer that bridges the new BaseCalculator framework with the existing
FactorRegistry system. Provides backward compatibility while enabling gradual
migration to the new framework.

Usage:
    # Use new calculators through the adapter
    adapter = FactorCalculatorAdapter()
    result = adapter.calculate('ma5', klines)

    # Batch calculation
    results = adapter.calculate_batch(['ma5', 'rsi14', 'macd'], klines)
"""

from typing import Dict, Any, List, Optional
import logging

from domain.quantlib.factors.moving_average import MovingAverageFactors
from domain.quantlib.factors.momentum import MomentumFactors
from domain.quantlib.factors.volatility import VolatilityFactors
from domain.quantlib.factors.volume import VolumeFactors
from domain.quantlib.factors.trend import TrendFactors
from domain.quantlib.factors.other import OtherFactors
from domain.quantlib.factors.reversal import ReversalFactors
from domain.quantlib.factors.fundamental import FScoreCalculator, EarningsQualityCalculator

logger = logging.getLogger(__name__)


class FactorCalculatorAdapter:
    """
    Adapter that provides FactorRegistry-compatible interface for new BaseCalculator framework.

    This adapter allows the new factor calculators to be used as drop-in replacements
    for the legacy FactorRegistry system.
    """

    def __init__(self):
        """Initialize all factor calculators."""
        self.calculators = {
            'moving_average': MovingAverageFactors(),
            'momentum': MomentumFactors(),
            'volatility': VolatilityFactors(),
            'volume': VolumeFactors(),
            'trend': TrendFactors(),
            'other': OtherFactors(),
            'reversal': ReversalFactors(),
            'fundamental': {
                'fscore': FScoreCalculator(),
                'earnings_quality': EarningsQualityCalculator()
            }
        }

        # Build factor name to calculator mapping
        self._factor_map = {}
        for calc_name, calc in self.calculators.items():
            # Handle fundamental calculators separately (they're in a dict)
            if calc_name == 'fundamental':
                for factor_name, fund_calc in calc.items():
                    # Fundamental calculators share a single 'calculate' method
                    # that accepts the financial_data dict
                    self._factor_map[factor_name] = (fund_calc, 'calculate')
            else:
                methods = calc.get_supported_methods()
                # Filter out helper methods
                factor_methods = [m for m in methods if not m.startswith('calculate_') and not m.startswith('_')]
                for method_name in factor_methods:
                    self._factor_map[method_name] = (calc, method_name)

        logger.info(f"FactorCalculatorAdapter initialized with {len(self._factor_map)} factors")

    def names(self, category: str = None) -> List[str]:
        """Backward-compatible: get factor names, optionally filtered by category."""
        if category:
            return [n for n in self.get_available_factors()
                    if self.get_factor_info(n)['category'] == category]
        return self.get_available_factors()

    def list_all(self) -> List[Dict[str, str]]:
        """Backward-compatible: list all factors with name and category."""
        return [{'name': info['name'], 'category': info['category']}
                for info in self.get_all_factors_info()]

    def get_available_factors(self) -> List[str]:
        """
        Get list of all available factor names.

        Returns:
            List of factor names that can be calculated
        """
        return sorted(self._factor_map.keys())

    def exists(self, factor_name: str) -> bool:
        """
        Check if a factor exists.

        Args:
            factor_name: Name of the factor

        Returns:
            True if factor exists, False otherwise
        """
        return factor_name in self._factor_map

    def calculate(self, factor_name: str, data: List[Dict[str, Any]], financial_data: Optional[Dict[str, Any]] = None) -> Optional[float]:
        """
        Calculate a single factor value (FactorRegistry-compatible interface).

        Args:
            factor_name: Name of the factor to calculate
            data: K-line data (list of dicts with OHLCV fields) for technical factors,
                  or financial data dict for fundamental factors
            financial_data: Financial data for fundamental factors (optional)

        Returns:
            Factor value as float, or None if calculation fails

        Raises:
            ValueError: If factor_name is not registered
        """
        if factor_name not in self._factor_map:
            raise ValueError(f"Factor '{factor_name}' is not registered")

        calc, method_name = self._factor_map[factor_name]

        try:
            # Check if this is a fundamental factor
            is_fundamental = factor_name in ['fscore', 'earnings_quality']

            if is_fundamental:
                # Use financial_data for fundamental factors
                if financial_data is None:
                    logger.debug(f"No financial data provided for fundamental factor {factor_name}")
                    return None
                method = getattr(calc, method_name)
                result = method(financial_data)
                # Fundamental factors have different return types:
                # - FSCORE: int or None
                # - EarningsQuality: dict with 'total_score' or None
                if factor_name == 'fscore':
                    return float(result) if result is not None else None
                elif factor_name == 'earnings_quality':
                    if isinstance(result, dict) and 'total_score' in result:
                        return float(result['total_score'])
                    return None
                else:
                    return None
            else:
                # Use klines for technical factors
                method = getattr(calc, method_name)
                result = method(data)

            # Extract value from result dict (new format)
            if isinstance(result, dict) and 'value' in result:
                return float(result['value']) if result['value'] is not None else None
            else:
                logger.warning(f"Unexpected result format for {factor_name}: {type(result)}")
                return None

        except Exception as e:
            logger.debug(f"Failed to calculate {factor_name}: {e}")
            return None

    def calculate_batch(
        self,
        factor_names: List[str],
        klines: List[Dict[str, Any]],
        financial_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Optional[float]]:
        """
        Calculate multiple factors in batch (FactorRegistry-compatible interface).

        Args:
            factor_names: List of factor names to calculate
            klines: K-line data
            financial_data: Financial data for fundamental factors (optional)

        Returns:
            Dictionary mapping factor names to their values (or None if failed)
        """
        results = {}

        for factor_name in factor_names:
            try:
                results[factor_name] = self.calculate(factor_name, klines, financial_data)
            except Exception as e:
                logger.debug(f"Failed to calculate {factor_name}: {e}")
                results[factor_name] = None

        return results

    def calculate_with_metadata(
        self,
        factor_name: str,
        klines: List[Dict[str, Any]],
        financial_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate a factor and return full result with metadata (new interface).

        Args:
            factor_name: Name of the factor to calculate
            klines: K-line data
            financial_data: Financial data for fundamental factors (optional)

        Returns:
            Full result dictionary with value, metadata, timestamp, etc.
            Returns None if calculation fails.
        """
        if factor_name not in self._factor_map:
            raise ValueError(f"Factor '{factor_name}' is not registered")

        calc, method_name = self._factor_map[factor_name]

        try:
            # Check if this is a fundamental factor
            is_fundamental = factor_name in ['fscore', 'earnings_quality']

            if is_fundamental:
                if financial_data is None:
                    logger.debug(f"No financial data provided for fundamental factor {factor_name}")
                    return None
                method = getattr(calc, method_name)
                result = method(financial_data)
                # Wrap fundamental factor results for consistent interface
                if factor_name == 'fscore':
                    return {'value': result, 'method': 'fscore', 'metadata': {}}
                elif factor_name == 'earnings_quality':
                    if isinstance(result, dict):
                        wrapped = dict(result)
                        wrapped['value'] = result.get('total_score')
                        return wrapped
                    return None
                else:
                    return None
            else:
                method = getattr(calc, method_name)
                result = method(klines)
            return result
        except Exception as e:
            logger.debug(f"Failed to calculate {factor_name} with metadata: {e}")
            return None

    def calculate_batch_with_metadata(
        self,
        factor_names: List[str],
        klines: List[Dict[str, Any]],
        financial_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Calculate multiple factors with full metadata (new interface).

        Args:
            factor_names: List of factor names to calculate
            klines: K-line data
            financial_data: Financial data for fundamental factors (optional)

        Returns:
            Dictionary mapping factor names to their full result dicts
        """
        results = {}

        for factor_name in factor_names:
            try:
                results[factor_name] = self.calculate_with_metadata(factor_name, klines, financial_data)
            except Exception as e:
                logger.debug(f"Failed to calculate {factor_name} with metadata: {e}")
                results[factor_name] = None

        return results

    def get_factor_info(self, factor_name: str) -> Dict[str, Any]:
        """
        Get information about a factor.

        Args:
            factor_name: Name of the factor

        Returns:
            Dictionary with factor information
        """
        if factor_name not in self._factor_map:
            raise ValueError(f"Factor '{factor_name}' is not registered")

        calc, method_name = self._factor_map[factor_name]

        # Determine category based on calculator type
        calc_type = type(calc).__name__
        category_map = {
            'MovingAverageFactors': 'technical',
            'MomentumFactors': 'technical',
            'VolatilityFactors': 'technical',
            'VolumeFactors': 'technical',
            'TrendFactors': 'technical',
            'OtherFactors': 'technical',
            'FScoreCalculator': 'fundamental',
            'EarningsQualityCalculator': 'fundamental'
        }

        return {
            'name': factor_name,
            'category': category_map.get(calc_type, 'technical'),
            'calculator': calc_type,
            'method': method_name,
            'framework': 'BaseCalculator'
        }

    def get_all_factors_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all available factors.

        Returns:
            List of factor information dictionaries
        """
        return [self.get_factor_info(name) for name in self.get_available_factors()]


# Global singleton instance
_adapter_instance = None


def get_factor_adapter() -> FactorCalculatorAdapter:
    """
    Get the global FactorCalculatorAdapter instance (singleton pattern).

    Returns:
        Global FactorCalculatorAdapter instance
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = FactorCalculatorAdapter()
    return _adapter_instance
