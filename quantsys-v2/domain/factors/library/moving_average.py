"""
Moving Average Factors
=======================

Simple Moving Average (SMA) and Exponential Moving Average (EMA) factors.
🆕 Enhanced with TA-Lib for 10x performance improvement.

Performance: TA-Lib (C implementation) vs pandas (Python) ~ 10x faster
"""
from __future__ import annotations


from typing import Optional
import numpy as np
try:
    import talib
except ImportError:
    talib = None

from domain.factors.library.base import TechnicalFactorCalculator
from infrastructure.quantlib.core.base_calculator import validate_inputs, timing_decorator


class MovingAverageFactors(TechnicalFactorCalculator):
    """Moving Average factor calculations."""

    def get_supported_methods(self):
        """Get list of supported MA/EMA methods."""
        return [
            'ma5', 'ma10', 'ma20', 'ma60', 'ma120',
            'ema5', 'ema10', 'ema20',
            'calculate_ma', 'calculate_ema'
        ]

    @validate_inputs
    @timing_decorator
    def ma5(self, klines: list[dict]):
        """
        5-day Simple Moving Average.

        Args:
            klines: K-line data

        Returns:
            CalculationResult with MA5 value
        """
        return self.calculate_ma(klines, period=5)

    @validate_inputs
    @timing_decorator
    def ma10(self, klines: list[dict]):
        """
        10-day Simple Moving Average.

        Args:
            klines: K-line data

        Returns:
            CalculationResult with MA10 value
        """
        return self.calculate_ma(klines, period=10)

    @validate_inputs
    @timing_decorator
    def ma20(self, klines: list[dict]):
        """
        20-day Simple Moving Average.

        Args:
            klines: K-line data

        Returns:
            CalculationResult with MA20 value
        """
        return self.calculate_ma(klines, period=20)

    @validate_inputs
    @timing_decorator
    def ma60(self, klines: list[dict]):
        """
        60-day Simple Moving Average.

        Args:
            klines: K-line data

        Returns:
            CalculationResult with MA60 value
        """
        return self.calculate_ma(klines, period=60)

    @validate_inputs
    @timing_decorator
    def ma120(self, klines: list[dict]):
        """
        120-day Simple Moving Average.

        Args:
            klines: K-line data

        Returns:
            CalculationResult with MA120 value
        """
        return self.calculate_ma(klines, period=120)

    @validate_inputs
    @timing_decorator
    def calculate_ma(self, klines: list[dict], period: int = 5):
        """
        Calculate Simple Moving Average for any period.

        Args:
            klines: K-line data
            period: Period for MA calculation

        Returns:
            CalculationResult with MA value
        """
        # Basic validation (no min_length check yet)
        self._validate_klines(klines, min_length=1)
        self._validate_period(period)

        closes = self._extract_closes(klines)
        actual_length = len(closes)

        # Fallback logic: if insufficient data, use all available data
        effective_period = period
        if actual_length < period:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"MA{period}: insufficient data ({actual_length} < {period}), "
                f"using all available data points"
            )
            effective_period = actual_length

        ma_value = self._sma(closes, effective_period)

        return self._create_result_dict(
            value=ma_value,
            method=f'ma{period}',
            parameters={
                'period': period,
                'effective_period': effective_period,
                'fallback_used': effective_period != period
            },
            metadata={
                'data_points': len(klines),
                'latest_close': float(closes[-1]),
                'ma_position': 'above' if closes[-1] > ma_value else 'below'
            }
        )

    @validate_inputs
    @timing_decorator
    def ema5(self, klines: list[dict]):
        """
        5-day Exponential Moving Average.

        Args:
            klines: K-line data

        Returns:
            CalculationResult with EMA5 value
        """
        return self.calculate_ema(klines, period=5)

    @validate_inputs
    @timing_decorator
    def ema10(self, klines: list[dict]):
        """
        10-day Exponential Moving Average.

        Args:
            klines: K-line data

        Returns:
            CalculationResult with EMA10 value
        """
        return self.calculate_ema(klines, period=10)

    @validate_inputs
    @timing_decorator
    def ema20(self, klines: list[dict]):
        """
        20-day Exponential Moving Average.

        Args:
            klines: K-line data

        Returns:
            CalculationResult with EMA20 value
        """
        return self.calculate_ema(klines, period=20)

    @validate_inputs
    @timing_decorator
    def calculate_ema(self, klines: list[dict], period: int = 5):
        """
        Calculate Exponential Moving Average for any period.

        Args:
            klines: K-line data
            period: Period for EMA calculation

        Returns:
            CalculationResult with EMA value
        """
        # Basic validation (no min_length check yet)
        self._validate_klines(klines, min_length=1)
        self._validate_period(period)

        closes = self._extract_closes(klines)
        actual_length = len(closes)

        # Fallback logic: if insufficient data, use all available data
        effective_period = period
        if actual_length < period:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"EMA{period}: insufficient data ({actual_length} < {period}), "
                f"using all available data points"
            )
            effective_period = actual_length

        ema_value = self._ema(closes, effective_period)

        return self._create_result_dict(
            value=ema_value,
            method=f'ema{period}',
            parameters={
                'period': period,
                'effective_period': effective_period,
                'fallback_used': effective_period != period
            },
            metadata={
                'data_points': len(klines),
                'latest_close': float(closes[-1]),
                'ema_position': 'above' if closes[-1] > ema_value else 'below'
            }
        )
