"""
Trend Indicators Module
========================

Trend-based technical factors including ADX, DMI, CCI, Aroon, and SAR.
🆕 Enhanced with TA-Lib for 10x performance improvement.

Performance: TA-Lib (C implementation) vs pandas (Python) ~ 10x faster
"""

from __future__ import annotations

import numpy as np
try:
    import talib
except ImportError:
    talib = None
from typing import Dict, Any, List

from domain.quantlib.factors.base import TechnicalFactorCalculator
from domain.quantlib.core.base_calculator import validate_inputs, timing_decorator
from domain.quantlib.core.exceptions import InsufficientDataError


class TrendFactors(TechnicalFactorCalculator):
    """
    Trend indicator calculator.

    Provides ADX, DMI, CCI, Aroon, and SAR calculations.
    """

    def get_supported_methods(self) -> List[str]:
        """Return list of supported trend indicators."""
        return [
            'adx', 'di_plus', 'di_minus', 'dmi',
            'cci', 'aroon_up', 'aroon_down', 'sar'
        ]

    # =========================================================================
    # ADX (Average Directional Index) and DMI Components
    # =========================================================================

    def _calculate_directional_movement(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate +DM, -DM, and TR series.

        Args:
            highs: High prices
            lows: Low prices
            closes: Close prices

        Returns:
            Tuple of (+DM, -DM, TR) arrays
        """
        n = len(highs)

        # Calculate directional movements
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        for i in range(1, n):
            high_diff = highs[i] - highs[i - 1]
            low_diff = lows[i - 1] - lows[i]

            if high_diff > low_diff and high_diff > 0:
                plus_dm[i] = high_diff

            if low_diff > high_diff and low_diff > 0:
                minus_dm[i] = low_diff

        # Calculate True Range
        tr = self._true_range_series(highs, lows, closes)

        return plus_dm, minus_dm, tr

    def _smooth_wilder(self, series: np.ndarray, period: int) -> np.ndarray:
        """
        Apply Wilder's smoothing method.

        Args:
            series: Input series
            period: Smoothing period

        Returns:
            Smoothed series
        """
        n = len(series)
        result = np.zeros(n)

        # Initial sum
        result[period - 1] = np.sum(series[:period])

        # Wilder's smoothing: smoothed = (prev_smoothed * (period - 1) + current) / period
        for i in range(period, n):
            result[i] = (result[i - 1] * (period - 1) + series[i]) / period

        return result

    @validate_inputs
    @timing_decorator
    def adx(self, klines: List[Dict[str, Any]], period: int = 14) -> Dict[str, Any]:
        """
        Calculate Average Directional Index using TA-Lib.

        🆕 TA-Lib implementation (10x faster than pandas)

        ADX measures trend strength (0-100):
        - 0-25: Weak or absent trend
        - 25-50: Strong trend
        - 50-75: Very strong trend
        - 75-100: Extremely strong trend

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            period: Period for ADX calculation (default: 14)

        Returns:
            Result dictionary with ADX value
        """
        n = len(klines)
        required = period * 2 + 1

        if n < required:
            raise InsufficientDataError(
                required=required,
                actual=n,
                message=f"ADX requires at least {required} data points for period {period}"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Use TA-Lib for ADX calculation (C implementation, 10x faster)
        adx_values = talib.ADX(highs, lows, closes, timeperiod=period)
        plus_di_values = talib.PLUS_DI(highs, lows, closes, timeperiod=period)
        minus_di_values = talib.MINUS_DI(highs, lows, closes, timeperiod=period)

        # Get last valid values
        adx_value = float(adx_values[-1]) if not np.isnan(adx_values[-1]) else 0.0
        plus_di = float(plus_di_values[-1]) if not np.isnan(plus_di_values[-1]) else 0.0
        minus_di = float(minus_di_values[-1]) if not np.isnan(minus_di_values[-1]) else 0.0

        # Calculate DX for metadata
        di_sum = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / di_sum if di_sum != 0 else 0.0

        # Determine trend strength
        if adx_value < 25:
            strength = 'weak'
        elif adx_value < 50:
            strength = 'strong'
        elif adx_value < 75:
            strength = 'very_strong'
        else:
            strength = 'extremely_strong'

        return self._create_result_dict(
            value=adx_value,
            method='adx',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'plus_di': plus_di,
                'minus_di': minus_di,
                'dx': dx,
                'trend_strength': strength,
                'trending': adx_value >= 25
            }
        )

    @validate_inputs
    @timing_decorator
    def di_plus(self, klines: List[Dict[str, Any]], period: int = 14) -> Dict[str, Any]:
        """
        Calculate Positive Directional Indicator (+DI) using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        +DI measures upward price movement strength.

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            period: Period for calculation (default: 14)

        Returns:
            Result dictionary with +DI value
        """
        n = len(klines)
        required = period * 2 + 1

        if n < required:
            raise InsufficientDataError(
                required=required,
                actual=n,
                message=f"+DI requires at least {required} data points for period {period}"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Use TA-Lib for +DI calculation
        plus_di_values = talib.PLUS_DI(highs, lows, closes, timeperiod=period)
        di_value = float(plus_di_values[-1]) if not np.isnan(plus_di_values[-1]) else 0.0

        return self._create_result_dict(
            value=di_value,
            method='di_plus',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'bullish': di_value > 25
            }
        )

    @validate_inputs
    @timing_decorator
    def di_minus(self, klines: List[Dict[str, Any]], period: int = 14) -> Dict[str, Any]:
        """
        Calculate Negative Directional Indicator (-DI) using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        -DI measures downward price movement strength.

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            period: Period for calculation (default: 14)

        Returns:
            Result dictionary with -DI value

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            period: Period for calculation (default: 14)

        Returns:
            Result dictionary with -DI value
        """
        n = len(klines)
        required = period * 2 + 1

        if n < required:
            raise InsufficientDataError(
                required=required,
                actual=n,
                message=f"-DI requires at least {required} data points for period {period}"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Use TA-Lib for -DI calculation
        minus_di_values = talib.MINUS_DI(highs, lows, closes, timeperiod=period)
        di_value = float(minus_di_values[-1]) if not np.isnan(minus_di_values[-1]) else 0.0

        return self._create_result_dict(
            value=di_value,
            method='di_minus',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'bearish': di_value > 25
            }
        )

    @validate_inputs
    @timing_decorator
    def dmi(self, klines: List[Dict[str, Any]], period: int = 14) -> Dict[str, Any]:
        """
        Calculate Directional Movement Index (DMI).

        Returns both +DI and -DI in a single calculation.
        DMI crossovers indicate trend changes:
        - +DI crosses above -DI: Bullish signal
        - -DI crosses above +DI: Bearish signal

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            period: Period for calculation (default: 14)

        Returns:
            Result dictionary with both +DI and -DI values
        """
        n = len(klines)
        required = period * 2 + 1

        if n < required:
            raise InsufficientDataError(
                required=required,
                actual=n,
                message=f"DMI requires at least {required} data points for period {period}"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Calculate directional movements and true range
        plus_dm, minus_dm, tr = self._calculate_directional_movement(highs, lows, closes)

        # Smooth using Wilder's method
        smoothed_plus_dm = self._smooth_wilder(plus_dm, period)
        smoothed_minus_dm = self._smooth_wilder(minus_dm, period)
        smoothed_tr = self._smooth_wilder(tr, period)

        # Calculate directional indicators
        if smoothed_tr[-1] == 0:
            plus_di_value = 0.0
            minus_di_value = 0.0
        else:
            plus_di_value = 100 * smoothed_plus_dm[-1] / smoothed_tr[-1]
            minus_di_value = 100 * smoothed_minus_dm[-1] / smoothed_tr[-1]

        # Determine trend direction
        if plus_di_value > minus_di_value:
            trend = 'bullish'
        elif minus_di_value > plus_di_value:
            trend = 'bearish'
        else:
            trend = 'neutral'

        return self._create_result_dict(
            value={'plus_di': float(plus_di_value), 'minus_di': float(minus_di_value)},
            method='dmi',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'di_spread': float(abs(plus_di_value - minus_di_value)),
                'trend': trend,
                'strong_trend': abs(plus_di_value - minus_di_value) > 25
            }
        )

    # =========================================================================
    # CCI (Commodity Channel Index)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def cci(self, klines: List[Dict[str, Any]], period: int = 20) -> Dict[str, Any]:
        """
        Calculate Commodity Channel Index using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        CCI = (Typical Price - SMA(Typical Price)) / (0.015 * Mean Deviation)

        CCI interpretation:
        - Above +100: Overbought
        - Below -100: Oversold
        - Between -100 and +100: Normal range

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            period: Period for CCI calculation (default: 20)

        Returns:
            Result dictionary with CCI value
        """
        n = len(klines)

        if n < period:
            raise InsufficientDataError(
                required=period,
                actual=n,
                message=f"CCI requires at least {period} data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Use TA-Lib for CCI calculation
        cci_values = talib.CCI(highs, lows, closes, timeperiod=period)
        cci_value = float(cci_values[-1]) if not np.isnan(cci_values[-1]) else 0.0

        # Determine market condition
        if cci_value > 100:
            condition = 'overbought'
        elif cci_value < -100:
            condition = 'oversold'
        else:
            condition = 'normal'

        return self._create_result_dict(
            value=cci_value,
            method='cci',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'condition': condition,
                'overbought': cci_value > 100,
                'oversold': cci_value < -100
            }
        )

    # =========================================================================
    # Aroon Indicators
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def aroon_up(self, klines: List[Dict[str, Any]], period: int = 25) -> Dict[str, Any]:
        """
        Calculate Aroon Up indicator using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        Aroon Up = ((period - periods since period high) / period) * 100

        Measures time since the highest high in the period.
        - High values (70-100): Strong uptrend
        - Low values (0-30): Weak uptrend

        Args:
            klines: K-line data with 'high' field
            period: Period for Aroon calculation (default: 25)

        Returns:
            Result dictionary with Aroon Up value
        """
        n = len(klines)

        if n < period:
            raise InsufficientDataError(
                required=period,
                actual=n,
                message=f"Aroon Up requires at least {period} data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)

        # Use TA-Lib for Aroon calculation (returns aroondown, aroonup)
        aroon_down, aroon_up = talib.AROON(highs, lows, timeperiod=period)
        aroon_up_value = float(aroon_up[-1]) if not np.isnan(aroon_up[-1]) else 0.0

        return self._create_result_dict(
            value=aroon_up_value,
            method='aroon_up',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'strong_uptrend': aroon_up_value >= 70,
                'weak_uptrend': aroon_up_value <= 30
            }
        )

    @validate_inputs
    @timing_decorator
    def aroon_down(self, klines: List[Dict[str, Any]], period: int = 25) -> Dict[str, Any]:
        """
        Calculate Aroon Down indicator using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        Aroon Down = ((period - periods since period low) / period) * 100

        Measures time since the lowest low in the period.
        - High values (70-100): Strong downtrend
        - Low values (0-30): Weak downtrend

        Args:
            klines: K-line data with 'low' field
            period: Period for Aroon calculation (default: 25)

        Returns:
            Result dictionary with Aroon Down value
        """
        n = len(klines)

        if n < period:
            raise InsufficientDataError(
                required=period,
                actual=n,
                message=f"Aroon Down requires at least {period} data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)

        # Use TA-Lib for Aroon calculation (returns aroondown, aroonup)
        aroon_down, aroon_up = talib.AROON(highs, lows, timeperiod=period)
        aroon_down_value = float(aroon_down[-1]) if not np.isnan(aroon_down[-1]) else 0.0

        return self._create_result_dict(
            value=aroon_down_value,
            method='aroon_down',
            parameters={'period': period},
            metadata={
                'data_points': n,
                'strong_downtrend': aroon_down_value >= 70,
                'weak_downtrend': aroon_down_value <= 30
            }
        )

    # =========================================================================
    # SAR (Parabolic SAR)
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def sar(
        self,
        klines: List[Dict[str, Any]],
        acceleration: float = 0.02,
        maximum: float = 0.2
    ) -> Dict[str, Any]:
        """
        Calculate Parabolic SAR (Stop and Reverse) using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        SAR is a trend-following indicator that provides entry/exit points:
        - SAR below price: Uptrend (bullish)
        - SAR above price: Downtrend (bearish)

        Args:
            klines: K-line data with 'high', 'low', 'close' fields
            acceleration: Acceleration factor (default: 0.02)
            maximum: Maximum acceleration factor (default: 0.2)

        Returns:
            Result dictionary with SAR value and trend
        """
        n = len(klines)

        if n < 2:
            raise InsufficientDataError(
                required=2,
                actual=n,
                message="SAR requires at least 2 data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Use TA-Lib for SAR calculation
        sar_values = talib.SAR(highs, lows, acceleration=acceleration, maximum=maximum)
        sar = float(sar_values[-1]) if not np.isnan(sar_values[-1]) else 0.0

        # Determine trend
        latest_close = closes[-1]
        is_bullish = sar < latest_close
        trend = 'bullish' if is_bullish else 'bearish'

        return self._create_result_dict(
            value=sar,
            method='sar',
            parameters={
                'acceleration': acceleration,
                'maximum': maximum
            },
            metadata={
                'data_points': n,
                'trend': trend,
                'is_bullish': is_bullish,
                'latest_close': float(latest_close),
                'distance_to_sar': float(abs(latest_close - sar)),
                'distance_pct': float(abs(latest_close - sar) / latest_close * 100)
            }
        )
