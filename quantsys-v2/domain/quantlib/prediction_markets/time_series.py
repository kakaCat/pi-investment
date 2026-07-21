"""
Time Series Calculator for Prediction Markets
=============================================

Analyzes probability time series for prediction markets.
Supports trend decomposition, volatility analysis, forecasting,
and correlation analysis.

Methods:
    - trend_decomposition: Linear regression trend detection
    - volatility: Rolling volatility and clustering analysis
    - forecast: Simple AR(1) forecast with confidence bands
"""

import numpy as np
from typing import Dict, List, Any, Optional, Union

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError


class PMTimeSeriesCalculator(BaseCalculator):
    """Time series analysis for prediction market probabilities.

    Provides trend analysis, volatility measurement, forecasting,
    and correlation tools adapted for probability series.

    Example:
        calc = PMTimeSeriesCalculator()
        result = calc.calculate(
            probability_series=[0.45, 0.48, 0.52, 0.55, 0.58],
            method="trend_decomposition"
        )
    """

    def __init__(self, precision: int = 6):
        """Initialize time series calculator.

        Args:
            precision: Number of decimal places (default 6)
        """
        super().__init__(precision=precision)

    def get_supported_methods(self) -> List[str]:
        """Get supported calculation methods."""
        return ["trend_decomposition", "volatility", "forecast"]

    def calculate(
        self,
        probability_series: Union[List[float], np.ndarray],
        timestamps: Optional[List[Any]] = None,
        method: str = "trend_decomposition",
        horizon: int = 7
    ) -> Dict[str, Any]:
        """Calculate time series metrics for probability data.

        Args:
            probability_series: Time series of probability values
            timestamps: Optional timestamps for the series
            method: 'trend_decomposition', 'volatility', or 'forecast'
            horizon: Forecast horizon in periods (default 7)

        Returns:
            Standardized result dictionary with analysis

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
            if method == "trend_decomposition":
                result = self._trend_decomposition(series)
            elif method == "volatility":
                result = self._volatility_clustering(series)
            elif method == "forecast":
                result = self.calculate_forecast(series, horizon)
            else:
                raise DataValidationError(
                    f"Unknown method: {method}",
                    field_name="method"
                )

            return self._create_result_dict(
                value=result.get("trend_coefficient", result.get("current_volatility", result.get("forecast", 0.0))),
                method=method,
                parameters={
                    "method": method,
                    "num_points": len(series),
                    "horizon": horizon,
                },
                metadata=result
            )
        except (DataValidationError, CalculationError):
            raise
        except Exception as e:
            raise CalculationError(
                str(e),
                calculation_type="pm_time_series"
            )

    def _trend_decomposition(self, series: np.ndarray) -> Dict[str, Any]:
        """Decompose probability series into trend and noise components.

        Uses linear regression to detect the underlying trend.
        The slope indicates direction and rate of change.

        Args:
            series: Probability time series

        Returns:
            Dictionary with trend analysis
        """
        n = len(series)
        x = np.arange(n, dtype=float)

        # Linear regression: y = slope * x + intercept
        x_mean = np.mean(x)
        y_mean = np.mean(series)
        numerator = np.sum((x - x_mean) * (series - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        if denominator <= 0:
            slope = 0.0
            intercept = y_mean
        else:
            slope = numerator / denominator
            intercept = y_mean - slope * x_mean

        # R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((series - y_pred) ** 2)
        ss_tot = np.sum((series - y_mean) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Trend strength: normalize slope relative to probability range
        trend_strength = abs(slope) * n  # Total expected change over series

        # Detrended series (residuals)
        residuals = series - y_pred

        # Trend classification
        if slope > 0.001:
            direction = "upward"
        elif slope < -0.001:
            direction = "downward"
        else:
            direction = "flat"

        if trend_strength > 0.2:
            strength_label = "strong"
        elif trend_strength > 0.05:
            strength_label = "moderate"
        else:
            strength_label = "weak"

        # Recent trend (last 5 points vs overall)
        recent_n = min(5, n)
        if recent_n >= 2:
            recent_x = np.arange(recent_n, dtype=float)
            recent_y = series[-recent_n:]
            recent_x_mean = np.mean(recent_x)
            recent_y_mean = np.mean(recent_y)
            recent_num = np.sum((recent_x - recent_x_mean) * (recent_y - recent_y_mean))
            recent_den = np.sum((recent_x - recent_x_mean) ** 2)
            recent_slope = recent_num / recent_den if recent_den > 0 else 0.0
        else:
            recent_slope = 0.0

        # Acceleration: is trend accelerating or decelerating?
        if abs(slope) > 0.0001:
            acceleration = "accelerating" if abs(recent_slope) > abs(slope) else "decelerating"
        else:
            acceleration = "stable"

        return {
            "trend_coefficient": self._round_result(float(slope)),
            "intercept": self._round_result(float(intercept)),
            "r_squared": self._round_result(float(r_squared)),
            "direction": direction,
            "strength": strength_label,
            "trend_strength_normalized": self._round_result(float(trend_strength)),
            "recent_slope": self._round_result(float(recent_slope)),
            "acceleration": acceleration,
            "start_value": self._round_result(float(series[0])),
            "end_value": self._round_result(float(series[-1])),
            "total_change": self._round_result(float(series[-1] - series[0])),
            "num_points": n,
        }

    def _volatility_clustering(self, series: np.ndarray) -> Dict[str, Any]:
        """Analyze volatility clustering in probability series.

        Uses rolling windows to detect periods of high and low
        volatility, which can indicate market regime changes.

        Args:
            series: Probability time series

        Returns:
            Dictionary with volatility analysis
        """
        n = len(series)

        # Overall volatility metrics
        returns = np.diff(series)
        total_vol = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0

        # Rolling volatility with multiple windows
        windows = [5, 10, 20]
        rolling_vols = {}

        for window in windows:
            if n >= window + 1:
                vols = np.zeros(n - window)
                for i in range(len(vols)):
                    chunk_returns = np.diff(series[i:i + window + 1])
                    vols[i] = np.std(chunk_returns, ddof=1) if len(chunk_returns) > 1 else 0.0
                rolling_vols[f"window_{window}"] = {
                    "latest": self._round_result(float(vols[-1])) if len(vols) > 0 else 0.0,
                    "max": self._round_result(float(np.max(vols))) if len(vols) > 0 else 0.0,
                    "min": self._round_result(float(np.min(vols))) if len(vols) > 0 else 0.0,
                    "mean": self._round_result(float(np.mean(vols))) if len(vols) > 0 else 0.0,
                }

        # Recent volatility (last 10 periods)
        recent = series[-min(10, n):]
        recent_vol = float(np.std(np.diff(recent), ddof=1)) if len(recent) > 1 else 0.0

        # Volatility regime
        if recent_vol > total_vol * 1.5:
            regime = "high_volatility"
        elif recent_vol > total_vol * 0.5:
            regime = "normal"
        else:
            regime = "low_volatility"

        # Volatility of volatility
        if n > 10:
            sub_returns = np.diff(series)
            # Simple vol-of-vol: std of rolling 5-period volatility
            short_vols = []
            for i in range(len(sub_returns) - 5):
                short_vols.append(np.std(sub_returns[i:i + 5], ddof=1))
            vol_of_vol = float(np.std(short_vols, ddof=1)) if len(short_vols) > 1 else 0.0
        else:
            vol_of_vol = 0.0

        return {
            "current_volatility": self._round_result(float(total_vol)),
            "recent_volatility": self._round_result(recent_vol),
            "volatility_regime": regime,
            "volatility_of_volatility": self._round_result(vol_of_vol),
            "rolling_windows": rolling_vols,
            "num_points": n,
            "returns_count": n - 1,
        }

    def calculate_forecast(
        self,
        series: np.ndarray,
        horizon: int = 7
    ) -> Dict[str, Any]:
        """Simple AR(1) forecast for probability series.

        Uses first-order autoregression to predict future values
        with confidence bands based on residual standard deviation.

        Args:
            series: Probability time series
            horizon: Number of periods to forecast (default 7)

        Returns:
            Dictionary with forecast values and confidence bands
        """
        n = len(series)
        if n < 5:
            raise DataValidationError(
                f"Need at least 5 observations for forecast, got {n}",
                field_name="probability_series"
            )

        self._validate_positive(horizon, "horizon")

        # AR(1) model: y_t = phi * y_{t-1} + c + epsilon
        y_lag = series[:-1]
        y_curr = series[1:]

        # Estimate phi (AR coefficient)
        y_lag_mean = np.mean(y_lag)
        y_curr_mean = np.mean(y_curr)

        num = np.sum((y_lag - y_lag_mean) * (y_curr - y_curr_mean))
        den = np.sum((y_lag - y_lag_mean) ** 2)

        if den > 0:
            phi = num / den
        else:
            phi = 0.0

        constant = y_curr_mean - phi * y_lag_mean if den > 0 else y_curr_mean

        # Residual standard deviation
        residuals = y_curr - (phi * y_lag + constant)
        residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.01

        # Generate forecast
        forecasts = []
        lower_band = []
        upper_band = []
        current = float(series[-1])

        for step in range(horizon):
            next_val = phi * current + constant
            # Clamp to [0, 1]
            next_val = max(0.0, min(1.0, next_val))

            # Uncertainty grows with sqrt of horizon
            uncertainty = residual_std * np.sqrt(step + 1)
            lower = max(0.0, next_val - 1.96 * uncertainty)
            upper = min(1.0, next_val + 1.96 * uncertainty)

            forecasts.append(self._round_result(float(next_val)))
            lower_band.append(self._round_result(float(lower)))
            upper_band.append(self._round_result(float(upper)))
            current = next_val

        # Forecast direction
        if len(forecasts) >= 2:
            if forecasts[-1] > forecasts[0] + 0.01:
                forecast_direction = "upward"
            elif forecasts[-1] < forecasts[0] - 0.01:
                forecast_direction = "downward"
            else:
                forecast_direction = "stable"
        else:
            forecast_direction = "stable"

        return {
            "forecast": forecasts,
            "lower_band": lower_band,
            "upper_band": upper_band,
            "horizon": horizon,
            "ar_coefficient": self._round_result(float(phi)),
            "constant": self._round_result(float(constant)),
            "residual_std": self._round_result(float(residual_std)),
            "forecast_direction": forecast_direction,
            "last_observed": self._round_result(float(series[-1])),
            "forecast_final": forecasts[-1] if forecasts else self._round_result(float(series[-1])),
        }

    def calculate_correlation(
        self,
        series_a: Union[List[float], np.ndarray],
        series_b: Union[List[float], np.ndarray]
    ) -> Dict[str, Any]:
        """Calculate rolling correlation between two probability series.

        Useful for comparing prediction market sentiment across
        related events or different platforms.

        Args:
            series_a: First probability series
            series_b: Second probability series

        Returns:
            Dictionary with correlation analysis

        Raises:
            DataValidationError: If inputs are invalid
            CalculationError: If calculation fails
        """
        a = self._validate_numeric_input(series_a, "series_a")
        b = self._validate_numeric_input(series_b, "series_b")

        if isinstance(a, (int, float)) or isinstance(b, (int, float)):
            raise DataValidationError(
                "Both series must be arrays/lists, not scalars",
                field_name="series"
            )

        # Align to common length
        min_len = min(len(a), len(b))
        if min_len < 3:
            raise DataValidationError(
                f"Need at least 3 observations, got {min_len}",
                field_name="series"
            )

        a_aligned = a[:min_len]
        b_aligned = b[:min_len]

        try:
            # Overall correlation
            a_centered = a_aligned - np.mean(a_aligned)
            b_centered = b_aligned - np.mean(b_aligned)

            num = np.sum(a_centered * b_centered)
            den = np.sqrt(np.sum(a_centered**2) * np.sum(b_centered**2))

            if den > 0:
                correlation = num / den
            else:
                correlation = 0.0

            # Rolling correlation (5-period window)
            window = min(5, min_len - 1)
            if min_len > window:
                rolling_corr = np.zeros(min_len - window)
                for i in range(len(rolling_corr)):
                    chunk_a = a_aligned[i:i + window + 1]
                    chunk_b = b_aligned[i:i + window + 1]
                    ca = chunk_a - np.mean(chunk_a)
                    cb = chunk_b - np.mean(chunk_b)
                    n_ = np.sum(ca * cb)
                    d_ = np.sqrt(np.sum(ca**2) * np.sum(cb**2))
                    rolling_corr[i] = n_ / d_ if d_ > 0 else 0.0
            else:
                rolling_corr = np.array([correlation])

            # Lead-lag: check if series_a leads or lags series_b
            if min_len > 2:
                # Correlation with 1-period lag
                lag_1_corr = 0.0
                if min_len > 1:
                    a_lagged = a_aligned[1:]
                    b_early = b_aligned[:-1]
                    ca2 = a_lagged - np.mean(a_lagged)
                    cb2 = b_early - np.mean(b_early)
                    n2 = np.sum(ca2 * cb2)
                    d2 = np.sqrt(np.sum(ca2**2) * np.sum(cb2**2))
                    lag_1_corr = n2 / d2 if d2 > 0 else 0.0

                if abs(correlation) >= abs(lag_1_corr):
                    lead_lag = "contemporaneous"
                elif abs(lag_1_corr) > abs(correlation) and lag_1_corr > 0:
                    lead_lag = "series_b_leads"
                else:
                    lead_lag = "series_a_leads"
            else:
                lead_lag = "insufficient_data"

            # Interpretation
            abs_corr = abs(correlation)
            if abs_corr > 0.7:
                interpretation = "strong"
            elif abs_corr > 0.4:
                interpretation = "moderate"
            else:
                interpretation = "weak"

            return self._create_result_dict(
                value=self._round_result(float(correlation)),
                method="pearson_correlation",
                parameters={
                    "common_length": min_len,
                    "rolling_window": window,
                },
                metadata={
                    "correlation": self._round_result(float(correlation)),
                    "abs_correlation": self._round_result(float(abs_corr)),
                    "interpretation": interpretation,
                    "lead_lag": lead_lag,
                    "lag_1_correlation": self._round_result(float(lag_1_corr)) if min_len > 2 else 0.0,
                    "rolling_correlation_latest": self._round_result(float(rolling_corr[-1])) if len(rolling_corr) > 0 else self._round_result(float(correlation)),
                    "direction": "positive" if correlation > 0 else ("negative" if correlation < 0 else "none"),
                }
            )
        except (DataValidationError, CalculationError):
            raise
        except Exception as e:
            raise CalculationError(
                str(e),
                calculation_type="correlation"
            )
