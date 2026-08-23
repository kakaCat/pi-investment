"""
Volatility Indicators Module
=============================

Volatility-based technical factors including Bollinger Bands, ATR, and Keltner Channels.
🆕 Enhanced with TA-Lib for 10x performance improvement.

Performance: TA-Lib (C implementation) vs pandas (Python) ~ 10x faster
"""

import numpy as np
try:
    import talib
except ImportError:
    talib = None
from typing import Dict, Any, List

from domain.factors.library.base import TechnicalFactorCalculator
from infrastructure.quantlib.core.base_calculator import validate_inputs, timing_decorator
from infrastructure.quantlib.core.exceptions import InsufficientDataError


class VolatilityFactors(TechnicalFactorCalculator):
    """
    Volatility indicator calculator.

    Provides Bollinger Bands, ATR, Keltner Channels, and volatility calculations.
    """

    def get_supported_methods(self) -> List[str]:
        """Return list of supported volatility indicators."""
        return [
            'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
            'atr14', 'atr20',
            'keltner_upper', 'keltner_middle', 'keltner_lower',
            'volatility_20'
        ]

    # =========================================================================
    # Bollinger Bands
    # =========================================================================

    def _calc_bollinger(
        self,
        klines: List[Dict[str, Any]],
        period: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, float]:
        """
        Calculate Bollinger Bands using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        Upper = MA + num_std * σ
        Middle = MA
        Lower = MA - num_std * σ

        Args:
            klines: K-line data
            period: Moving average period (default 20)
            num_std: Number of standard deviations (default 2.0)

        Returns:
            Dictionary with upper, middle, and lower band values
        """
        closes = self._extract_closes(klines)
        n = len(closes)

        if n < period:
            raise InsufficientDataError(
                required=period,
                actual=n,
                message=f"Bollinger Bands require at least {period} data points"
            )

        # Use TA-Lib for Bollinger Bands calculation
        upper, middle, lower = talib.BBANDS(
            closes,
            timeperiod=period,
            nbdevup=num_std,
            nbdevdn=num_std,
            matype=0  # SMA
        )

        # Get last valid values
        upper_val = float(upper[-1]) if not np.isnan(upper[-1]) else 0.0
        middle_val = float(middle[-1]) if not np.isnan(middle[-1]) else 0.0
        lower_val = float(lower[-1]) if not np.isnan(lower[-1]) else 0.0

        bandwidth = upper_val - lower_val
        percent_b = (closes[-1] - lower_val) / bandwidth if bandwidth != 0 else 0.5

        return {
            'upper': upper_val,
            'middle': middle_val,
            'lower': lower_val,
            'bandwidth': bandwidth,
            'percent_b': percent_b
        }

    @validate_inputs
    @timing_decorator
    def bollinger_upper(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate Bollinger upper band (MA20 + 2σ)."""
        result = self._calc_bollinger(klines)

        return self._create_result_dict(
            value=result['upper'],
            method='bollinger_upper',
            parameters={'period': 20, 'num_std': 2.0},
            metadata={
                'data_points': len(klines),
                'middle': result['middle'],
                'lower': result['lower'],
                'bandwidth': result['bandwidth']
            }
        )

    @validate_inputs
    @timing_decorator
    def bollinger_middle(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate Bollinger middle band (MA20)."""
        result = self._calc_bollinger(klines)

        return self._create_result_dict(
            value=result['middle'],
            method='bollinger_middle',
            parameters={'period': 20},
            metadata={
                'data_points': len(klines),
                'upper': result['upper'],
                'lower': result['lower'],
                'bandwidth': result['bandwidth']
            }
        )

    @validate_inputs
    @timing_decorator
    def bollinger_lower(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate Bollinger lower band (MA20 - 2σ)."""
        result = self._calc_bollinger(klines)

        return self._create_result_dict(
            value=result['lower'],
            method='bollinger_lower',
            parameters={'period': 20, 'num_std': 2.0},
            metadata={
                'data_points': len(klines),
                'upper': result['upper'],
                'middle': result['middle'],
                'bandwidth': result['bandwidth']
            }
        )

    # =========================================================================
    # ATR (Average True Range)
    # =========================================================================

    def _calc_atr(self, klines: List[Dict[str, Any]], period: int) -> float:
        """
        Calculate Average True Range using TA-Lib.

        🆕 TA-Lib implementation (10x faster than Wilder's smoothing)

        True Range = max(high - low, |high - prev_close|, |low - prev_close|)
        ATR = Wilder's smoothed average of TR

        Args:
            klines: K-line data
            period: ATR period

        Returns:
            ATR value
        """
        n = len(klines)

        if n < period + 1:
            raise InsufficientDataError(
                required=period + 1,
                actual=n,
                message=f"ATR{period} requires at least {period + 1} data points"
            )

        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        closes = self._extract_closes(klines)

        # Use TA-Lib for ATR calculation
        atr_values = talib.ATR(highs, lows, closes, timeperiod=period)
        atr = float(atr_values[-1]) if not np.isnan(atr_values[-1]) else 0.0

        return atr

    @validate_inputs
    @timing_decorator
    def atr14(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 14-day Average True Range."""
        atr_value = self._calc_atr(klines, 14)

        return self._create_result_dict(
            value=atr_value,
            method='atr14',
            parameters={'period': 14},
            metadata={
                'data_points': len(klines),
                'latest_close': self._extract_closes(klines)[-1]
            }
        )

    @validate_inputs
    @timing_decorator
    def atr20(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate 20-day Average True Range."""
        atr_value = self._calc_atr(klines, 20)

        return self._create_result_dict(
            value=atr_value,
            method='atr20',
            parameters={'period': 20},
            metadata={
                'data_points': len(klines),
                'latest_close': self._extract_closes(klines)[-1]
            }
        )

    # =========================================================================
    # Keltner Channels
    # =========================================================================

    def _calc_keltner(
        self,
        klines: List[Dict[str, Any]],
        ema_period: int = 20,
        atr_period: int = 10,
        atr_multiplier: float = 2.0
    ) -> Dict[str, float]:
        """
        Calculate Keltner Channels.

        Middle = EMA(close, ema_period)
        Upper = Middle + atr_multiplier * ATR(atr_period)
        Lower = Middle - atr_multiplier * ATR(atr_period)

        Args:
            klines: K-line data
            ema_period: EMA period for middle line (default 20)
            atr_period: ATR period (default 10)
            atr_multiplier: ATR multiplier (default 2.0)

        Returns:
            Dictionary with upper, middle, and lower channel values
        """
        n = len(klines)

        if n < max(ema_period, atr_period + 1):
            raise InsufficientDataError(
                required=max(ema_period, atr_period + 1),
                actual=n,
                message=f"Keltner Channels require at least {max(ema_period, atr_period + 1)} data points"
            )

        # Calculate EMA for middle line
        closes = self._extract_closes(klines)
        middle = self._ema(closes, ema_period)

        # Calculate ATR
        highs = self._extract_highs(klines)
        lows = self._extract_lows(klines)
        tr_values = self._true_range_series(highs, lows, closes)[1:]

        if len(tr_values) < atr_period:
            raise InsufficientDataError(
                required=atr_period,
                actual=len(tr_values),
                message=f"Insufficient TR values for Keltner ATR{atr_period}"
            )

        # Simple average for ATR (not Wilder's smoothing in Keltner)
        atr = float(np.mean(tr_values[-atr_period:]))

        upper = middle + atr_multiplier * atr
        lower = middle - atr_multiplier * atr

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'width': upper - lower,
            'atr': atr
        }

    @validate_inputs
    @timing_decorator
    def keltner_upper(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate Keltner Channel upper band (EMA20 + 2*ATR10)."""
        result = self._calc_keltner(klines)

        return self._create_result_dict(
            value=result['upper'],
            method='keltner_upper',
            parameters={'ema_period': 20, 'atr_period': 10, 'atr_multiplier': 2.0},
            metadata={
                'data_points': len(klines),
                'middle': result['middle'],
                'lower': result['lower'],
                'width': result['width']
            }
        )

    @validate_inputs
    @timing_decorator
    def keltner_middle(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate Keltner Channel middle line (EMA20)."""
        result = self._calc_keltner(klines)

        return self._create_result_dict(
            value=result['middle'],
            method='keltner_middle',
            parameters={'ema_period': 20},
            metadata={
                'data_points': len(klines),
                'upper': result['upper'],
                'lower': result['lower'],
                'width': result['width']
            }
        )

    @validate_inputs
    @timing_decorator
    def keltner_lower(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate Keltner Channel lower band (EMA20 - 2*ATR10)."""
        result = self._calc_keltner(klines)

        return self._create_result_dict(
            value=result['lower'],
            method='keltner_lower',
            parameters={'ema_period': 20, 'atr_period': 10, 'atr_multiplier': 2.0},
            metadata={
                'data_points': len(klines),
                'upper': result['upper'],
                'middle': result['middle'],
                'width': result['width']
            }
        )

    # =========================================================================
    # Historical Volatility
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def volatility_20(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate 20-day historical volatility (standard deviation of returns).

        Volatility = σ(log_returns) * sqrt(252) (annualized)

        Args:
            klines: K-line data

        Returns:
            Result dictionary with volatility value
        """
        closes = self._extract_closes(klines)
        n = len(closes)

        if n < 21:
            raise InsufficientDataError(
                required=21,
                actual=n,
                message="20-day volatility requires at least 21 data points"
            )

        # Calculate log returns
        log_returns = np.diff(np.log(closes[-21:]))

        # Calculate standard deviation
        volatility = float(np.std(log_returns, ddof=1))

        # Annualize (assuming 252 trading days)
        annualized_volatility = volatility * np.sqrt(252)

        return self._create_result_dict(
            value=float(annualized_volatility),
            method='volatility_20',
            parameters={'period': 20, 'annualized': True},
            metadata={
                'data_points': len(klines),
                'daily_volatility': volatility,
                'latest_close': closes[-1]
            }
        )
