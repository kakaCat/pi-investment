"""
ARIMA Time Series Modeling Module
==================================

ARIMA (AutoRegressive Integrated Moving Average) models for time series
forecasting and analysis. Migrated from FinceptTerminal.

Features:
    - ARIMA(p,d,q) parameter estimation
    - SARIMAX with seasonal components
    - Auto ARIMA order selection (AIC/BIC)
    - Forecasting with confidence intervals
    - Residual diagnostics (Ljung-Box, normality tests)
    - Model comparison and selection

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""
import structlog
logger = structlog.get_logger(__name__)

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Any, Literal
import warnings

from domain.quantlib.base_calculator import BaseCalculator, validate_inputs, timing_decorator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    ModelFitError,
    CalculationError
)


class ARIMACalculator(BaseCalculator):
    """
    ARIMA time series model calculator.

    ARIMA(p,d,q) components:
        - p: AutoRegressive order (lags of the series)
        - d: Differencing order (to achieve stationarity)
        - q: Moving Average order (lags of forecast errors)

    Seasonal ARIMA adds (P,D,Q,s):
        - P: Seasonal AR order
        - D: Seasonal differencing order
        - Q: Seasonal MA order
        - s: Seasonal period

    Example:
        calc = ARIMACalculator()
        result = calc.fit(data, order=(1,1,1))
        forecast = calc.forecast(result, data, steps=10)
    """

    def get_supported_methods(self) -> List[str]:
        return [
            'fit',
            'forecast',
            'auto_select_order',
            'diagnose_residuals',
            'compare_models'
        ]

    @validate_inputs
    @timing_decorator
    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Main calculation method. Delegates to fit() by default.
        """
        return self.fit(*args, **kwargs)

    @validate_inputs
    @timing_decorator
    def fit(
        self,
        data: Union[List, np.ndarray, pd.Series],
        order: Tuple[int, int, int] = (1, 1, 1),
        seasonal_order: Optional[Tuple[int, int, int, int]] = None,
        trend: Optional[str] = 'c',
        method: str = 'lbfgs',
        maxiter: int = 50
    ) -> Dict[str, Any]:
        """
        Fit ARIMA model to time series data.

        Args:
            data: Time series data
            order: (p, d, q) ARIMA order
            seasonal_order: (P, D, Q, s) seasonal order (optional)
            trend: Trend component ('n', 'c', 't', 'ct')
            method: Optimization method ('lbfgs', 'bfgs', 'newton', etc.)
            maxiter: Maximum iterations for optimization

        Returns:
            Result dict with model parameters, diagnostics, and fit statistics
        """
        try:
            from statsmodels.tsa.arima.model import ARIMA
            from statsmodels.tsa.statespace.sarimax import SARIMAX
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed. Install with: pip install statsmodels",
                model_type="ARIMA"
            )

        # Validate input
        data = self._validate_numeric_input(data, 'data')
        if isinstance(data, pd.Series):
            data_array = data.values
        elif isinstance(data, pd.DataFrame):
            if data.shape[1] != 1:
                raise DataValidationError(
                    "DataFrame must have exactly one column",
                    field_name="data"
                )
            data_array = data.iloc[:, 0].values
        else:
            data_array = np.array(data)

        # Check minimum length
        min_length = order[0] + order[2] + (seasonal_order[0] + seasonal_order[2] if seasonal_order else 0) + 20
        if len(data_array) < min_length:
            raise InsufficientDataError(
                required=min_length,
                provided=len(data_array),
                calculation="ARIMA"
            )

        # Validate order parameters
        if any(x < 0 for x in order):
            raise DataValidationError(
                "ARIMA order (p,d,q) must be non-negative",
                field_name="order"
            )

        if seasonal_order and any(x < 0 for x in seasonal_order):
            raise DataValidationError(
                "Seasonal order (P,D,Q,s) must be non-negative",
                field_name="seasonal_order"
            )

        # Auto-adjust trend: statsmodels disallows trend terms of lower order
        # than d+D (they would be eliminated by differencing). When d>0 or D>0,
        # set trend='n' (no trend) unless user explicitly requested a higher-order trend.
        d = order[1]
        D = seasonal_order[1] if seasonal_order else 0
        if (d + D) > 0 and trend in (None, 'c'):
            # 'c' (constant) is eliminated by differencing when d+D>0;
            # statsmodels raises ValueError in this case. Use 'n' instead.
            trend = 'n'

        try:
            # Fit model
            if seasonal_order:
                model = SARIMAX(
                    data_array,
                    order=order,
                    seasonal_order=seasonal_order,
                    trend=trend,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )
            else:
                model = ARIMA(
                    data_array,
                    order=order,
                    trend=trend,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # statsmodels ARIMA uses 'method' parameter, not optimizer name
                # Valid methods: None (default MLE), 'css', 'css-mle'
                # For seasonal models, method must be None
                if seasonal_order:
                    fitted_model = model.fit()
                else:
                    fit_method = None if method == 'lbfgs' else method
                    method_kwargs = {'maxiter': maxiter}
                    fitted_model = model.fit(method=fit_method, method_kwargs=method_kwargs)

            # Extract parameters
            params = {}
            if hasattr(fitted_model.params, 'to_dict'):
                params = fitted_model.params.to_dict()
            else:
                for i, val in enumerate(fitted_model.params):
                    params[f'param_{i}'] = float(val)

            # Get fitted values and residuals
            fitted_values = fitted_model.fittedvalues
            residuals = fitted_model.resid

            # Information criteria
            aic = fitted_model.aic
            bic = fitted_model.bic
            hqic = fitted_model.hqic if hasattr(fitted_model, 'hqic') else None

            # Residual diagnostics
            residual_diagnostics = self._diagnose_residuals_internal(residuals)

            # Convergence check
            converged = True
            if hasattr(fitted_model, 'mle_retvals'):
                converged = fitted_model.mle_retvals.get('converged', True)

            return self._create_result_dict(
                value={
                    'order': order,
                    'seasonal_order': seasonal_order,
                    'parameters': {k: round(float(v), self.precision) for k, v in params.items()},
                    'aic': round(aic, self.precision),
                    'bic': round(bic, self.precision),
                    'hqic': round(hqic, self.precision) if hqic else None,
                    'fitted_values': fitted_values.tolist(),
                    'residuals': residuals.tolist()
                },
                method='arima_fit',
                parameters={
                    'data_length': len(data_array),
                    'order': order,
                    'seasonal_order': seasonal_order,
                    'trend': trend,
                    'method': method
                },
                metadata={
                    'converged': converged,
                    'n_params': len(params),
                    'residual_diagnostics': residual_diagnostics,
                    'model_summary': str(fitted_model.summary())
                }
            )

        except Exception as e:
            raise ModelFitError(
                message=f"Failed to fit ARIMA model: {str(e)}",
                model_type="ARIMA"
            )

    @validate_inputs
    @timing_decorator
    def forecast(
        self,
        fitted_result: Dict[str, Any],
        data: Union[List, np.ndarray, pd.Series],
        steps: int = 10,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Generate forecasts from fitted ARIMA model.

        Args:
            fitted_result: Result from fit() method
            data: Original time series data
            steps: Number of steps to forecast
            confidence_level: Confidence level for prediction intervals (0-1)

        Returns:
            Result dict with forecasts and confidence intervals
        """
        try:
            from statsmodels.tsa.arima.model import ARIMA
            from statsmodels.tsa.statespace.sarimax import SARIMAX
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed",
                model_type="ARIMA"
            )

        # Validate inputs
        data = self._validate_numeric_input(data, 'data')
        if isinstance(data, pd.Series):
            data_array = data.values
        elif isinstance(data, pd.DataFrame):
            data_array = data.iloc[:, 0].values
        else:
            data_array = np.array(data)

        if steps < 1:
            raise DataValidationError("steps must be at least 1", field_name="steps")

        confidence_level = self._validate_probability(confidence_level, "confidence_level")

        # Extract model parameters
        order = fitted_result['value']['order']
        seasonal_order = fitted_result['value']['seasonal_order']
        trend = fitted_result['parameters'].get('trend', 'c')

        try:
            # Refit model
            if seasonal_order:
                model = SARIMAX(
                    data_array,
                    order=order,
                    seasonal_order=seasonal_order,
                    trend=trend,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )
            else:
                model = ARIMA(
                    data_array,
                    order=order,
                    trend=trend,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted_model = model.fit()

            # Generate forecast
            forecast_result = fitted_model.get_forecast(steps=steps)
            forecast_mean = forecast_result.predicted_mean

            # Get confidence intervals
            alpha = 1 - confidence_level
            conf_int = forecast_result.conf_int(alpha=alpha)

            if hasattr(conf_int, 'values'):
                lower_bound = conf_int.values[:, 0]
                upper_bound = conf_int.values[:, 1]
            else:
                lower_bound = conf_int[:, 0]
                upper_bound = conf_int[:, 1]

            # Calculate forecast statistics
            forecast_std = forecast_result.se_mean

            return self._create_result_dict(
                value={
                    'forecast': [round(float(f), self.precision) for f in forecast_mean],
                    'lower_bound': [round(float(l), self.precision) for l in lower_bound],
                    'upper_bound': [round(float(u), self.precision) for u in upper_bound],
                    'forecast_std': [round(float(s), self.precision) for s in forecast_std]
                },
                method='arima_forecast',
                parameters={
                    'steps': steps,
                    'confidence_level': confidence_level,
                    'order': order,
                    'seasonal_order': seasonal_order
                },
                metadata={
                    'forecast_mean': round(float(np.mean(forecast_mean)), self.precision),
                    'forecast_range': round(float(np.max(forecast_mean) - np.min(forecast_mean)), self.precision)
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Failed to generate forecast: {str(e)}",
                calculation_type="arima_forecast"
            )

    @validate_inputs
    @timing_decorator
    def auto_select_order(
        self,
        data: Union[List, np.ndarray, pd.Series],
        max_p: int = 5,
        max_d: int = 2,
        max_q: int = 5,
        seasonal: bool = False,
        m: int = 12,
        ic: Literal['aic', 'bic', 'hqic'] = 'aic',
        stepwise: bool = True
    ) -> Dict[str, Any]:
        """
        Automatically select optimal ARIMA order using information criteria.

        Args:
            data: Time series data
            max_p: Maximum AR order to test
            max_d: Maximum differencing order to test
            max_q: Maximum MA order to test
            seasonal: Include seasonal components
            m: Seasonal period (if seasonal=True)
            ic: Information criterion ('aic', 'bic', 'hqic')
            stepwise: Use stepwise search (faster)

        Returns:
            Result dict with optimal order and model comparison
        """
        # Try pmdarima first (better auto ARIMA)
        try:
            import pmdarima as pm

            data = self._validate_numeric_input(data, 'data')
            if isinstance(data, pd.Series):
                data_array = data.values
            elif isinstance(data, pd.DataFrame):
                data_array = data.iloc[:, 0].values
            else:
                data_array = np.array(data)

            self._check_data_length(data_array, min_length=30)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                auto_model = pm.auto_arima(
                    data_array,
                    start_p=0, max_p=max_p,
                    start_q=0, max_q=max_q,
                    max_d=max_d,
                    seasonal=seasonal,
                    m=m if seasonal else 1,
                    information_criterion=ic,
                    stepwise=stepwise,
                    suppress_warnings=True,
                    error_action='ignore',
                    trace=False
                )

            order = auto_model.order
            seasonal_order = auto_model.seasonal_order if seasonal else None

            return self._create_result_dict(
                value={
                    'optimal_order': order,
                    'optimal_seasonal_order': seasonal_order,
                    'aic': round(auto_model.aic(), self.precision),
                    'bic': round(auto_model.bic(), self.precision),
                    'hqic': round(auto_model.hqic(), self.precision) if hasattr(auto_model, 'hqic') else None
                },
                method='auto_arima',
                parameters={
                    'data_length': len(data_array),
                    'max_p': max_p,
                    'max_d': max_d,
                    'max_q': max_q,
                    'seasonal': seasonal,
                    'm': m,
                    'ic': ic,
                    'stepwise': stepwise
                },
                metadata={
                    'n_fits': auto_model.n_fits_ if hasattr(auto_model, 'n_fits_') else None,
                    'model_summary': str(auto_model.summary())
                }
            )

        except ImportError:
            # Fallback to manual grid search
            return self._manual_order_selection(
                data, max_p, max_d, max_q, seasonal, m, ic
            )

    def _manual_order_selection(
        self,
        data: Union[List, np.ndarray, pd.Series],
        max_p: int,
        max_d: int,
        max_q: int,
        seasonal: bool,
        m: int,
        ic: str
    ) -> Dict[str, Any]:
        """
        Manual grid search for optimal ARIMA order.
        Fallback when pmdarima is not available.
        """
        from statsmodels.tsa.arima.model import ARIMA

        data = self._validate_numeric_input(data, 'data')
        if isinstance(data, pd.Series):
            data_array = data.values
        elif isinstance(data, pd.DataFrame):
            data_array = data.iloc[:, 0].values
        else:
            data_array = np.array(data)

        best_ic = np.inf
        best_order = (1, 1, 1)
        results = []

        # Grid search
        for p in range(max_p + 1):
            for d in range(max_d + 1):
                for q in range(max_q + 1):
                    if p == 0 and d == 0 and q == 0:
                        continue

                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            model = ARIMA(data_array, order=(p, d, q))
                            fitted = model.fit(disp=False)

                        if ic == 'aic':
                            ic_value = fitted.aic
                        elif ic == 'bic':
                            ic_value = fitted.bic
                        else:
                            ic_value = fitted.hqic if hasattr(fitted, 'hqic') else fitted.aic

                        results.append({
                            'order': (p, d, q),
                            ic: round(ic_value, 4)
                        })

                        if ic_value < best_ic:
                            best_ic = ic_value
                            best_order = (p, d, q)

                    except Exception:
                        logger.debug("unexpected exception in module", exc_info=True)
                        continue

        return self._create_result_dict(
            value={
                'optimal_order': best_order,
                'optimal_seasonal_order': None,
                ic: round(best_ic, self.precision)
            },
            method='manual_order_selection',
            parameters={
                'data_length': len(data_array),
                'max_p': max_p,
                'max_d': max_d,
                'max_q': max_q,
                'ic': ic
            },
            metadata={
                'n_models_tested': len(results),
                'all_results': results[:10]  # Top 10 results
            }
        )

    def _diagnose_residuals_internal(self, residuals: np.ndarray) -> Dict[str, Any]:
        """
        Internal method to diagnose model residuals.

        Tests:
            - Ljung-Box test for autocorrelation
            - Jarque-Bera test for normality
            - Heteroskedasticity test
        """
        from scipy import stats

        diagnostics = {}

        # Ljung-Box test
        try:
            from statsmodels.stats.diagnostic import acorr_ljungbox
            lb_result = acorr_ljungbox(residuals, lags=min(10, len(residuals) // 5))
            if hasattr(lb_result, 'iloc'):
                diagnostics['ljung_box_pvalue'] = float(lb_result['lb_pvalue'].iloc[-1])
            else:
                diagnostics['ljung_box_pvalue'] = float(lb_result[1][-1])
        except Exception:
            logger.debug("unexpected exception in module", exc_info=True)
            diagnostics['ljung_box_pvalue'] = None

        # Jarque-Bera test for normality
        try:
            jb_stat, jb_pvalue = stats.jarque_bera(residuals)
            diagnostics['jarque_bera_pvalue'] = float(jb_pvalue)
            diagnostics['residuals_normal'] = jb_pvalue > 0.05
        except Exception:
            logger.debug("unexpected exception in module", exc_info=True)
            diagnostics['jarque_bera_pvalue'] = None
            diagnostics['residuals_normal'] = None

        # Basic statistics
        diagnostics['residual_mean'] = float(np.mean(residuals))
        diagnostics['residual_std'] = float(np.std(residuals))
        diagnostics['residual_skewness'] = float(stats.skew(residuals))
        diagnostics['residual_kurtosis'] = float(stats.kurtosis(residuals))

        return diagnostics

    @validate_inputs
    @timing_decorator
    def diagnose_residuals(
        self,
        fitted_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Comprehensive residual diagnostics for fitted ARIMA model.

        Args:
            fitted_result: Result from fit() method

        Returns:
            Result dict with diagnostic tests and plots data
        """
        residuals = np.array(fitted_result['value']['residuals'])

        diagnostics = self._diagnose_residuals_internal(residuals)

        # ACF of residuals
        from statsmodels.tsa.stattools import acf
        acf_values = acf(residuals, nlags=min(20, len(residuals) // 4))

        return self._create_result_dict(
            value=diagnostics,
            method='diagnose_residuals',
            parameters={
                'n_residuals': len(residuals)
            },
            metadata={
                'acf_residuals': acf_values.tolist(),
                'interpretation': self._interpret_diagnostics(diagnostics)
            }
        )

    def _interpret_diagnostics(self, diagnostics: Dict[str, Any]) -> str:
        """Generate human-readable interpretation of diagnostics."""
        issues = []

        if diagnostics.get('ljung_box_pvalue') and diagnostics['ljung_box_pvalue'] < 0.05:
            issues.append("Residuals show significant autocorrelation")

        if diagnostics.get('residuals_normal') is False:
            issues.append("Residuals are not normally distributed")

        if abs(diagnostics.get('residual_mean', 0)) > 0.1:
            issues.append("Residuals have non-zero mean")

        if not issues:
            return "Model residuals pass all diagnostic tests"
        else:
            return "Issues found: " + "; ".join(issues)

    @validate_inputs
    @timing_decorator
    def compare_models(
        self,
        data: Union[List, np.ndarray, pd.Series],
        orders: List[Tuple[int, int, int]]
    ) -> Dict[str, Any]:
        """
        Compare multiple ARIMA models with different orders.

        Args:
            data: Time series data
            orders: List of (p,d,q) tuples to compare

        Returns:
            Result dict with comparison table and best model
        """
        data = self._validate_numeric_input(data, 'data')
        if isinstance(data, pd.Series):
            data_array = data.values
        elif isinstance(data, pd.DataFrame):
            data_array = data.iloc[:, 0].values
        else:
            data_array = np.array(data)

        results = []
        best_aic = np.inf
        best_order = None

        for order in orders:
            try:
                fit_result = self.fit(data_array, order=order)

                results.append({
                    'order': order,
                    'aic': fit_result['value']['aic'],
                    'bic': fit_result['value']['bic'],
                    'converged': fit_result['metadata']['converged']
                })

                if fit_result['value']['aic'] < best_aic:
                    best_aic = fit_result['value']['aic']
                    best_order = order

            except Exception:
                logger.debug("unexpected exception in module", exc_info=True)
                results.append({
                    'order': order,
                    'aic': None,
                    'bic': None,
                    'converged': False,
                    'error': 'Failed to fit'
                })

        return self._create_result_dict(
            value={
                'comparison_table': results,
                'best_order': best_order,
                'best_aic': round(best_aic, self.precision) if best_aic != np.inf else None
            },
            method='compare_models',
            parameters={
                'data_length': len(data_array),
                'n_models': len(orders)
            },
            metadata={
                'orders_tested': orders
            }
        )
