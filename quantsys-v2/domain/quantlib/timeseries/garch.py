"""
GARCH Volatility Modeling Module
=================================

GARCH (Generalized AutoRegressive Conditional Heteroskedasticity) models
for volatility forecasting. Migrated from FinceptTerminal.

Features:
    - GARCH(p,q) volatility modeling
    - EGARCH (Exponential GARCH) for asymmetric effects
    - GJR-GARCH for leverage effects
    - Conditional variance forecasting
    - Volatility clustering detection
    - Risk metrics (VaR, CVaR)

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any, Literal
import warnings

from domain.quantlib.base_calculator import BaseCalculator, validate_inputs, timing_decorator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    ModelFitError,
    CalculationError
)


class GARCHCalculator(BaseCalculator):
    """
    GARCH volatility model calculator.

    GARCH(p,q) models conditional variance:
        σ²_t = ω + Σ(α_i * ε²_{t-i}) + Σ(β_j * σ²_{t-j})

    Where:
        - p: GARCH order (lags of conditional variance)
        - q: ARCH order (lags of squared residuals)
        - ω: Constant term
        - α: ARCH coefficients
        - β: GARCH coefficients

    Variants:
        - GARCH: Standard model
        - EGARCH: Exponential GARCH (asymmetric)
        - GJR-GARCH: Glosten-Jagannathan-Runkle (leverage effects)

    Example:
        calc = GARCHCalculator()
        result = calc.fit(returns, p=1, q=1)
        forecast = calc.forecast_volatility(result, steps=10)
    """

    def get_supported_methods(self) -> List[str]:
        return [
            'fit',
            'forecast_volatility',
            'calculate_var',
            'detect_volatility_clustering',
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
        returns: Union[List, np.ndarray, pd.Series],
        p: int = 1,
        q: int = 1,
        mean_model: Literal['Constant', 'Zero', 'AR', 'ARX'] = 'Constant',
        vol_model: Literal['GARCH', 'EGARCH', 'GJR-GARCH'] = 'GARCH',
        dist: Literal['normal', 't', 'skewt'] = 'normal',
        rescale: bool = True
    ) -> Dict[str, Any]:
        """
        Fit GARCH model to return series.

        Args:
            returns: Return series (not prices)
            p: GARCH order (lags of conditional variance)
            q: ARCH order (lags of squared residuals)
            mean_model: Mean model specification
            vol_model: Volatility model type
            dist: Error distribution
            rescale: Rescale returns to percentage (recommended)

        Returns:
            Result dict with model parameters, conditional volatility, and diagnostics
        """
        try:
            from arch import arch_model
        except ImportError:
            raise ModelFitError(
                "arch package not installed. Install with: pip install arch",
                model_type="GARCH"
            )

        # Validate input
        returns = self._validate_numeric_input(returns, 'returns')
        if isinstance(returns, pd.Series):
            returns_array = returns.values
        elif isinstance(returns, pd.DataFrame):
            if returns.shape[1] != 1:
                raise DataValidationError(
                    "DataFrame must have exactly one column",
                    field_name="returns"
                )
            returns_array = returns.iloc[:, 0].values
        else:
            returns_array = np.array(returns)

        # Check minimum length
        min_length = max(50, p + q + 20)
        if len(returns_array) < min_length:
            raise InsufficientDataError(
                required=min_length,
                provided=len(returns_array),
                calculation="GARCH"
            )

        # Validate parameters
        if p < 1 or q < 1:
            raise DataValidationError(
                "GARCH orders p and q must be at least 1",
                field_name="order"
            )

        if p > 5 or q > 5:
            warnings.warn("Large GARCH orders (p>5 or q>5) may lead to convergence issues")

        try:
            # Scale returns to percentage for numerical stability
            if rescale:
                returns_scaled = returns_array * 100
            else:
                returns_scaled = returns_array

            # Map vol_model to arch package names
            vol_map = {
                'GARCH': 'Garch',
                'EGARCH': 'EGARCH',
                'GJR-GARCH': 'GARCH'  # GJR is a parameter in arch
            }

            # Build model
            model = arch_model(
                returns_scaled,
                mean=mean_model,
                vol=vol_map.get(vol_model, 'Garch'),
                p=p,
                q=q,
                dist=dist,
                o=1 if vol_model == 'GJR-GARCH' else 0  # Asymmetry parameter
            )

            # Fit model
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted_model = model.fit(disp='off', show_warning=False)

            # Extract parameters
            params = {}
            if hasattr(fitted_model.params, 'to_dict'):
                params = fitted_model.params.to_dict()
            else:
                for i, val in enumerate(fitted_model.params):
                    params[f'param_{i}'] = float(val)

            # Conditional volatility
            cond_vol = fitted_model.conditional_volatility

            # Scale back to original units
            if rescale:
                cond_vol_original = cond_vol / 100
            else:
                cond_vol_original = cond_vol

            # Standardized residuals
            std_resid = fitted_model.std_resid

            # Information criteria
            aic = fitted_model.aic
            bic = fitted_model.bic
            loglikelihood = fitted_model.loglikelihood

            # Volatility statistics
            vol_stats = {
                'mean_volatility': float(np.mean(cond_vol_original)),
                'max_volatility': float(np.max(cond_vol_original)),
                'min_volatility': float(np.min(cond_vol_original)),
                'volatility_std': float(np.std(cond_vol_original))
            }

            # Persistence (sum of ARCH and GARCH coefficients)
            persistence = self._calculate_persistence(params, p, q)

            return self._create_result_dict(
                value={
                    'p': p,
                    'q': q,
                    'parameters': {k: round(float(v), self.precision) for k, v in params.items()},
                    'aic': round(aic, self.precision),
                    'bic': round(bic, self.precision),
                    'loglikelihood': round(loglikelihood, self.precision),
                    'conditional_volatility': cond_vol_original.tolist(),
                    'standardized_residuals': std_resid.tolist()
                },
                method='garch_fit',
                parameters={
                    'data_length': len(returns_array),
                    'p': p,
                    'q': q,
                    'mean_model': mean_model,
                    'vol_model': vol_model,
                    'dist': dist
                },
                metadata={
                    'volatility_stats': vol_stats,
                    'persistence': round(persistence, 4),
                    'converged': True,
                    'model_summary': str(fitted_model.summary())
                }
            )

        except Exception as e:
            raise ModelFitError(
                message=f"Failed to fit GARCH model: {str(e)}",
                model_type="GARCH"
            )

    def _calculate_persistence(self, params: Dict[str, float], p: int, q: int) -> float:
        """
        Calculate volatility persistence (sum of ARCH and GARCH coefficients).

        Persistence close to 1 indicates high volatility persistence.
        """
        persistence = 0.0

        # Sum ARCH coefficients (alpha)
        for i in range(1, q + 1):
            key = f'alpha[{i}]'
            if key in params:
                persistence += params[key]

        # Sum GARCH coefficients (beta)
        for j in range(1, p + 1):
            key = f'beta[{j}]'
            if key in params:
                persistence += params[key]

        return persistence

    @validate_inputs
    @timing_decorator
    def forecast_volatility(
        self,
        fitted_result: Dict[str, Any],
        returns: Union[List, np.ndarray, pd.Series],
        steps: int = 10,
        method: Literal['analytic', 'simulation'] = 'analytic',
        simulations: int = 1000
    ) -> Dict[str, Any]:
        """
        Forecast future volatility using fitted GARCH model.

        Args:
            fitted_result: Result from fit() method
            returns: Original return series
            steps: Number of steps to forecast
            method: Forecasting method ('analytic' or 'simulation')
            simulations: Number of simulations (if method='simulation')

        Returns:
            Result dict with volatility forecasts
        """
        try:
            from arch import arch_model
        except ImportError:
            raise ModelFitError(
                "arch package not installed",
                model_type="GARCH"
            )

        # Validate inputs
        returns = self._validate_numeric_input(returns, 'returns')
        if isinstance(returns, pd.Series):
            returns_array = returns.values
        elif isinstance(returns, pd.DataFrame):
            returns_array = returns.iloc[:, 0].values
        else:
            returns_array = np.array(returns)

        if steps < 1:
            raise DataValidationError("steps must be at least 1", field_name="steps")

        # Extract model parameters
        p = fitted_result['value']['p']
        q = fitted_result['value']['q']
        mean_model = fitted_result['parameters'].get('mean_model', 'Constant')
        vol_model = fitted_result['parameters'].get('vol_model', 'GARCH')
        dist = fitted_result['parameters'].get('dist', 'normal')

        try:
            # Scale returns
            returns_scaled = returns_array * 100

            # Rebuild and refit model
            vol_map = {'GARCH': 'Garch', 'EGARCH': 'EGARCH', 'GJR-GARCH': 'GARCH'}
            model = arch_model(
                returns_scaled,
                mean=mean_model,
                vol=vol_map.get(vol_model, 'Garch'),
                p=p,
                q=q,
                dist=dist,
                o=1 if vol_model == 'GJR-GARCH' else 0
            )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted_model = model.fit(disp='off', show_warning=False)

            # Generate forecast
            if method == 'analytic':
                forecast = fitted_model.forecast(horizon=steps, method='analytic')
                variance_forecast = forecast.variance.values[-1, :]
                volatility_forecast = np.sqrt(variance_forecast) / 100  # Scale back

            else:  # simulation
                forecast = fitted_model.forecast(
                    horizon=steps,
                    method='simulation',
                    simulations=simulations
                )
                variance_forecast = forecast.variance.values[-1, :]
                volatility_forecast = np.sqrt(variance_forecast) / 100

            # Calculate forecast statistics
            mean_forecast = float(np.mean(volatility_forecast))
            std_forecast = float(np.std(volatility_forecast))

            return self._create_result_dict(
                value={
                    'volatility_forecast': [round(float(v), self.precision) for v in volatility_forecast],
                    'variance_forecast': [round(float(v**2), self.precision) for v in volatility_forecast]
                },
                method='garch_forecast',
                parameters={
                    'steps': steps,
                    'method': method,
                    'simulations': simulations if method == 'simulation' else None,
                    'p': p,
                    'q': q
                },
                metadata={
                    'mean_forecast': round(mean_forecast, self.precision),
                    'std_forecast': round(std_forecast, self.precision),
                    'forecast_range': round(float(np.max(volatility_forecast) - np.min(volatility_forecast)), self.precision)
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Failed to forecast volatility: {str(e)}",
                calculation_type="garch_forecast"
            )

    @validate_inputs
    @timing_decorator
    def calculate_var(
        self,
        fitted_result: Dict[str, Any],
        returns: Union[List, np.ndarray, pd.Series],
        confidence_level: float = 0.95,
        horizon: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate Value at Risk (VaR) using GARCH volatility forecast.

        Args:
            fitted_result: Result from fit() method
            returns: Original return series
            confidence_level: Confidence level (e.g., 0.95 for 95% VaR)
            horizon: Forecast horizon in days

        Returns:
            Result dict with VaR and CVaR (Conditional VaR)
        """
        from scipy import stats

        # Validate
        confidence_level = self._validate_probability(confidence_level, "confidence_level")

        # Get volatility forecast
        vol_forecast_result = self.forecast_volatility(
            fitted_result,
            returns,
            steps=horizon
        )

        # Extract forecasted volatility
        vol_forecast = vol_forecast_result['value']['volatility_forecast']

        # Calculate VaR for each horizon
        alpha = 1 - confidence_level
        z_score = stats.norm.ppf(alpha)

        var_values = []
        cvar_values = []

        for vol in vol_forecast:
            # VaR = μ + σ * z_score (assuming zero mean)
            var = vol * z_score
            var_values.append(var)

            # CVaR (Expected Shortfall) = E[loss | loss > VaR]
            cvar = vol * stats.norm.pdf(z_score) / alpha
            cvar_values.append(cvar)

        return self._create_result_dict(
            value={
                'var': [round(float(v), self.precision) for v in var_values],
                'cvar': [round(float(c), self.precision) for c in cvar_values],
                'volatility_forecast': [round(float(v), self.precision) for v in vol_forecast]
            },
            method='garch_var',
            parameters={
                'confidence_level': confidence_level,
                'horizon': horizon
            },
            metadata={
                'var_1day': round(float(var_values[0]), self.precision) if var_values else None,
                'cvar_1day': round(float(cvar_values[0]), self.precision) if cvar_values else None,
                'interpretation': f"{confidence_level*100}% VaR: {abs(var_values[0]):.4f}" if var_values else None
            }
        )

    @validate_inputs
    @timing_decorator
    def detect_volatility_clustering(
        self,
        returns: Union[List, np.ndarray, pd.Series],
        window: int = 20
    ) -> Dict[str, Any]:
        """
        Detect volatility clustering in return series.

        Volatility clustering: periods of high volatility tend to cluster together.

        Args:
            returns: Return series
            window: Rolling window size for volatility calculation

        Returns:
            Result dict with clustering metrics and periods
        """
        # Validate
        returns = self._validate_numeric_input(returns, 'returns')
        if isinstance(returns, pd.Series):
            returns_array = returns.values
        elif isinstance(returns, pd.DataFrame):
            returns_array = returns.iloc[:, 0].values
        else:
            returns_array = np.array(returns)

        if len(returns_array) < window * 2:
            raise InsufficientDataError(
                required=window * 2,
                provided=len(returns_array),
                calculation="volatility_clustering"
            )

        # Calculate rolling volatility
        returns_series = pd.Series(returns_array)
        rolling_vol = returns_series.rolling(window=window).std()

        # Identify high volatility periods (> 1.5 * median)
        median_vol = rolling_vol.median()
        high_vol_threshold = median_vol * 1.5

        high_vol_periods = rolling_vol > high_vol_threshold

        # Calculate clustering metric (autocorrelation of squared returns)
        squared_returns = returns_array ** 2
        from statsmodels.tsa.stattools import acf

        acf_squared = acf(squared_returns, nlags=min(20, len(returns_array) // 4))

        # Clustering score (sum of first 5 ACF lags)
        clustering_score = float(np.sum(acf_squared[1:6]))

        return self._create_result_dict(
            value={
                'rolling_volatility': rolling_vol.tolist(),
                'high_volatility_periods': high_vol_periods.tolist(),
                'clustering_score': round(clustering_score, 4)
            },
            method='detect_volatility_clustering',
            parameters={
                'data_length': len(returns_array),
                'window': window
            },
            metadata={
                'median_volatility': round(float(median_vol), self.precision),
                'max_volatility': round(float(rolling_vol.max()), self.precision),
                'high_vol_threshold': round(float(high_vol_threshold), self.precision),
                'n_high_vol_periods': int(high_vol_periods.sum()),
                'has_clustering': clustering_score > 0.1,
                'acf_squared_returns': acf_squared.tolist()
            }
        )

    @validate_inputs
    @timing_decorator
    def compare_models(
        self,
        returns: Union[List, np.ndarray, pd.Series],
        models: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compare different GARCH model specifications.

        Args:
            returns: Return series
            models: List of model specifications (if None, uses default set)

        Returns:
            Result dict with comparison table and best model
        """
        if models is None:
            # Default model specifications to compare
            models = [
                {'p': 1, 'q': 1, 'vol_model': 'GARCH'},
                {'p': 1, 'q': 1, 'vol_model': 'EGARCH'},
                {'p': 1, 'q': 1, 'vol_model': 'GJR-GARCH'},
                {'p': 1, 'q': 2, 'vol_model': 'GARCH'},
                {'p': 2, 'q': 1, 'vol_model': 'GARCH'},
            ]

        results = []
        best_aic = np.inf
        best_model = None

        for model_spec in models:
            try:
                fit_result = self.fit(
                    returns,
                    p=model_spec.get('p', 1),
                    q=model_spec.get('q', 1),
                    vol_model=model_spec.get('vol_model', 'GARCH'),
                    mean_model=model_spec.get('mean_model', 'Constant')
                )

                model_info = {
                    'specification': model_spec,
                    'aic': fit_result['value']['aic'],
                    'bic': fit_result['value']['bic'],
                    'loglikelihood': fit_result['value']['loglikelihood'],
                    'persistence': fit_result['metadata']['persistence']
                }

                results.append(model_info)

                if fit_result['value']['aic'] < best_aic:
                    best_aic = fit_result['value']['aic']
                    best_model = model_spec

            except Exception as e:
                results.append({
                    'specification': model_spec,
                    'aic': None,
                    'bic': None,
                    'error': str(e)
                })

        # Sort by AIC
        results_sorted = sorted(
            [r for r in results if r.get('aic') is not None],
            key=lambda x: x['aic']
        )

        return self._create_result_dict(
            value={
                'comparison_table': results_sorted,
                'best_model': best_model,
                'best_aic': round(best_aic, self.precision) if best_aic != np.inf else None
            },
            method='compare_garch_models',
            parameters={
                'n_models': len(models)
            },
            metadata={
                'models_tested': models,
                'n_successful': len(results_sorted)
            }
        )
