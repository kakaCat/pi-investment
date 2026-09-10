"""
Time Series Analysis Module
============================

Advanced time series analysis tools including ARIMA modeling,
stationarity tests, and trend decomposition.

Inspired by FinceptTerminal's AdvancedQuantAnalyzer.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Literal
from scipy import stats
import warnings

from domain.quantlib.core.base_calculator import (
    BaseCalculator,
    validate_inputs,
    timing_decorator,
    handle_calculation_error
)
from domain.quantlib.core.exceptions import (
    DataValidationError,
    InsufficientDataError,
    CalculationError,
    ModelFitError,
    require_dependency
)


class TimeSeriesAnalyzer(BaseCalculator):
    """
    Time series analysis calculator.

    Provides trend analysis, stationarity tests, and forecasting methods.
    """

    def get_supported_methods(self) -> List[str]:
        return [
            'analyze_trend',
            'test_stationarity',
            'decompose_trend',
            'calculate_autocorrelation',
            'detect_seasonality',
            'fit_arima',
            'predict_arima',
            'fit_garch',
            'fit_var',
            'cointegration_test'
        ]

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def analyze_trend(
        self,
        data: Union[List, np.ndarray, pd.Series],
        trend_type: Literal['linear', 'log_linear'] = 'linear',
        dates: Optional[pd.DatetimeIndex] = None
    ) -> Dict:
        """
        Analyze linear or log-linear trends in time series data.

        Args:
            data: Time series data
            trend_type: 'linear' or 'log_linear'
            dates: Optional datetime index

        Returns:
            Result dict with trend parameters and statistics
        """
        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=10)

        if trend_type not in ['linear', 'log_linear']:
            raise DataValidationError(
                f"Invalid trend_type: {trend_type}",
                "trend_type"
            )

        # Create time index
        if dates is not None:
            time_index = np.arange(len(dates))
        else:
            time_index = np.arange(len(data))

        # Prepare data for regression
        if trend_type == 'log_linear':
            if np.any(data <= 0):
                raise DataValidationError(
                    "Log-linear trend requires positive data",
                    "data"
                )
            y_data = np.log(data)
        else:
            y_data = data

        # Fit trend using OLS
        X = np.column_stack([np.ones(len(time_index)), time_index])
        coefficients = np.linalg.lstsq(X, y_data, rcond=None)[0]

        intercept, slope = coefficients
        fitted_values = intercept + slope * time_index
        residuals = y_data - fitted_values

        # Transform back if log-linear
        if trend_type == 'log_linear':
            fitted_values_original = np.exp(fitted_values)
            residuals_original = data - fitted_values_original
        else:
            fitted_values_original = fitted_values
            residuals_original = residuals

        # Calculate R-squared
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y_data - np.mean(y_data)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        # Statistical tests
        n = len(data)
        mse = ss_res / (n - 2)
        var_slope = mse / np.sum((time_index - np.mean(time_index)) ** 2)
        t_stat = slope / np.sqrt(var_slope) if var_slope > 0 else np.inf
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))

        # Determine trend direction
        if p_value < 0.05:
            if slope > 0:
                trend_direction = 'upward'
            elif slope < 0:
                trend_direction = 'downward'
            else:
                trend_direction = 'flat'
        else:
            trend_direction = 'no_significant_trend'

        return self._create_result_dict(
            value={
                'slope': round(slope, self.precision),
                'intercept': round(intercept, self.precision)
            },
            method=f'{trend_type}_trend',
            parameters={
                'data_length': len(data),
                'trend_type': trend_type
            },
            metadata={
                'fitted_values': fitted_values_original.tolist(),
                'residuals': residuals_original.tolist(),
                'r_squared': round(r_squared, 4),
                'slope_t_statistic': round(t_stat, 4),
                'slope_p_value': round(p_value, 6),
                'trend_significant': p_value < 0.05,
                'trend_direction': trend_direction,
                'mse': round(mse, 6)
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    @require_dependency('statsmodels')
    def test_stationarity(
        self,
        data: Union[List, np.ndarray, pd.Series],
        test_type: Literal['adf', 'kpss', 'both'] = 'both'
    ) -> Dict:
        """
        Test time series for stationarity using ADF and/or KPSS tests.

        Args:
            data: Time series data
            test_type: 'adf', 'kpss', or 'both'

        Returns:
            Result dict with test statistics and conclusions
        """
        from statsmodels.tsa.stattools import adfuller, kpss

        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=20)

        if test_type not in ['adf', 'kpss', 'both']:
            raise DataValidationError(
                f"Invalid test_type: {test_type}",
                "test_type"
            )

        results = {}

        # Augmented Dickey-Fuller test
        if test_type in ['adf', 'both']:
            adf_result = adfuller(data, autolag='AIC')
            results['adf'] = {
                'statistic': round(adf_result[0], 6),
                'p_value': round(adf_result[1], 6),
                'used_lag': int(adf_result[2]),
                'n_obs': int(adf_result[3]),
                'critical_values': {
                    k: round(v, 4) for k, v in adf_result[4].items()
                },
                'is_stationary': adf_result[1] < 0.05
            }

        # KPSS test
        if test_type in ['kpss', 'both']:
            kpss_result = kpss(data, regression='c', nlags='auto')
            results['kpss'] = {
                'statistic': round(kpss_result[0], 6),
                'p_value': round(kpss_result[1], 6),
                'used_lag': int(kpss_result[2]),
                'critical_values': {
                    k: round(v, 4) for k, v in kpss_result[3].items()
                },
                'is_stationary': kpss_result[1] > 0.05
            }

        # Overall conclusion
        if test_type == 'both':
            adf_stationary = results['adf']['is_stationary']
            kpss_stationary = results['kpss']['is_stationary']

            if adf_stationary and kpss_stationary:
                conclusion = 'stationary'
            elif not adf_stationary and not kpss_stationary:
                conclusion = 'non_stationary'
            else:
                conclusion = 'inconclusive'
        elif test_type == 'adf':
            conclusion = 'stationary' if results['adf']['is_stationary'] else 'non_stationary'
        else:
            conclusion = 'stationary' if results['kpss']['is_stationary'] else 'non_stationary'

        return self._create_result_dict(
            value=results,
            method='test_stationarity',
            parameters={
                'data_length': len(data),
                'test_type': test_type
            },
            metadata={
                'conclusion': conclusion,
                'recommendation': self._get_stationarity_recommendation(conclusion)
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    @require_dependency('statsmodels')
    def decompose_trend(
        self,
        data: Union[List, np.ndarray, pd.Series],
        model: Literal['additive', 'multiplicative'] = 'additive',
        period: Optional[int] = None
    ) -> Dict:
        """
        Decompose time series into trend, seasonal, and residual components.

        Args:
            data: Time series data
            model: 'additive' or 'multiplicative'
            period: Seasonal period (auto-detected if None)

        Returns:
            Result dict with decomposed components
        """
        from statsmodels.tsa.seasonal import seasonal_decompose

        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=20)

        if model not in ['additive', 'multiplicative']:
            raise DataValidationError(
                f"Invalid model: {model}",
                "model"
            )

        # Auto-detect period if not provided
        if period is None:
            period = self._detect_period(data)

        # Perform decomposition
        try:
            result = seasonal_decompose(
                data,
                model=model,
                period=period,
                extrapolate_trend='freq'
            )

            return self._create_result_dict(
                value={
                    'trend': result.trend.tolist(),
                    'seasonal': result.seasonal.tolist(),
                    'residual': result.resid.tolist()
                },
                method='decompose_trend',
                parameters={
                    'data_length': len(data),
                    'model': model,
                    'period': period
                },
                metadata={
                    'trend_strength': self._calculate_trend_strength(
                        data, result.trend, result.resid
                    ),
                    'seasonal_strength': self._calculate_seasonal_strength(
                        data, result.seasonal, result.resid
                    )
                }
            )
        except Exception as e:
            raise ModelFitError('seasonal_decompose', str(e))

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def calculate_autocorrelation(
        self,
        data: Union[List, np.ndarray, pd.Series],
        max_lag: Optional[int] = None
    ) -> Dict:
        """
        Calculate autocorrelation function (ACF) and partial autocorrelation (PACF).

        Args:
            data: Time series data
            max_lag: Maximum lag (default: min(10*log10(N), N-1))

        Returns:
            Result dict with ACF and PACF values
        """
        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=20)

        n = len(data)
        if max_lag is None:
            max_lag = min(int(10 * np.log10(n)), n - 1)

        # Calculate ACF
        acf_values = self._calculate_acf(data, max_lag)

        # Calculate PACF
        pacf_values = self._calculate_pacf(data, max_lag)

        # Find significant lags (using 95% confidence interval)
        confidence_interval = 1.96 / np.sqrt(n)
        significant_acf_lags = np.where(np.abs(acf_values[1:]) > confidence_interval)[0] + 1
        significant_pacf_lags = np.where(np.abs(pacf_values[1:]) > confidence_interval)[0] + 1

        return self._create_result_dict(
            value={
                'acf': acf_values.tolist(),
                'pacf': pacf_values.tolist()
            },
            method='calculate_autocorrelation',
            parameters={
                'data_length': n,
                'max_lag': max_lag
            },
            metadata={
                'confidence_interval': round(confidence_interval, 4),
                'significant_acf_lags': significant_acf_lags.tolist(),
                'significant_pacf_lags': significant_pacf_lags.tolist(),
                'has_autocorrelation': len(significant_acf_lags) > 0
            }
        )

    # Helper methods

    def _get_stationarity_recommendation(self, conclusion: str) -> str:
        """Get recommendation based on stationarity test."""
        if conclusion == 'stationary':
            return "Data is stationary. Suitable for ARMA/ARIMA modeling."
        elif conclusion == 'non_stationary':
            return "Data is non-stationary. Consider differencing or detrending."
        else:
            return "Results are inconclusive. Try additional tests or transformations."

    def _detect_period(self, data: np.ndarray) -> int:
        """Auto-detect seasonal period using FFT."""
        # Simple heuristic: use FFT to find dominant frequency
        n = len(data)
        if n < 20:
            return 12  # Default to monthly

        # Detrend data
        detrended = data - np.linspace(data[0], data[-1], n)

        # FFT
        fft = np.fft.fft(detrended)
        power = np.abs(fft[:n // 2]) ** 2

        # Find peak (excluding DC component)
        peak_idx = np.argmax(power[1:]) + 1
        period = n // peak_idx

        # Clamp to reasonable range
        return max(2, min(period, n // 2))

    def _calculate_trend_strength(
        self,
        data: np.ndarray,
        trend: np.ndarray,
        residual: np.ndarray
    ) -> float:
        """Calculate trend strength (0-1)."""
        var_residual = np.nanvar(residual)
        var_detrended = np.nanvar(data - trend)
        if var_detrended == 0:
            return 0.0
        return max(0, 1 - var_residual / var_detrended)

    def _calculate_seasonal_strength(
        self,
        data: np.ndarray,
        seasonal: np.ndarray,
        residual: np.ndarray
    ) -> float:
        """Calculate seasonal strength (0-1)."""
        var_residual = np.nanvar(residual)
        var_deseasoned = np.nanvar(data - seasonal)
        if var_deseasoned == 0:
            return 0.0
        return max(0, 1 - var_residual / var_deseasoned)

    def _calculate_acf(self, data: np.ndarray, max_lag: int) -> np.ndarray:
        """Calculate autocorrelation function."""
        data = data - np.mean(data)
        c0 = np.dot(data, data) / len(data)

        acf = np.ones(max_lag + 1)
        for k in range(1, max_lag + 1):
            c_k = np.dot(data[:-k], data[k:]) / len(data)
            acf[k] = c_k / c0

        return acf

    def _calculate_pacf(self, data: np.ndarray, max_lag: int) -> np.ndarray:
        """Calculate partial autocorrelation function using Yule-Walker."""
        acf = self._calculate_acf(data, max_lag)
        pacf = np.zeros(max_lag + 1)
        pacf[0] = 1.0

        for k in range(1, max_lag + 1):
            # Yule-Walker equations
            if k == 1:
                pacf[k] = acf[1]
            else:
                # Solve for PACF using Levinson-Durbin recursion
                phi = np.zeros(k)
                phi[k-1] = (acf[k] - np.dot(acf[1:k][::-1], phi[:k-1])) / \
                           (1 - np.dot(acf[1:k], phi[:k-1]))
                pacf[k] = phi[k-1]

        return pacf

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    @require_dependency('statsmodels')
    def fit_arima(
        self,
        data: Union[List, np.ndarray, pd.Series],
        order: Tuple[int, int, int] = (1, 0, 1),
        seasonal_order: Optional[Tuple[int, int, int, int]] = None,
        auto_select: bool = False
    ) -> Dict:
        """
        Fit ARIMA model to time series data.

        Args:
            data: Time series data
            order: (p, d, q) order of ARIMA model
            seasonal_order: (P, D, Q, s) seasonal order (optional)
            auto_select: Use auto_arima for automatic order selection

        Returns:
            Result dict with model parameters and diagnostics
        """
        from statsmodels.tsa.arima.model import ARIMA

        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=30)

        try:
            if auto_select:
                # Use pmdarima for auto selection
                try:
                    import pmdarima as pm
                    model = pm.auto_arima(
                        data,
                        seasonal=seasonal_order is not None,
                        m=seasonal_order[3] if seasonal_order else 1,
                        suppress_warnings=True,
                        stepwise=True
                    )
                    order = model.order
                    seasonal_order = model.seasonal_order
                except ImportError:
                    warnings.warn("pmdarima not installed, using specified order")
                    model = ARIMA(data, order=order, seasonal_order=seasonal_order)
                    model = model.fit()
            else:
                model = ARIMA(data, order=order, seasonal_order=seasonal_order)
                model = model.fit()

            # Extract model information
            aic = model.aic
            bic = model.bic
            # Convert params to dict (handle both Series and array)
            if hasattr(model.params, 'to_dict'):
                params = model.params.to_dict()
            else:
                params = {f'param_{i}': float(v) for i, v in enumerate(model.params)}

            # Residual diagnostics
            residuals = model.resid
            ljung_box = model.test_serial_correlation('ljungbox')
            # Extract p-value from ljung_box result (handle both DataFrame and array)
            if hasattr(ljung_box, 'iloc'):
                ljung_box_pvalue = ljung_box.iloc[0, 1]
            elif isinstance(ljung_box, (list, tuple)):
                ljung_box_pvalue = ljung_box[0][1] if len(ljung_box) > 0 else 0.0
            else:
                ljung_box_pvalue = float(ljung_box[1]) if len(ljung_box) > 1 else 0.0

            return self._create_result_dict(
                value={
                    'order': order,
                    'seasonal_order': seasonal_order,
                    'aic': round(aic, self.precision),
                    'bic': round(bic, self.precision),
                    'parameters': {k: round(v, self.precision) for k, v in params.items()}
                },
                method='fit_arima',
                parameters={
                    'data_length': len(data),
                    'order': order,
                    'seasonal_order': seasonal_order,
                    'auto_select': auto_select
                },
                metadata={
                    'residual_mean': round(np.mean(residuals), self.precision),
                    'residual_std': round(np.std(residuals), self.precision),
                    'ljung_box_pvalue': round(ljung_box_pvalue, 4),
                    'model_summary': str(model.summary())
                }
            )
        except Exception as e:
            raise ModelFitError("ARIMA", str(e))

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    @require_dependency('statsmodels')
    def predict_arima(
        self,
        model_result: Dict,
        data: Union[List, np.ndarray, pd.Series],
        steps: int = 10,
        confidence_level: float = 0.95
    ) -> Dict:
        """
        Make predictions using fitted ARIMA model.

        Args:
            model_result: Result from fit_arima()
            data: Original time series data
            steps: Number of steps to forecast
            confidence_level: Confidence level for prediction intervals

        Returns:
            Result dict with forecasts and confidence intervals
        """
        from statsmodels.tsa.arima.model import ARIMA

        # Validate
        data = self._validate_returns(data, "data")
        confidence_level = self._validate_probability(confidence_level, "confidence_level")

        if steps < 1:
            raise DataValidationError("steps must be at least 1", "steps")

        try:
            # Refit model
            order = model_result['value']['order']
            seasonal_order = model_result['value']['seasonal_order']

            model = ARIMA(data, order=order, seasonal_order=seasonal_order)
            fitted_model = model.fit()

            # Make forecast
            forecast = fitted_model.forecast(steps=steps)

            # Get prediction intervals
            forecast_obj = fitted_model.get_forecast(steps=steps)
            pred_int = forecast_obj.conf_int(alpha=1-confidence_level)

            # Handle pred_int (can be DataFrame or array)
            if hasattr(pred_int, 'iloc'):
                lower_bound = pred_int.iloc[:, 0]
                upper_bound = pred_int.iloc[:, 1]
            else:
                lower_bound = pred_int[:, 0]
                upper_bound = pred_int[:, 1]

            return self._create_result_dict(
                value={
                    'forecast': [round(f, self.precision) for f in forecast],
                    'lower_bound': [round(l, self.precision) for l in lower_bound],
                    'upper_bound': [round(u, self.precision) for u in upper_bound]
                },
                method='predict_arima',
                parameters={
                    'steps': steps,
                    'confidence_level': confidence_level,
                    'order': order
                },
                metadata={
                    'forecast_mean': round(np.mean(forecast), self.precision),
                    'forecast_std': round(np.std(forecast), self.precision)
                }
            )
        except Exception as e:
            raise CalculationError("predict_arima", str(e))

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    @require_dependency('arch')
    def fit_garch(
        self,
        returns: Union[List, np.ndarray, pd.Series],
        p: int = 1,
        q: int = 1,
        mean_model: Literal['Constant', 'Zero', 'AR'] = 'Constant'
    ) -> Dict:
        """
        Fit GARCH model to returns data.

        Args:
            returns: Return series
            p: GARCH order
            q: ARCH order
            mean_model: Mean model specification

        Returns:
            Result dict with model parameters and volatility forecast
        """
        from arch import arch_model

        # Validate
        returns = self._validate_returns(returns, "returns")
        self._check_data_length(returns, min_length=50)

        # Scale returns to percentage
        returns_pct = returns * 100

        try:
            # Fit GARCH model
            model = arch_model(
                returns_pct,
                mean=mean_model,
                vol='Garch',
                p=p,
                q=q
            )
            fitted_model = model.fit(disp='off')

            # Extract parameters
            # Convert params to dict (handle both Series and array)
            if hasattr(fitted_model.params, 'to_dict'):
                params = fitted_model.params.to_dict()
            else:
                params = {f'param_{i}': float(v) for i, v in enumerate(fitted_model.params)}

            # Conditional volatility
            cond_vol = fitted_model.conditional_volatility

            # Forecast volatility
            forecast = fitted_model.forecast(horizon=1)
            next_vol = np.sqrt(forecast.variance.values[-1, 0])

            return self._create_result_dict(
                value={
                    'parameters': {k: round(v, self.precision) for k, v in params.items()},
                    'aic': round(fitted_model.aic, self.precision),
                    'bic': round(fitted_model.bic, self.precision),
                    'next_volatility': round(next_vol / 100, self.precision)  # Convert back to decimal
                },
                method='fit_garch',
                parameters={
                    'data_length': len(returns),
                    'p': p,
                    'q': q,
                    'mean_model': mean_model
                },
                metadata={
                    'mean_volatility': round(np.mean(cond_vol) / 100, self.precision),
                    'max_volatility': round(np.max(cond_vol) / 100, self.precision),
                    'min_volatility': round(np.min(cond_vol) / 100, self.precision),
                    'model_summary': str(fitted_model.summary())
                }
            )
        except Exception as e:
            raise ModelFitError("GARCH", str(e))

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    @require_dependency('statsmodels')
    def fit_var(
        self,
        data: pd.DataFrame,
        maxlags: int = 5,
        ic: Literal['aic', 'bic', 'hqic', 'fpe'] = 'aic'
    ) -> Dict:
        """
        Fit Vector Autoregression (VAR) model.

        Args:
            data: DataFrame with multiple time series
            maxlags: Maximum number of lags to consider
            ic: Information criterion for lag selection

        Returns:
            Result dict with model parameters and diagnostics
        """
        from statsmodels.tsa.api import VAR

        # Validate
        if not isinstance(data, pd.DataFrame):
            raise DataValidationError(
                "VAR requires DataFrame with multiple series",
                "data"
            )

        if data.shape[1] < 2:
            raise DataValidationError(
                "VAR requires at least 2 time series",
                "data"
            )

        if len(data) < 30:
            raise InsufficientDataError(
                f"VAR requires at least 30 observations, got {len(data)}",
                "data"
            )

        try:
            # Fit VAR model
            model = VAR(data)
            fitted_model = model.fit(maxlags=maxlags, ic=ic)

            # Extract information
            selected_lag = fitted_model.k_ar
            aic = fitted_model.aic
            bic = fitted_model.bic

            # Granger causality tests
            causality_results = {}
            for col in data.columns:
                try:
                    test = fitted_model.test_causality(col, data.columns.drop(col).tolist())
                    causality_results[col] = {
                        'statistic': float(test.test_statistic),
                        'pvalue': float(test.pvalue)
                    }
                except:
                    pass

            return self._create_result_dict(
                value={
                    'selected_lag': selected_lag,
                    'aic': round(aic, self.precision),
                    'bic': round(bic, self.precision),
                    'n_series': data.shape[1]
                },
                method='fit_var',
                parameters={
                    'data_shape': data.shape,
                    'maxlags': maxlags,
                    'ic': ic,
                    'series_names': data.columns.tolist()
                },
                metadata={
                    'causality_tests': causality_results,
                    'model_summary': str(fitted_model.summary())
                }
            )
        except Exception as e:
            raise ModelFitError("VAR", str(e))

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    @require_dependency('statsmodels')
    def cointegration_test(
        self,
        series1: Union[List, np.ndarray, pd.Series],
        series2: Union[List, np.ndarray, pd.Series],
        method: Literal['engle-granger', 'johansen'] = 'engle-granger'
    ) -> Dict:
        """
        Test for cointegration between two time series.

        Args:
            series1: First time series
            series2: Second time series
            method: Test method ('engle-granger' or 'johansen')

        Returns:
            Result dict with test statistics and cointegration status
        """
        from statsmodels.tsa.stattools import coint

        # Validate
        series1 = self._validate_returns(series1, "series1")
        series2 = self._validate_returns(series2, "series2")

        if len(series1) != len(series2):
            raise DataValidationError(
                f"Series must have same length: {len(series1)} vs {len(series2)}",
                "series_length"
            )

        self._check_data_length(series1, min_length=30)

        try:
            if method == 'engle-granger':
                # Engle-Granger test
                score, pvalue, crit_values = coint(series1, series2)

                # Determine cointegration
                is_cointegrated = pvalue < 0.05

                return self._create_result_dict(
                    value={
                        'test_statistic': round(float(score), self.precision),
                        'p_value': round(float(pvalue), 4),
                        'critical_values': {
                            '1%': round(float(crit_values[0]), self.precision),
                            '5%': round(float(crit_values[1]), self.precision),
                            '10%': round(float(crit_values[2]), self.precision)
                        }
                    },
                    method='cointegration_test',
                    parameters={
                        'data_length': len(series1),
                        'method': method
                    },
                    metadata={
                        'is_cointegrated': is_cointegrated,
                        'alpha': 0.05,
                        'conclusion': 'cointegrated' if is_cointegrated else 'not_cointegrated',
                        'recommendation': 'Series are cointegrated. Consider pairs trading strategy.' if is_cointegrated else 'Series are not cointegrated.'
                    }
                )
            else:
                raise DataValidationError(
                    f"Method '{method}' not yet implemented. Use 'engle-granger'.",
                    "method"
                )
        except Exception as e:
            raise CalculationError("cointegration_test", str(e))
