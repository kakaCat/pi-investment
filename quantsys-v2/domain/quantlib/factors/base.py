"""
Technical Factor Calculator Base Class
=======================================

Base class for all technical factor calculations.
Inherits from BaseCalculator and provides common utilities for K-line data processing.
"""
from __future__ import annotations


from typing import Optional, Union
import numpy as np

from domain.quantlib.core.base_calculator import BaseCalculator
from domain.quantlib.core.exceptions import DataValidationError, InsufficientDataError


class TechnicalFactorCalculator(BaseCalculator):
    """
    Base class for technical factor calculations.

    Provides:
    - K-line data validation
    - OHLCV data extraction
    - Common technical analysis utilities
    - Unified result formatting

    All technical factors should inherit from this class.
    """

    def __init__(self, precision: int = 4):
        """
        Initialize technical factor calculator.

        Args:
            precision: Number of decimal places for results
        """
        super().__init__(precision)

    # =========================================================================
    # Data Validation
    # =========================================================================

    def _validate_klines(self, klines: list[dict], min_length: Optional[int] = None) -> None:
        """
        Validate K-line data format and content.

        Args:
            klines: List of K-line dictionaries
            min_length: Minimum required data points

        Raises:
            DataValidationError: If data format is invalid
            InsufficientDataError: If data length is insufficient
        """
        if not klines:
            raise DataValidationError("K-line data cannot be empty", "klines")

        if not isinstance(klines, list):
            raise DataValidationError("K-line data must be a list", "klines")

        # Check required fields
        required_fields = ['open', 'high', 'low', 'close', 'volume']
        first_kline = klines[0]

        if not isinstance(first_kline, dict):
            raise DataValidationError("Each K-line must be a dictionary", "klines")

        missing_fields = [f for f in required_fields if f not in first_kline]
        if missing_fields:
            raise DataValidationError(
                f"Missing required fields: {', '.join(missing_fields)}",
                "klines"
            )

        # Check minimum length
        if min_length is not None and len(klines) < min_length:
            raise InsufficientDataError(min_length, len(klines))

    def _validate_period(self, period: int, min_period: int = 1, max_period: int = 500) -> None:
        """
        Validate period parameter.

        Args:
            period: Period value to validate
            min_period: Minimum allowed period
            max_period: Maximum allowed period

        Raises:
            DataValidationError: If period is invalid
        """
        if not isinstance(period, int):
            raise DataValidationError("Period must be an integer", "period")

        if period < min_period or period > max_period:
            raise DataValidationError(
                f"Period must be between {min_period} and {max_period}",
                "period"
            )

    # =========================================================================
    # Data Extraction
    # =========================================================================

    def _extract_closes(self, klines: list[dict]) -> np.ndarray:
        """
        Extract close prices from K-line data.

        Args:
            klines: List of K-line dictionaries

        Returns:
            numpy array of close prices
        """
        return np.array([k['close'] for k in klines], dtype=np.float64)

    def _extract_opens(self, klines: list[dict]) -> np.ndarray:
        """
        Extract open prices from K-line data.

        Args:
            klines: List of K-line dictionaries

        Returns:
            numpy array of open prices
        """
        return np.array([k['open'] for k in klines], dtype=np.float64)

    def _extract_highs(self, klines: list[dict]) -> np.ndarray:
        """
        Extract high prices from K-line data.

        Args:
            klines: List of K-line dictionaries

        Returns:
            numpy array of high prices
        """
        return np.array([k['high'] for k in klines], dtype=np.float64)

    def _extract_lows(self, klines: list[dict]) -> np.ndarray:
        """
        Extract low prices from K-line data.

        Args:
            klines: List of K-line dictionaries

        Returns:
            numpy array of low prices
        """
        return np.array([k['low'] for k in klines], dtype=np.float64)

    def _extract_volumes(self, klines: list[dict]) -> np.ndarray:
        """
        Extract volumes from K-line data.

        Args:
            klines: List of K-line dictionaries

        Returns:
            numpy array of volumes
        """
        return np.array([k['volume'] for k in klines], dtype=np.float64)

    # =========================================================================
    # Common Technical Analysis Utilities
    # =========================================================================

    def _sma(self, series: np.ndarray, period: int) -> float:
        """
        Calculate Simple Moving Average using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        Args:
            series: Price series
            period: Period for SMA

        Returns:
            SMA value
        """
        if len(series) < period:
            raise InsufficientDataError(period, len(series))

        import talib
        sma_values = talib.SMA(series, timeperiod=period)
        sma = float(sma_values[-1]) if not np.isnan(sma_values[-1]) else 0.0
        return sma

    def _ema(self, series: np.ndarray, period: int) -> float:
        """
        Calculate Exponential Moving Average using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        Args:
            series: Price series
            period: Period for EMA

        Returns:
            EMA value
        """
        n = len(series)
        if n < period:
            raise InsufficientDataError(period, n)

        import talib
        ema_values = talib.EMA(series, timeperiod=period)
        ema = float(ema_values[-1]) if not np.isnan(ema_values[-1]) else 0.0
        return ema

    def _ema_series(self, series: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate full EMA series using TA-Lib.

        🆕 TA-Lib implementation (10x faster)

        Args:
            series: Price series
            period: Period for EMA

        Returns:
            Full EMA series
        """
        n = len(series)
        if n < period:
            raise InsufficientDataError(period, n)

        import talib
        ema_values = talib.EMA(series, timeperiod=period)
        return ema_values

    def _std(self, series: np.ndarray, period: int) -> float:
        """
        Calculate standard deviation.

        Args:
            series: Price series
            period: Period for std

        Returns:
            Standard deviation value
        """
        if len(series) < period:
            raise InsufficientDataError(period, len(series))

        return float(np.std(series[-period:], ddof=1))

    def _true_range_series(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
        """
        Calculate True Range series.

        Args:
            highs: High prices
            lows: Low prices
            closes: Close prices

        Returns:
            True Range series
        """
        prev_close = np.roll(closes, 1)
        prev_close[0] = closes[0]

        tr1 = highs - lows
        tr2 = np.abs(highs - prev_close)
        tr3 = np.abs(lows - prev_close)

        return np.maximum(np.maximum(tr1, tr2), tr3)

    def _rma(self, series: np.ndarray, period: int) -> float:
        """
        Calculate Wilder's Moving Average (RMA/SMMA).

        Args:
            series: Price series
            period: Period for RMA

        Returns:
            RMA value
        """
        n = len(series)
        if n < period:
            raise InsufficientDataError(period, n)

        alpha = 1.0 / period

        # Seed with SMA
        rma_val = float(np.mean(series[:period]))

        # Apply Wilder's smoothing
        if n > period:
            for v in series[period:]:
                rma_val = alpha * v + (1 - alpha) * rma_val

        return rma_val

    def _typical_price(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
        """
        Calculate Typical Price series.

        Args:
            highs: High prices
            lows: Low prices
            closes: Close prices

        Returns:
            Typical Price series
        """
        return (highs + lows + closes) / 3.0
