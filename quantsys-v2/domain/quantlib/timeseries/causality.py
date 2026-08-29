"""
Granger Causality Testing Module
=================================

Granger causality tests for identifying predictive relationships
between time series. Migrated from FinceptTerminal.

Features:
    - Granger causality test (univariate and multivariate)
    - Optimal lag selection
    - Bidirectional causality testing
    - Instantaneous causality
    - VAR-based causality analysis

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""
import structlog
logger = structlog.get_logger(__name__)

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


class GrangerCausalityCalculator(BaseCalculator):
    """
    Granger causality testing calculator.

    Granger Causality: X "Granger-causes" Y if past values of X contain
    information that helps predict Y beyond what is contained in past
    values of Y alone.

    Note: Granger causality is a statistical concept, not true causality.
    It tests predictive power, not causal relationships.

    Applications:
        - Lead-lag relationships
        - Market microstructure analysis
        - Economic indicator relationships
        - Trading strategy development

    Example:
        calc = GrangerCausalityCalculator()
        result = calc.test(y, x, maxlag=5)
        if result['value']['x_granger_causes_y']:
            print(f"X predicts Y with optimal lag {result['value']['optimal_lag']}")
    """

    def get_supported_methods(self) -> List[str]:
        return [
            'test',
            'bidirectional_test',
            'select_optimal_lag',
            'instantaneous_causality',
            'multivariate_test'
        ]

    @validate_inputs
    @timing_decorator
    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Main calculation method. Delegates to test() by default.
        """
        return self.test(*args, **kwargs)

    @validate_inputs
    @timing_decorator
    def test(
        self,
        y: Union[List, np.ndarray, pd.Series],
        x: Union[List, np.ndarray, pd.Series],
        maxlag: int = 5,
        test: Literal['ssr_ftest', 'ssr_chi2test', 'lrtest', 'params_ftest'] = 'ssr_ftest',
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Test if X Granger-causes Y.

        Null hypothesis: X does NOT Granger-cause Y
        Alternative: X Granger-causes Y

        Args:
            y: Dependent variable (effect)
            x: Independent variable (potential cause)
            maxlag: Maximum number of lags to test
            test: Test statistic to use
            verbose: Include detailed test results

        Returns:
            Result dict with test statistics, p-values, and causality conclusion
        """
        try:
            from statsmodels.tsa.stattools import grangercausalitytests
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed",
                model_type="GrangerCausality"
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

        # Check lengths match
        if len(y_array) != len(x_array):
            raise DataValidationError(
                f"Series lengths must match: y={len(y_array)}, x={len(x_array)}",
                field_name="series_length"
            )

        # Check minimum length
        min_length = maxlag * 3 + 10
        if len(y_array) < min_length:
            raise InsufficientDataError(
                required=min_length,
                provided=len(y_array),
                calculation="GrangerCausality"
            )

        # Validate maxlag
        if maxlag < 1:
            raise DataValidationError(
                "maxlag must be at least 1",
                field_name="maxlag"
            )

        if maxlag > len(y_array) // 3:
            warnings.warn(f"maxlag={maxlag} is large relative to data length. Consider reducing.")

        try:
            # Prepare data for grangercausalitytests
            # It expects a 2D array with [y, x] columns
            data = np.column_stack([y_array, x_array])

            # Run Granger causality tests
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                gc_results = grangercausalitytests(data, maxlag=maxlag, verbose=False)

            # Extract results for each lag
            lag_results = []
            min_pvalue = 1.0
            optimal_lag = 1

            for lag in range(1, maxlag + 1):
                lag_result = gc_results[lag][0]

                # Extract test statistic and p-value
                if test in lag_result:
                    stat, pvalue, df = lag_result[test][:3]
                else:
                    # Default to ssr_ftest
                    stat, pvalue, df = lag_result['ssr_ftest'][:3]

                lag_results.append({
                    'lag': lag,
                    'statistic': round(float(stat), 4),
                    'pvalue': round(float(pvalue), 6),
                    'df': int(df) if not isinstance(df, tuple) else df
                })

                # Track minimum p-value
                if pvalue < min_pvalue:
                    min_pvalue = pvalue
                    optimal_lag = lag

            # Determine causality (using 5% significance level)
            x_granger_causes_y = min_pvalue < 0.05

            return self._create_result_dict(
                value={
                    'x_granger_causes_y': x_granger_causes_y,
                    'min_pvalue': round(min_pvalue, 6),
                    'optimal_lag': optimal_lag,
                    'lag_results': lag_results
                },
                method='granger_causality',
                parameters={
                    'data_length': len(y_array),
                    'maxlag': maxlag,
                    'test': test
                },
                metadata={
                    'conclusion': self._interpret_causality(x_granger_causes_y, optimal_lag, min_pvalue),
                    'significance_level': 0.05
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Granger causality test failed: {str(e)}",
                calculation_type="granger_causality"
            )

    @validate_inputs
    @timing_decorator
    def bidirectional_test(
        self,
        series1: Union[List, np.ndarray, pd.Series],
        series2: Union[List, np.ndarray, pd.Series],
        maxlag: int = 5,
        test: str = 'ssr_ftest'
    ) -> Dict[str, Any]:
        """
        Test for bidirectional Granger causality.

        Tests both:
            1. Does series1 Granger-cause series2?
            2. Does series2 Granger-cause series1?

        Args:
            series1: First time series
            series2: Second time series
            maxlag: Maximum lag to test
            test: Test statistic to use

        Returns:
            Result dict with bidirectional causality results
        """
        # Test series1 -> series2
        result_1_to_2 = self.test(
            y=series2,
            x=series1,
            maxlag=maxlag,
            test=test
        )

        # Test series2 -> series1
        result_2_to_1 = self.test(
            y=series1,
            x=series2,
            maxlag=maxlag,
            test=test
        )

        # Determine relationship type
        causes_1_to_2 = result_1_to_2['value']['x_granger_causes_y']
        causes_2_to_1 = result_2_to_1['value']['x_granger_causes_y']

        if causes_1_to_2 and causes_2_to_1:
            relationship = 'bidirectional'
        elif causes_1_to_2:
            relationship = 'series1_causes_series2'
        elif causes_2_to_1:
            relationship = 'series2_causes_series1'
        else:
            relationship = 'no_causality'

        return self._create_result_dict(
            value={
                'series1_causes_series2': causes_1_to_2,
                'series2_causes_series1': causes_2_to_1,
                'relationship': relationship,
                'series1_to_series2_pvalue': result_1_to_2['value']['min_pvalue'],
                'series2_to_series1_pvalue': result_2_to_1['value']['min_pvalue'],
                'optimal_lag_1_to_2': result_1_to_2['value']['optimal_lag'],
                'optimal_lag_2_to_1': result_2_to_1['value']['optimal_lag']
            },
            method='bidirectional_granger',
            parameters={
                'maxlag': maxlag,
                'test': test
            },
            metadata={
                'interpretation': self._interpret_bidirectional(relationship),
                'result_1_to_2': result_1_to_2,
                'result_2_to_1': result_2_to_1
            }
        )

    @validate_inputs
    @timing_decorator
    def select_optimal_lag(
        self,
        y: Union[List, np.ndarray, pd.Series],
        x: Union[List, np.ndarray, pd.Series],
        maxlag: int = 10,
        ic: Literal['aic', 'bic', 'hqic'] = 'aic'
    ) -> Dict[str, Any]:
        """
        Select optimal lag for Granger causality test using information criteria.

        Args:
            y: Dependent variable
            x: Independent variable
            maxlag: Maximum lag to consider
            ic: Information criterion ('aic', 'bic', 'hqic')

        Returns:
            Result dict with optimal lag and IC values
        """
        try:
            from statsmodels.tsa.api import VAR
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed",
                model_type="VAR"
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
                "Series lengths must match",
                field_name="series_length"
            )

        try:
            # Prepare data for VAR
            data = pd.DataFrame({'y': y_array, 'x': x_array})

            # Fit VAR model
            model = VAR(data)

            # Select order using information criterion
            lag_order_results = model.select_order(maxlags=maxlag)

            # Get optimal lag for specified IC
            if ic == 'aic':
                optimal_lag = lag_order_results.aic
            elif ic == 'bic':
                optimal_lag = lag_order_results.bic
            else:  # hqic
                optimal_lag = lag_order_results.hqic

            # Get IC values for all lags
            ic_values = {}
            for lag in range(1, maxlag + 1):
                try:
                    fitted = model.fit(lag)
                    ic_values[lag] = {
                        'aic': round(fitted.aic, 4),
                        'bic': round(fitted.bic, 4),
                        'hqic': round(fitted.hqic, 4)
                    }
                except Exception:
                    logger.debug("unexpected exception in module", exc_info=True)
                    continue

            return self._create_result_dict(
                value={
                    'optimal_lag': optimal_lag,
                    'ic_values': ic_values
                },
                method='select_optimal_lag',
                parameters={
                    'data_length': len(y_array),
                    'maxlag': maxlag,
                    'ic': ic
                },
                metadata={
                    'recommendation': f"Use lag={optimal_lag} for Granger causality test"
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Lag selection failed: {str(e)}",
                calculation_type="select_optimal_lag"
            )

    @validate_inputs
    @timing_decorator
    def instantaneous_causality(
        self,
        series1: Union[List, np.ndarray, pd.Series],
        series2: Union[List, np.ndarray, pd.Series],
        maxlag: int = 5
    ) -> Dict[str, Any]:
        """
        Test for instantaneous causality (contemporaneous correlation).

        Tests if series1 and series2 are contemporaneously correlated
        after accounting for their own lags.

        Args:
            series1: First time series
            series2: Second time series
            maxlag: Number of lags to include in VAR model

        Returns:
            Result dict with instantaneous causality test
        """
        try:
            from statsmodels.tsa.api import VAR
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed",
                model_type="VAR"
            )

        # Validate inputs
        series1 = self._validate_numeric_input(series1, 'series1')
        series2 = self._validate_numeric_input(series2, 'series2')

        if isinstance(series1, pd.Series):
            s1_array = series1.values
        else:
            s1_array = np.array(series1)

        if isinstance(series2, pd.Series):
            s2_array = series2.values
        else:
            s2_array = np.array(series2)

        if len(s1_array) != len(s2_array):
            raise DataValidationError(
                "Series lengths must match",
                field_name="series_length"
            )

        try:
            # Prepare data
            data = pd.DataFrame({'series1': s1_array, 'series2': s2_array})

            # Fit VAR model
            model = VAR(data)
            fitted = model.fit(maxlag)

            # Test instantaneous causality
            # This tests if the residuals are correlated
            resid = fitted.resid

            # Calculate correlation of residuals
            corr = np.corrcoef(resid['series1'], resid['series2'])[0, 1]

            # Test significance using t-test
            n = len(resid)
            t_stat = corr * np.sqrt(n - 2) / np.sqrt(1 - corr**2)

            from scipy import stats
            p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))

            has_instantaneous = p_value < 0.05

            return self._create_result_dict(
                value={
                    'residual_correlation': round(float(corr), 4),
                    't_statistic': round(float(t_stat), 4),
                    'p_value': round(float(p_value), 6),
                    'has_instantaneous_causality': has_instantaneous
                },
                method='instantaneous_causality',
                parameters={
                    'data_length': len(s1_array),
                    'maxlag': maxlag
                },
                metadata={
                    'interpretation': 'Series are contemporaneously correlated' if has_instantaneous else 'No instantaneous causality'
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Instantaneous causality test failed: {str(e)}",
                calculation_type="instantaneous_causality"
            )

    @validate_inputs
    @timing_decorator
    def multivariate_test(
        self,
        data: pd.DataFrame,
        caused_variable: str,
        causing_variables: List[str],
        maxlag: int = 5
    ) -> Dict[str, Any]:
        """
        Test if multiple variables jointly Granger-cause a target variable.

        Args:
            data: DataFrame with all time series
            caused_variable: Name of dependent variable
            causing_variables: List of potential causing variable names
            maxlag: Maximum lag to test

        Returns:
            Result dict with multivariate causality test
        """
        try:
            from statsmodels.tsa.api import VAR
        except ImportError:
            raise ModelFitError(
                "statsmodels not installed",
                model_type="VAR"
            )

        # Validate inputs
        if not isinstance(data, pd.DataFrame):
            raise DataValidationError(
                "multivariate_test requires DataFrame",
                field_name="data"
            )

        if caused_variable not in data.columns:
            raise DataValidationError(
                f"caused_variable '{caused_variable}' not in DataFrame",
                field_name="caused_variable"
            )

        for var in causing_variables:
            if var not in data.columns:
                raise DataValidationError(
                    f"causing_variable '{var}' not in DataFrame",
                    field_name="causing_variables"
                )

        try:
            # Fit VAR model with all variables
            model = VAR(data)
            fitted = model.fit(maxlag)

            # Test causality from causing_variables to caused_variable
            test_result = fitted.test_causality(
                caused=caused_variable,
                causing=causing_variables,
                kind='f'
            )

            # Extract results
            statistic = float(test_result.test_statistic)
            p_value = float(test_result.pvalue)
            df = test_result.df
            causes = p_value < 0.05

            return self._create_result_dict(
                value={
                    'joint_granger_causality': causes,
                    'f_statistic': round(statistic, 4),
                    'p_value': round(p_value, 6),
                    'degrees_of_freedom': df
                },
                method='multivariate_granger',
                parameters={
                    'data_shape': data.shape,
                    'caused_variable': caused_variable,
                    'causing_variables': causing_variables,
                    'maxlag': maxlag
                },
                metadata={
                    'interpretation': f"{', '.join(causing_variables)} jointly Granger-cause {caused_variable}" if causes else "No joint causality found"
                }
            )

        except Exception as e:
            raise CalculationError(
                message=f"Multivariate causality test failed: {str(e)}",
                calculation_type="multivariate_granger"
            )

    def _interpret_causality(self, causes: bool, lag: int, pvalue: float) -> str:
        """Generate interpretation of causality test."""
        if causes:
            return f"X Granger-causes Y at lag {lag} (p={pvalue:.4f}). X has predictive power for Y."
        else:
            return f"X does NOT Granger-cause Y (min p={pvalue:.4f}). X has no predictive power for Y."

    def _interpret_bidirectional(self, relationship: str) -> str:
        """Generate interpretation of bidirectional test."""
        interpretations = {
            'bidirectional': 'Bidirectional causality: both series predict each other',
            'series1_causes_series2': 'Unidirectional: series1 predicts series2',
            'series2_causes_series1': 'Unidirectional: series2 predicts series1',
            'no_causality': 'No Granger causality in either direction'
        }
        return interpretations.get(relationship, 'Unknown relationship')
