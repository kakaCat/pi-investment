"""
Sentiment Calculator for Prediction Markets
===========================================

Generates sentiment signals from probability time series.
Supports multiple signal generation methods for detecting
trends, breakouts, momentum shifts, and mean reversion.

Methods:
    - exponential_weighted: EWMA smoothing and trend
    - bollinger_band: Breakout signals using Bollinger Bands
    - momentum: Fast/slow momentum crossover
    - mean_reversion: Z-score based mean reversion
"""

import numpy as np
from typing import Dict, List, Any, Optional, Union

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError


class SentimentCalculator(BaseCalculator):
    """Generate sentiment signals from probability time series.

    Converts raw probability data into actionable trading signals
    using multiple technical analysis methods adapted for
    prediction market probability series.

    Example:
        calc = SentimentCalculator()
        result = calc.calculate(
            probability_series=[0.55, 0.58, 0.62, 0.59, 0.65],
            method="exponential_weighted",
            halflife=3
        )
    """

    def __init__(self, precision: int = 6):
        """Initialize sentiment calculator.

        Args:
            precision: Number of decimal places (default 6)
        """
        super().__init__(precision=precision)

    def get_supported_methods(self) -> List[str]:
        """Get supported calculation methods."""
        return [
            "exponential_weighted",
            "bollinger_band",
            "momentum",
            "mean_reversion"
        ]

    def calculate(
        self,
        probability_series: Union[List[float], np.ndarray],
        method: str = "exponential_weighted",
        halflife: int = 7,
        window: int = 20,
        num_std: float = 2.0,
        fast: int = 5,
        slow: int = 20
    ) -> Dict[str, Any]:
        """Calculate sentiment signal from probability series.

        Args:
            probability_series: Time series of probability values
            method: Signal method to use
            halflife: Halflife for exponential weighting (default 7)
            window: Window size for Bollinger/z-score (default 20)
            num_std: Number of standard deviations for Bollinger (default 2.0)
            fast: Fast period for momentum (default 5)
            slow: Slow period for momentum (default 20)

        Returns:
            Standardized result dictionary with signal and metadata

        Raises:
            DataValidationError: If inputs are invalid
            CalculationError: If calculation fails
        """
        self.validate_method(method)

        # Validate series
        series = self._validate_numeric_input(probability_series, "probability_series")
        if isinstance(series, (int, float)):
            raise DataValidationError(
                "probability_series must be a list or array, not a scalar",
                field_name="probability_series"
            )
        self._check_data_length(series, min_length=3)

        try:
            if method == "exponential_weighted":
                result = self._exponential_weighted(series, halflife)
            elif method == "bollinger_band":
                result = self._bollinger_band_signal(series, window, num_std)
            elif method == "momentum":
                result = self._momentum_signal(series, fast, slow)
            elif method == "mean_reversion":
                result = self._mean_reversion_signal(series, window)
            else:
                raise DataValidationError(
                    f"Unknown method: {method}",
                    field_name="method"
                )

            return self._create_result_dict(
                value=result.get("signal", 0.0),
                method=method,
                parameters={
                    "method": method,
                    "halflife": halflife,
                    "window": window,
                    "num_std": num_std,
                    "fast": fast,
                    "slow": slow
                },
                metadata=result
            )
        except (DataValidationError, CalculationError):
            raise
        except Exception as e:
            raise CalculationError(
                str(e),
                calculation_type="sentiment"
            )

    def _exponential_weighted(
        self,
        series: np.ndarray,
        halflife: int
    ) -> Dict[str, Any]:
        """Calculate EWMA smoothed probability and trend.

        Uses exponential decay: weight = 2^(-1/halflife)
        Signal is based on smoothed value and trend direction.

        Args:
            series: Probability time series
            halflife: Decay halflife in periods

        Returns:
            Dictionary with smoothed series, trend, and signal
        """
        n = len(series)

        if n <= 1:
            return {
                "signal": 0.0,
                "smoothed": [self._round_result(float(series[-1]))],
                "trend": 0.0,
                "halflife": halflife,
            }

        alpha = 1 - np.exp(np.log(0.5) / halflife)

        smoothed = np.zeros(n)
        smoothed[0] = series[0]
        for i in range(1, n):
            smoothed[i] = alpha * series[i] + (1 - alpha) * smoothed[i - 1]

        # Signal: use last smoothed value
        # Interpret as bullish (> 0.5) or bearish (< 0.5) or neutral
        last_smoothed = float(smoothed[-1])

        if last_smoothed > 0.65:
            signal = 1.0  # Strong bullish
        elif last_smoothed > 0.55:
            signal = 0.5  # Mild bullish
        elif last_smoothed > 0.45:
            signal = 0.0  # Neutral
        elif last_smoothed > 0.35:
            signal = -0.5  # Mild bearish
        else:
            signal = -1.0  # Strong bearish

        # Trend: slope of last 5 smoothed points
        lookback = min(5, n)
        if lookback >= 2:
            x = np.arange(lookback)
            y = smoothed[-lookback:]
            slope = float(np.polyfit(x, y, 1)[0])
        else:
            slope = 0.0

        trend = 1.0 if slope > 0.005 else (-1.0 if slope < -0.005 else 0.0)

        return {
            "signal": signal,
            "smoothed": self._round_result(smoothed[-10:]),
            "last_smoothed": self._round_result(last_smoothed),
            "trend": trend,
            "ewma_slope": self._round_result(slope),
            "halflife": halflife,
            "alpha": self._round_result(alpha),
        }

    def _bollinger_band_signal(
        self,
        series: np.ndarray,
        window: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, Any]:
        """Generate signals using Bollinger Band analysis.

        A breakout above the upper band suggests bullish sentiment,
        while a breakdown below the lower band suggests bearish sentiment.

        Args:
            series: Probability time series
            window: Rolling window for mean/std
            num_std: Number of standard deviations for bands

        Returns:
            Dictionary with bands and signal
        """
        n = len(series)
        if n < window:
            window = max(2, n)

        rolling_mean = np.convolve(series, np.ones(window) / window, mode="valid")
        series_aligned = series[window - 1:]

        # Manual rolling std
        rolling_std = np.zeros(len(series) - window + 1)
        for i in range(len(rolling_std)):
            rolling_std[i] = np.std(series[i:i + window], ddof=1)

        # Pad the beginning
        padding = window - 1
        padded_mean = np.zeros(n)
        padded_std = np.zeros(n)
        padded_mean[padding:] = rolling_mean
        padded_std[padding:] = rolling_std
        # Fill initial values with first valid
        padded_mean[:padding] = rolling_mean[0] if len(rolling_mean) > 0 else series[0]
        padded_std[:padding] = rolling_std[0] if len(rolling_std) > 0 else 0.0

        upper_band = padded_mean + num_std * padded_std
        lower_band = padded_mean - num_std * padded_std

        # Clamp bands to [0, 1] for probability context
        upper_band = np.clip(upper_band, 0.0, 1.0)
        lower_band = np.clip(lower_band, 0.0, 1.0)

        last_price = float(series[-1])
        last_upper = float(upper_band[-1])
        last_lower = float(lower_band[-1])
        last_mean = float(padded_mean[-1])

        # Signal logic
        if last_price > last_upper:
            signal = 1.0  # Breakout above
        elif last_price < last_lower:
            signal = -1.0  # Breakdown below
        else:
            # Position within bands: -1 to 1
            band_range = last_upper - last_lower
            if band_range > 0:
                rel_pos = (last_price - last_lower) / band_range
                signal = (rel_pos - 0.5) * 2.0  # Map [0,1] to [-1,1]
            else:
                signal = 0.0

        # Bandwidth: relative width of bands
        bandwidth = (last_upper - last_lower) / last_mean if last_mean > 0 else 0.0

        return {
            "signal": self._round_result(signal),
            "upper_band": self._round_result(last_upper),
            "lower_band": self._round_result(last_lower),
            "middle_band": self._round_result(last_mean),
            "last_price": self._round_result(last_price),
            "bandwidth": self._round_result(bandwidth * 100),
            "window": window,
            "num_std": num_std,
        }

    def _momentum_signal(
        self,
        series: np.ndarray,
        fast: int = 5,
        slow: int = 20
    ) -> Dict[str, Any]:
        """Generate signals using fast/slow momentum crossover.

        When fast MA crosses above slow MA, it signals bullish momentum.
        When fast MA crosses below slow MA, it signals bearish momentum.

        Args:
            series: Probability time series
            fast: Fast moving average period
            slow: Slow moving average period

        Returns:
            Dictionary with MAs and signal
        """
        n = len(series)
        if n < slow:
            slow = max(fast + 1, n)

        if n < fast:
            fast = max(2, n)

        def moving_average(data, window):
            if len(data) < window:
                window = len(data)
            return np.convolve(data, np.ones(window) / window, mode="valid")

        fast_ma = moving_average(series, fast)
        slow_ma = moving_average(series, slow)

        # Align lengths
        offset = abs(len(fast_ma) - len(slow_ma))
        if len(fast_ma) > len(slow_ma):
            fast_ma = fast_ma[offset:]
        elif len(slow_ma) > len(fast_ma):
            slow_ma = slow_ma[offset:]

        min_len = min(len(fast_ma), len(slow_ma))
        fast_ma = fast_ma[:min_len]
        slow_ma = slow_ma[:min_len]

        if min_len < 1:
            return {
                "signal": 0.0,
                "fast_ma": self._round_result(float(series[-1])),
                "slow_ma": self._round_result(float(series[-1])),
                "fast": fast,
                "slow": slow,
            }

        last_fast = float(fast_ma[-1])
        last_slow = float(slow_ma[-1])

        # Signal: fast vs slow
        diff = last_fast - last_slow

        # Check for crossover
        crossover = False
        if min_len >= 2:
            prev_fast = float(fast_ma[-2])
            prev_slow = float(slow_ma[-2])
            prev_diff = prev_fast - prev_slow
            if (prev_diff <= 0 and diff > 0):
                crossover = True  # Bullish crossover
            elif (prev_diff >= 0 and diff < 0):
                crossover = True  # Bearish crossover

        # Scale signal: diff normalized by probability scale
        raw_signal = diff * 10.0  # Amplify small differences
        signal = max(-1.0, min(1.0, raw_signal))

        return {
            "signal": self._round_result(signal),
            "fast_ma": self._round_result(last_fast),
            "slow_ma": self._round_result(last_slow),
            "ma_diff": self._round_result(diff),
            "crossover": crossover,
            "fast": fast,
            "slow": slow,
        }

    def _mean_reversion_signal(
        self,
        series: np.ndarray,
        window: int = 20
    ) -> Dict[str, Any]:
        """Generate signals using z-score mean reversion.

        When probability deviates significantly from its mean (high absolute z-score),
        it suggests a reversion is likely. Buy when oversold (low z-score),
        sell when overbought (high z-score).

        Args:
            series: Probability time series
            window: Rolling window for z-score

        Returns:
            Dictionary with z-score and reversion signal
        """
        n = len(series)
        if n < window:
            window = max(2, n)

        # Rolling z-score
        z_scores = np.zeros(n - window + 1)
        for i in range(len(z_scores)):
            chunk = series[i:i + window]
            chunk_mean = np.mean(chunk)
            chunk_std = np.std(chunk, ddof=1)
            if chunk_std > 0:
                z_scores[i] = (series[i + window - 1] - chunk_mean) / chunk_std
            else:
                z_scores[i] = 0.0

        last_z = float(z_scores[-1]) if len(z_scores) > 0 else 0.0

        # Signal: negative for reversion expectation
        # High z-score → overbought → sell signal (negative)
        # Low z-score → oversold → buy signal (positive)
        signal = -np.tanh(last_z / 2.0)

        # Mean reversion strength
        if abs(last_z) > 2.0:
            reversion_strength = "strong"
        elif abs(last_z) > 1.0:
            reversion_strength = "moderate"
        else:
            reversion_strength = "weak"

        return {
            "signal": self._round_result(float(signal)),
            "z_score": self._round_result(last_z),
            "reversion_strength": reversion_strength,
            "window": window,
            "z_score_history": self._round_result(z_scores[-10:]),
        }

    def aggregate_market_probability(
        self,
        market_data: List[Dict[str, Any]],
        method: str = "weighted_average"
    ) -> Dict[str, Any]:
        """Combine probabilities from multiple markets on the same event.

        Useful when the same event is traded on multiple platforms
        (Polymarket + Kalshi) with slightly different prices.

        Args:
            market_data: List of dicts with 'probability' and optional 'volume' keys
            method: Aggregation method ('weighted_average', 'median', 'trimmed_mean')

        Returns:
            Dictionary with aggregated probability
        """
        if not market_data:
            raise DataValidationError(
                "market_data cannot be empty",
                field_name="market_data"
            )

        probabilities = []
        volumes = []
        for item in market_data:
            prob = item.get("probability", 0.0)
            vol = item.get("volume", 1.0)
            probabilities.append(float(prob))
            volumes.append(max(1.0, float(vol)))

        prob_array = np.array(probabilities)
        vol_array = np.array(volumes)
        self._validate_probability(np.clip(prob_array, 0, 1), "probabilities")

        try:
            if method == "weighted_average":
                # Weight by log volume to reduce outlier influence
                log_volumes = np.log1p(vol_array)
                weights = log_volumes / np.sum(log_volumes)
                aggregated = float(np.average(prob_array, weights=weights))
                method_name = "volume_weighted"
            elif method == "median":
                aggregated = float(np.median(prob_array))
                method_name = "median"
            elif method == "trimmed_mean":
                # Trim 20% of extremes
                from scipy import stats as scipy_stats
                aggregated = float(scipy_stats.trim_mean(prob_array, 0.2))
                method_name = "trimmed_mean_20pct"
            else:
                # Simple average
                aggregated = float(np.mean(prob_array))
                method_name = "simple_average"

            # Calculate dispersion as a measure of agreement
            if len(prob_array) > 1:
                dispersion = float(np.std(prob_array, ddof=1))
            else:
                dispersion = 0.0

            return self._create_result_dict(
                value=self._round_result(aggregated),
                method=method_name,
                parameters={
                    "method": method,
                },
                metadata={
                    "num_markets": len(market_data),
                    "individual_probabilities": [self._round_result(p) for p in probabilities],
                    "dispersion": self._round_result(dispersion),
                    "agreement": "high" if dispersion < 0.05 else ("moderate" if dispersion < 0.10 else "low"),
                }
            )
        except (DataValidationError, CalculationError):
            raise
        except Exception as e:
            raise CalculationError(
                str(e),
                calculation_type="aggregate_market_probability"
            )
