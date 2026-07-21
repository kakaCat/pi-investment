"""
Cointegration Testing Module
=============================

Cointegration tests for identifying long-run equilibrium relationships
between non-stationary time series. Migrated from FinceptTerminal.

Features:
    - Engle-Granger two-step cointegration test
    - Johansen cointegration test
    - Cointegrating vector estimation
    - Error correction model (ECM)
    - Pairs trading signal generation

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any, Tuple, Literal
import warnings

from domain.quantlib.base_calculator import BaseCalculator, validate_inputs, timing_decorator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    ModelFitError,
    CalculationError
)


class CointegrationCalculator(BaseCalculator):
    """
    Cointegration testing calculator.

    Cointegration: Two or more non-stationary time series that share
    a common stochastic trend, resulting in a stationary linear combination.

    Applications:
        - Pairs trading strategies
        - Portfolio construction
        - Risk management
        - Economic relationship analysis

    Example:
        calc = CointegrationCalculator()
        result = calc.engle_granger_test(series1, series2)
        if result['value']['is_cointegrated']:
            hedge_ratio = result['value']['cointegrating_vector'][1]
    """

    def get_supported_methods(self) -> List[str]:
        return [
            'engle_granger_test',
            'johansen_test',
            'estimate_ecm',
            'calculate_spread',
            'generate_trading_signals'
        ]

    @validate_inputs
    @timing_decorator
    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Main calculation method. Delegates to engle_granger_test() by default.
        """
        return self.engle_granger_test(*args, **kwargs)

    @validate_inputs
    @timing_decorator
    def engle_granger_test(
        self,
        y: Union[List, np.ndarray, pd.Series],
        x: Union[List, np.ndarray, pd.Series, pd.DataFrame],
        trend: Literal['c', 'ct', 'ctt', 'n'] = 'c',
        maxlag: Optional[int] = None,
        autolag: Optional[str] = 'aic'
    ) -> Dict[str, Any]:
        """
        Engle-Granger two-step cointegration test.

        Step 1: Estimate cointegrating regression y = α + βx + ε
        Step 2: Test residuals for stationarity using ADF test

        Args:
            y: Dependent variable (price series 1)
            x: Independent variable(s) (price series 2, or multiple series)
            trend: Trend specification ('c'=constant, 'ct'=constant+trend, etc.)
            maxlag: Maximum lag for ADF test
            autolag: Lag selection method ('aic', 'bic', etc.)

        Returns:
            Result dict with test statistic, p-value, and cointegrating vector
        """
        try:
            from statsmodels.tsa.stattools import coint
            import statsmodels.api as sm
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed",
                model_type="Cointegration"
            )

        # Validate inputs
        y = self._validate_numeric_input(y, 'y')
        x = self._validate_numeric_input(x, 'x')

        if isinstance(y, pd.Series):
            y_array = y.values
        elif isinstance(y, pd.DataFrame):
            y_array = y.iloc[:, 0].values
        else:
            y_array = np.array(y)

        if isinstance(x, pd.Series):
            x_array = x.values.reshape(-1, 1)
        elif isinstance(x, pd.DataFrame):
            x_array = x.values
        else:
            x_array = np.array(x)
            if x_array.ndim == 1:
                x_array = x_array.reshape(-1, 1)

        # Check lengths match
        if len(y_array) != len(x_array):
            raise DataValidationError(
                f"Series lengths must match: y={len(y_array)}, x={len(x_array)}",
                field_name="series_length"
            )

        # Check minimum length
        min_length = 30
        if len(y_array) < min_length:
            raise InsufficientDataError(
                required=min_length,
                provided=len(y_array),
                calculation="Cointegration"
            )

        try:
            # Step 1: Estimate cointegrating regression
            if trend in ['c', 'ct', 'ctt']:
                X = sm.add_constant(x_array)
            else:
                X = x_array

            ols_model = sm.OLS(y_array, X)
            ols_result = ols_model.fit()

            # Cointegrating vector (beta coefficients)
            cointegrating_vector = ols_result.params.tolist()

            # Residuals from cointegrating regression
            residuals = ols_result.resid

            # Step 2: Test residuals for stationarity (ADF test)
            from statsmodels.tsa.stattools import adfuller

            adf_result = adfuller(
                residuals,
                maxlag=maxlag,
                regression='c',  # Residuals should not have trend
                autolag=autolag
            )

            test_statistic = float(adf_result[0])
            p_value = float(adf_result[1])
            used_lag = int(adf_result[2])
            n_obs = int(adf_result[3])
            critical_values = {k: float(v) for k, v in adf_result[4].items()}

            # Determine cointegration (more stringent than standard ADF)
            # Use 5% critical value
            is_cointegrated = test_statistic < critical_values['5%']

            # Calculate R-squared of cointegrating regression
            r_squared = float(ols_result.rsquared)

            return self._create_result_dict(
                value={
                    'test_statistic': round(test_statistic, self.precision),
                    'p_value': round(p_value, 4),
                    'critical_values': {k: round(v, 4) for k, v in critical_values.items()},
                    'is_cointegrated': is_cointegrated,
                    'cointegrating_vector': [round(float(c), self.precision) for c in cointegrating_vector],
                    'residuals': residuals.tolist()
                },
                method='engle_granger',
                parameters={
                    'data_length': len(y_array),
                    'n_variables': x_array.shape[1],
                    'trend': trend,
                    'maxlag': maxlag,
                    'autolag': autolag
                },
                metadata={
                    'used_lag': used_lag,
                    'n_obs': n_obs,
                    'r_squared': round(r_squared, 4),
                    'conclusion': 'Cointegrated' if is_cointegrated else 'Not cointegrated',
                    'hedge_ratio': round(float(cointegrating_vector[1]), 4) if len(cointegrating_vector) > 1 else None,
                    'interpretation': self._interpret_cointegration(is_cointegrated, cointegrating_vector)
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Engle-Granger test failed: {str(e)}",
                calculation_type="engle_granger"
            )

    @validate_inputs
    @timing_decorator
    def johansen_test(
        self,
        data: pd.DataFrame,
        det_order: int = 0,
        k_ar_diff: int = 1
    ) -> Dict[str, Any]:
        """
        Johansen cointegration test for multiple time series.

        Tests for cointegration among multiple (>2) time series.
        Can identify multiple cointegrating relationships.

        Args:
            data: DataFrame with multiple time series (columns)
            det_order: Deterministic term order (-1=no deterministic, 0=constant, 1=linear trend)
            k_ar_diff: Number of lagged differences in the model

        Returns:
            Result dict with trace statistic, eigenvalues, and cointegrating vectors
        """
        try:
            from statsmodels.tsa.vector_ar.vecm import coint_johansen
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed",
                model_type="Johansen"
            )

        # Validate input
        if not isinstance(data, pd.DataFrame):
            raise DataValidationError(
                "Johansen test requires DataFrame with multiple series",
                field_name="data"
            )

        if data.shape[1] < 2:
            raise DataValidationError(
                "Johansen test requires at least 2 time series",
                field_name="data"
            )

        if len(data) < 30:
            raise InsufficientDataError(
                required=30,
                provided=len(data),
                calculation="Johansen"
            )

        try:
            # Run Johansen test
            result = coint_johansen(data, det_order=det_order, k_ar_diff=k_ar_diff)

            # Extract results
            trace_stat = result.lr1  # Trace statistic
            max_eig_stat = result.lr2  # Maximum eigenvalue statistic
            critical_values_trace = result.cvt  # Critical values for trace
            critical_values_max_eig = result.cvm  # Critical values for max eigenvalue
            eigenvalues = result.eig  # Eigenvalues

            # Cointegrating vectors (beta)
            coint_vectors = result.evec

            # Determine number of cointegrating relationships
            # Compare trace statistic with 5% critical value
            n_coint = 0
            for i in range(len(trace_stat)):
                if trace_stat[i] > critical_values_trace[i, 1]:  # 5% level
                    n_coint += 1

            return self._create_result_dict(
                value={
                    'trace_statistic': [round(float(t), 4) for t in trace_stat],
                    'max_eigenvalue_statistic': [round(float(m), 4) for m in max_eig_stat],
                    'critical_values_trace_90': critical_values_trace[:, 0].tolist(),
                    'critical_values_trace_95': critical_values_trace[:, 1].tolist(),
                    'critical_values_trace_99': critical_values_trace[:, 2].tolist(),
                    'eigenvalues': [round(float(e), 6) for e in eigenvalues],
                    'cointegrating_vectors': coint_vectors.tolist(),
                    'n_cointegrating_relationships': n_coint
                },
                method='johansen',
                parameters={
                    'data_shape': data.shape,
                    'det_order': det_order,
                    'k_ar_diff': k_ar_diff,
                    'series_names': data.columns.tolist()
                },
                metadata={
                    'has_cointegration': n_coint > 0,
                    'interpretation': f"Found {n_coint} cointegrating relationship(s)" if n_coint > 0 else "No cointegration found"
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Johansen test failed: {str(e)}",
                calculation_type="johansen"
            )

    @validate_inputs
    @timing_decorator
    def estimate_ecm(
        self,
        y: Union[List, np.ndarray, pd.Series],
        x: Union[List, np.ndarray, pd.Series],
        lags: int = 1
    ) -> Dict[str, Any]:
        """
        Estimate Error Correction Model (ECM).

        ECM represents short-run dynamics and long-run equilibrium:
        Δy_t = α + β*Δx_t + γ*ECT_{t-1} + ε_t

        Where ECT (Error Correction Term) = y_{t-1} - θ*x_{t-1}

        Args:
            y: Dependent variable
            x: Independent variable
            lags: Number of lags for differenced variables

        Returns:
            Result dict with ECM parameters and adjustment speed
        """
        try:
            import statsmodels.api as sm
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed",
                model_type="ECM"
            )

        # Validate inputs
        y = self._validate_numeric_input(y, 'y')
        x = self._validate_numeric_input(x, 'x')

        if isinstance(y, pd.Series):
            y_array = y.values
        else:
            y_array = np.array(y)

        if isinstance(x, pd.Series):
            x_array = x.values
        else:
            x_array = np.array(x)

        if len(y_array) != len(x_array):
            raise DataValidationError(
                f"Series lengths must match",
                field_name="series_length"
            )

        try:
            # Step 1: Estimate cointegrating relationship
            X_levels = sm.add_constant(x_array)
            ols_levels = sm.OLS(y_array, X_levels).fit()
            residuals = ols_levels.resid

            # Step 2: Estimate ECM
            # Calculate differences
            dy = np.diff(y_array)
            dx = np.diff(x_array)

            # Error correction term (lagged residuals)
            ect = residuals[:-1]

            # Build ECM regression
            X_ecm = np.column_stack([dx, ect])
            X_ecm = sm.add_constant(X_ecm)

            ecm_model = sm.OLS(dy, X_ecm)
            ecm_result = ecm_model.fit()

            # Extract parameters
            params = ecm_result.params
            const = float(params[0])
            beta_dx = float(params[1])  # Short-run effect
            gamma_ect = float(params[2])  # Adjustment speed

            # Adjustment speed should be negative for convergence
            half_life = -np.log(2) / gamma_ect if gamma_ect < 0 else np.inf

            return self._create_result_dict(
                value={
                    'constant': round(const, self.precision),
                    'short_run_effect': round(beta_dx, self.precision),
                    'adjustment_speed': round(gamma_ect, self.precision),
                    'half_life': round(float(half_life), 2) if np.isfinite(half_life) else None,
                    'r_squared': round(float(ecm_result.rsquared), 4),
                    'cointegrating_parameter': round(float(ols_levels.params[1]), self.precision)
                },
                method='ecm',
                parameters={
                    'data_length': len(y_array),
                    'lags': lags
                },
                metadata={
                    'converges': gamma_ect < 0,
                    'interpretation': self._interpret_ecm(gamma_ect, half_life),
                    'model_summary': str(ecm_result.summary())
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"ECM estimation failed: {str(e)}",
                calculation_type="ecm"
            )

    @validate_inputs
    @timing_decorator
    def calculate_spread(
        self,
        y: Union[List, np.ndarray, pd.Series],
        x: Union[List, np.ndarray, pd.Series],
        hedge_ratio: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate cointegration spread for pairs trading.

        Spread = y - hedge_ratio * x

        Args:
            y: First price series
            x: Second price series
            hedge_ratio: Hedge ratio (if None, estimated from data)

        Returns:
            Result dict with spread, z-score, and trading signals
        """
        # Validate inputs
        y = self._validate_numeric_input(y, 'y')
        x = self._validate_numeric_input(x, 'x')

        if isinstance(y, pd.Series):
            y_array = y.values
        else:
            y_array = np.array(y)

        if isinstance(x, pd.Series):
            x_array = x.values
        else:
            x_array = np.array(x)

        if len(y_array) != len(x_array):
            raise DataValidationError(
                "Series lengths must match",
                field_name="series_length"
            )

        try:
            # Estimate hedge ratio if not provided
            if hedge_ratio is None:
                import statsmodels.api as sm
                X = sm.add_constant(x_array)
                ols_result = sm.OLS(y_array, X).fit()
                hedge_ratio = float(ols_result.params[1])

            # Calculate spread
            spread = y_array - hedge_ratio * x_array

            # Calculate z-score
            spread_mean = np.mean(spread)
            spread_std = np.std(spread)
            z_score = (spread - spread_mean) / spread_std if spread_std > 0 else np.zeros_like(spread)

            # Calculate spread statistics
            spread_stats = {
                'mean': float(spread_mean),
                'std': float(spread_std),
                'min': float(np.min(spread)),
                'max': float(np.max(spread)),
                'current': float(spread[-1]),
                'current_z_score': float(z_score[-1])
            }

            return self._create_result_dict(
                value={
                    'spread': spread.tolist(),
                    'z_score': z_score.tolist(),
                    'hedge_ratio': round(hedge_ratio, self.precision)
                },
                method='calculate_spread',
                parameters={
                    'data_length': len(y_array),
                    'hedge_ratio_estimated': hedge_ratio is None
                },
                metadata={
                    'spread_stats': {k: round(v, self.precision) for k, v in spread_stats.items()}
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Spread calculation failed: {str(e)}",
                calculation_type="calculate_spread"
            )

    @validate_inputs
    @timing_decorator
    def generate_trading_signals(
        self,
        spread_result: Dict[str, Any],
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Generate pairs trading signals from cointegration spread.

        Trading logic:
            - Long spread when z-score < -entry_threshold
            - Short spread when z-score > entry_threshold
            - Exit when |z-score| < exit_threshold

        Args:
            spread_result: Result from calculate_spread()
            entry_threshold: Z-score threshold for entry (absolute value)
            exit_threshold: Z-score threshold for exit (absolute value)

        Returns:
            Result dict with trading signals and performance metrics
        """
        # Extract z-scores
        z_scores = np.array(spread_result['value']['z_score'])

        # Generate signals
        signals = np.zeros(len(z_scores))

        position = 0  # 0=flat, 1=long spread, -1=short spread

        for i in range(len(z_scores)):
            z = z_scores[i]

            if position == 0:
                # Entry signals
                if z < -entry_threshold:
                    position = 1  # Long spread
                    signals[i] = 1
                elif z > entry_threshold:
                    position = -1  # Short spread
                    signals[i] = -1
            else:
                # Exit signals
                if abs(z) < exit_threshold:
                    signals[i] = 0
                    position = 0
                else:
                    signals[i] = position

        # Calculate signal statistics
        n_long = int(np.sum(signals == 1))
        n_short = int(np.sum(signals == -1))
        n_flat = int(np.sum(signals == 0))

        return self._create_result_dict(
            value={
                'signals': signals.tolist(),
                'positions': signals.tolist()  # Same as signals in this case
            },
            method='generate_trading_signals',
            parameters={
                'entry_threshold': entry_threshold,
                'exit_threshold': exit_threshold
            },
            metadata={
                'n_long': n_long,
                'n_short': n_short,
                'n_flat': n_flat,
                'pct_in_market': round((n_long + n_short) / len(signals) * 100, 2)
            }
        )

    def _interpret_cointegration(self, is_cointegrated: bool, cointegrating_vector: List[float]) -> str:
        """Generate interpretation of cointegration results."""
        if not is_cointegrated:
            return "Series are not cointegrated. No long-run equilibrium relationship."

        if len(cointegrating_vector) > 1:
            hedge_ratio = cointegrating_vector[1]
            return f"Series are cointegrated. Hedge ratio: {hedge_ratio:.4f}. Suitable for pairs trading."
        else:
            return "Series are cointegrated."

    def _interpret_ecm(self, gamma: float, half_life: float) -> str:
        """Generate interpretation of ECM results."""
        if gamma >= 0:
            return "Warning: Positive adjustment speed indicates divergence, not convergence."

        if np.isinf(half_life):
            return "Adjustment speed is very slow."

        return f"Spread converges to equilibrium with half-life of {half_life:.2f} periods."
