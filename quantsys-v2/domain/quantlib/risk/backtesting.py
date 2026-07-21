"""
VaR Backtesting Calculator
===========================

Statistical tests for validating Value at Risk models including:
- Kupiec Proportion of Failures (POF) test
- Christoffersen conditional coverage test
- Basel traffic light test
- Exception counting and analysis

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional
from scipy import stats

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    DataValidationError,
    InsufficientDataError,
    ConfigurationError,
)


class BacktestingCalculator(BaseCalculator):
    """
    VaR backtesting calculator with statistical validation.

    Implements standard VaR backtesting tests to validate risk model
    accuracy including unconditional coverage (Kupiec), conditional
    coverage (Christoffersen), and Basel regulatory traffic light tests.

    Methods:
        - kupiec: Kupiec POF test (unconditional coverage)
        - christoffersen: Christoffersen test (conditional coverage + independence)
        - traffic_light: Basel traffic light zones
        - exceptions: Simple exception analysis

    Example:
        calculator = BacktestingCalculator(precision=4)
        pnl = np.random.normal(-0.001, 0.02, 500)
        var_series = np.full(500, 0.03)  # Daily VaR at 99%
        result = calculator.calculate(pnl, var_series, confidence_level=0.99)
    """

    # Basel traffic light thresholds (for 250-day window at 99% VaR)
    GREEN_ZONE_MAX = 4      # 0-4 exceptions: green
    YELLOW_ZONE_MAX = 9     # 5-9 exceptions: yellow
    # >= 10 exceptions: red

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize backtesting calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate (not used in backtesting but kept for consistency)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  pnl_or_returns: Union[List, np.ndarray, pd.Series],
                  var_series: Union[List, np.ndarray, pd.Series],
                  confidence_level: float = 0.99,
                  method: str = 'kupiec') -> Dict[str, Any]:
        """
        Calculate VaR backtesting statistics.

        Args:
            pnl_or_returns: Realized P&L or return series
            var_series: VaR estimates for each period (should be positive values
                       representing loss magnitude)
            confidence_level: VaR confidence level (default: 0.99)
            method: 'kupiec', 'christoffersen', 'traffic_light', or 'exceptions'

        Returns:
            Dictionary with backtesting results

        Raises:
            DataValidationError: If series lengths don't match or data is invalid
            InsufficientDataError: If not enough observations
            ConfigurationError: If method is unsupported
            CalculationError: If computation fails
        """
        # Validate and convert inputs
        pnl = self._validate_returns(pnl_or_returns, 'pnl_or_returns')
        var = self._validate_returns(var_series, 'var_series')
        confidence_level = self._validate_probability(confidence_level, 'confidence_level')

        # Check lengths match
        if len(pnl) != len(var):
            raise DataValidationError(
                f"P&L series length ({len(pnl)}) must match VaR series length ({len(var)})",
                field_name='pnl_or_returns/var_series'
            )

        # Check minimum observations
        min_obs = 100
        if len(pnl) < min_obs:
            raise InsufficientDataError(
                required=min_obs,
                provided=len(pnl),
                calculation=f'VaR backtesting ({method})'
            )

        # Validate method
        method = self.validate_method(method)

        try:
            # VaR violations: PnL < -VaR (i.e., loss exceeds VaR estimate)
            # Since VaR is typically stored as positive magnitude, check if PnL < -VaR
            # But if all VaR values are negative, compare directly
            if np.all(var >= 0):
                # VaR is positive magnitude, loss is negative PnL
                hit_series = (pnl < -var).astype(int)
            else:
                # VaR is negative, compare directly
                hit_series = (pnl < var).astype(int)

            n_obs = len(pnl)
            exceptions = int(np.sum(hit_series))
            exception_rate = exceptions / n_obs
            expected_rate = 1 - confidence_level
            expected_exceptions = expected_rate * n_obs

            if method == 'kupiec':
                result = self._kupiec_pof_test(exceptions, n_obs, confidence_level)
            elif method == 'christoffersen':
                result = self._christoffersen_test(hit_series, confidence_level)
            elif method == 'traffic_light':
                result = self._traffic_light_test(exceptions, n_obs, confidence_level)
            elif method == 'exceptions':
                result = self.calculate_exceptions(pnl, var_series)
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            # Add common metadata
            result.update({
                'n_observations': n_obs,
                'n_exceptions': exceptions,
                'exception_rate': float(self._round_result(exception_rate)),
                'expected_rate': float(self._round_result(expected_rate)),
                'expected_exceptions': float(self._round_result(expected_exceptions)),
            })

            return self._create_result_dict(
                value=result,
                method=f'backtesting_{method}',
                parameters={
                    'confidence_level': confidence_level,
                    'method': method,
                    'n_observations': n_obs
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, InsufficientDataError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='VaRBacktesting')

    def _kupiec_pof_test(self,
                          exceptions: int,
                          n_obs: int,
                          cl: float) -> Dict[str, Any]:
        """
        Kupiec Proportion of Failures (POF) test.

        Tests whether the observed exception rate is statistically consistent
        with the expected exception rate (1 - confidence_level).

        Null hypothesis: The exception rate equals the expected rate.

        LR_POF = -2 * ln( ((1-cl)^(n-x) * cl^x) / ((1-x/n)^(n-x) * (x/n)^x) )

        The test statistic follows a chi-squared distribution with 1 degree
        of freedom under the null hypothesis.

        Args:
            exceptions: Number of VaR violations
            n_obs: Total number of observations
            cl: VaR confidence level

        Returns:
            Dictionary with test results
        """
        x = exceptions
        n = n_obs
        p_expected = 1 - cl  # Expected exception rate
        p_observed = x / n if n > 0 else 0.0

        # Avoid log(0) issues
        if x == 0:
            # All terms with x become 0: p_observed = 0
            # LR = -2 * ln( (1-p)^n / 1^n ) = -2 * n * ln(1-p)
            if p_expected > 0:
                lr_stat = -2 * n * np.log(1 - p_expected)
            else:
                lr_stat = 0.0
        elif x == n:
            # LR = -2 * ln( p^n / 1^n ) = -2 * n * ln(p)
            if cl > 0:
                lr_stat = -2 * n * np.log(cl)
            else:
                lr_stat = float('inf')
        else:
            # Restricted likelihood (under null): (1-p)^(n-x) * p^x
            ll_restricted = (n - x) * np.log(1 - p_expected) + x * np.log(p_expected)
            # Unrestricted likelihood (MLE): (1-x/n)^(n-x) * (x/n)^x
            if p_observed > 0 and p_observed < 1:
                ll_unrestricted = (n - x) * np.log(1 - p_observed) + x * np.log(p_observed)
            elif p_observed == 0:
                ll_unrestricted = (n - x) * np.log(1 - 0) + x * np.log(1e-10)
            else:
                ll_unrestricted = (n - x) * np.log(1e-10) + x * np.log(1)

            lr_stat = -2 * (ll_restricted - ll_unrestricted)

        # Ensure non-negative LR statistic
        lr_stat = max(0.0, lr_stat)

        # Critical value at 5% significance level (chi2 with 1 df)
        critical_value_95 = stats.chi2.ppf(0.95, 1)
        critical_value_99 = stats.chi2.ppf(0.99, 1)

        # p-value
        p_value = 1 - stats.chi2.cdf(lr_stat, 1)

        # Decision: reject null if LR > critical value at chosen significance
        reject_95 = lr_stat > critical_value_95
        reject_99 = lr_stat > critical_value_99

        return {
            'test': 'Kupiec POF',
            'lr_statistic': float(self._round_result(lr_stat)),
            'p_value': float(self._round_result(p_value)),
            'critical_value_95': float(self._round_result(critical_value_95)),
            'critical_value_99': float(self._round_result(critical_value_99)),
            'reject_at_5pct': reject_95,
            'reject_at_1pct': reject_99,
            'interpretation': (
                'Model is accurate (fail to reject)' if not reject_95
                else 'Model may be inaccurate (reject at 5%)'
            )
        }

    def _christoffersen_test(self,
                              hit_series: np.ndarray,
                              cl: float) -> Dict[str, Any]:
        """
        Christoffersen conditional coverage test.

        Tests both unconditional coverage (like Kupiec) AND independence
        of exceptions (i.e., whether exceptions cluster in time).

        The test decomposes into:
        - LR_ind: Tests independence of hits
        - LR_cc = LR_ind + LR_POF: Tests conditional coverage

        Args:
            hit_series: Binary series (1=exception, 0=no exception)
            cl: VaR confidence level

        Returns:
            Dictionary with test results
        """
        n = len(hit_series)
        hits = hit_series.astype(int)

        # Build transition counts
        # n_ij = number of times state i is followed by state j
        # 0 = no exception, 1 = exception
        n_00 = np.sum((hits[:-1] == 0) & (hits[1:] == 0))
        n_01 = np.sum((hits[:-1] == 0) & (hits[1:] == 1))
        n_10 = np.sum((hits[:-1] == 1) & (hits[1:] == 0))
        n_11 = np.sum((hits[:-1] == 1) & (hits[1:] == 1))

        # Transition probabilities
        # pi_01 = P(exception_t | no_exception_t-1)
        # pi_11 = P(exception_t | exception_t-1)
        # pi = unconditional exception probability

        n_0 = n_00 + n_01  # Total times in state 0
        n_1 = n_10 + n_11  # Total times in state 1

        pi_01 = n_01 / n_0 if n_0 > 0 else 0.0
        pi_11 = n_11 / n_1 if n_1 > 0 else 0.0
        pi = (n_01 + n_11) / (n_0 + n_1) if (n_0 + n_1) > 0 else 0.0

        # LR independence test
        # Under independence: pi_01 = pi_11 = pi
        def safe_log(x):
            return np.log(x) if x > 0 else 0.0

        if pi > 0 and (1 - pi) > 0 and pi_01 > 0 and pi_11 > 0:
            ll_independent = (
                n_00 * safe_log(1 - pi) + n_01 * safe_log(pi) +
                n_10 * safe_log(1 - pi) + n_11 * safe_log(pi)
            )
            ll_dependent = (
                n_00 * safe_log(1 - pi_01) + n_01 * safe_log(pi_01) +
                n_10 * safe_log(1 - pi_11) + n_11 * safe_log(pi_11)
            )
            lr_ind = -2 * (ll_independent - ll_dependent)
        else:
            lr_ind = 0.0

        lr_ind = max(0.0, lr_ind)

        # Kupiec POF (unconditional coverage)
        exceptions = int(np.sum(hits))
        pof_result = self._kupiec_pof_test(exceptions, n, cl)
        lr_pof = pof_result['lr_statistic']

        # Conditional coverage: LR_cc = LR_ind + LR_POF
        lr_cc = lr_ind + lr_pof

        # Critical values (chi2 with 2 df for CC, 1 df for independence)
        cv_ind_95 = stats.chi2.ppf(0.95, 1)
        cv_cc_95 = stats.chi2.ppf(0.95, 2)

        # p-values
        p_ind = 1 - stats.chi2.cdf(lr_ind, 1)
        p_cc = 1 - stats.chi2.cdf(lr_cc, 2)

        reject_ind_95 = lr_ind > cv_ind_95
        reject_cc_95 = lr_cc > cv_cc_95

        return {
            'test': 'Christoffersen',
            'lr_pof': float(self._round_result(lr_pof)),
            'lr_ind': float(self._round_result(lr_ind)),
            'lr_cc': float(self._round_result(lr_cc)),
            'p_value_ind': float(self._round_result(p_ind)),
            'p_value_cc': float(self._round_result(p_cc)),
            'critical_value_ind_95': float(self._round_result(cv_ind_95)),
            'critical_value_cc_95': float(self._round_result(cv_cc_95)),
            'reject_ind_at_5pct': reject_ind_95,
            'reject_cc_at_5pct': reject_cc_95,
            'pi_01': float(self._round_result(pi_01)),
            'pi_11': float(self._round_result(pi_11)),
            'pi': float(self._round_result(pi)),
            'interpretation': (
                'Model passes all tests'
                if not reject_cc_95
                else 'Clustering detected' if reject_ind_95
                else 'Coverage issue detected'
            )
        }

    def _traffic_light_test(self,
                             exceptions: int,
                             n_obs: int,
                             cl: float) -> Dict[str, Any]:
        """
        Basel traffic light test for VaR backtesting.

        Based on the number of exceptions in a 250-day window at 99% VaR:
        - Green zone: 0-4 exceptions (model is adequate)
        - Yellow zone: 5-9 exceptions (model may be inaccurate)
        - Red zone: 10+ exceptions (model is problematic)

        The test includes a multiplier scaling factor for the VaR multiplier
        in regulatory capital calculations (the "plus factor" k):
        - Green: k = 0
        - Yellow: k = 0.4 to 0.85 (linear interpolation)
        - Red: k = 1

        Args:
            exceptions: Number of VaR exceptions
            n_obs: Number of observations
            cl: VaR confidence level

        Returns:
            Dictionary with traffic light results
        """
        # Scale exceptions to 250-day equivalent for 99% VaR
        if cl == 0.99:
            # Apply directly
            scaled_exceptions = exceptions * (250.0 / n_obs)
        else:
            # Approximate scaling for other confidence levels
            scaling_factor = (1 - cl) / 0.01
            scaled_exceptions = exceptions * (250.0 / n_obs) * scaling_factor

        # Determine zone
        if scaled_exceptions <= self.GREEN_ZONE_MAX:
            zone = 'green'
            k_factor = 0.0
            interpretation = 'Model is adequate - green zone'
        elif scaled_exceptions <= self.YELLOW_ZONE_MAX:
            zone = 'yellow'
            # Linear interpolation between 0.4 and 0.85
            range_width = self.YELLOW_ZONE_MAX - self.GREEN_ZONE_MAX
            position = scaled_exceptions - self.GREEN_ZONE_MAX
            k_factor = 0.4 + 0.45 * (position / range_width)
            interpretation = 'Model may be inaccurate - yellow zone'
        else:
            zone = 'red'
            k_factor = 1.0
            interpretation = 'Model is problematic - red zone'

        return {
            'test': 'Basel Traffic Light',
            'exceptions': int(exceptions),
            'scaled_exceptions_250d': float(self._round_result(scaled_exceptions)),
            'zone': zone,
            'k_multiplier': float(self._round_result(k_factor)),
            'n_observations': n_obs,
            'interpretation': interpretation
        }

    def calculate_exceptions(self,
                              pnl: np.ndarray,
                              var_series: np.ndarray) -> Dict[str, Any]:
        """
        Calculate VaR exceptions and related statistics.

        Args:
            pnl: Realized P&L series
            var_series: VaR estimate series

        Returns:
            Dictionary with exception analysis
        """
        # Determine VaR direction
        if np.all(var_series >= 0):
            exceptions = pnl < -var_series
        else:
            exceptions = pnl < var_series

        hit_series = exceptions.astype(int)
        n_obs = len(pnl)
        n_exceptions = int(np.sum(exceptions))

        # Find exception indices and magnitudes
        exception_indices = np.where(exceptions)[0].tolist()
        exception_magnitudes = np.abs(pnl[exceptions] + var_series[exceptions]) if n_exceptions > 0 else np.array([])

        # Serial correlation of hit series
        if n_obs > 1:
            hit_autocorr = np.corrcoef(hit_series[:-1], hit_series[1:])[0, 1]
            if np.isnan(hit_autocorr):
                hit_autocorr = 0.0
        else:
            hit_autocorr = 0.0

        # Exception clustering: average time between exceptions
        if n_exceptions > 1:
            exception_gaps = np.diff(exception_indices)
            avg_exception_gap = float(np.mean(exception_gaps))
            max_exception_gap = int(np.max(exception_gaps))
            min_exception_gap = int(np.min(exception_gaps))
        elif n_exceptions == 1:
            avg_exception_gap = float(n_obs)
            max_exception_gap = n_obs
            min_exception_gap = n_obs
        else:
            avg_exception_gap = float('inf')
            max_exception_gap = None
            min_exception_gap = None

        # Maximum consecutive exceptions
        if n_exceptions > 0:
            max_consecutive = 1
            current_run = 1
            for i in range(1, len(hit_series)):
                if hit_series[i] == 1 and hit_series[i-1] == 1:
                    current_run += 1
                    max_consecutive = max(max_consecutive, current_run)
                else:
                    current_run = 1
        else:
            max_consecutive = 0

        return {
            'n_observations': n_obs,
            'n_exceptions': n_exceptions,
            'exception_rate': float(self._round_result(n_exceptions / n_obs)),
            'exception_indices': exception_indices[:20],  # Limit output size
            'exception_magnitudes': (
                [float(self._round_result(m)) for m in exception_magnitudes[:10]]
                if n_exceptions > 0 else []
            ),
            'avg_exception_gap': (
                float(self._round_result(avg_exception_gap))
                if avg_exception_gap != float('inf') else None
            ),
            'max_consecutive_exceptions': max_consecutive,
            'hit_autocorrelation': float(self._round_result(hit_autocorr)),
        }

    def get_supported_methods(self) -> List[str]:
        """Return list of supported backtesting methods."""
        return ['kupiec', 'christoffersen', 'traffic_light', 'exceptions']
