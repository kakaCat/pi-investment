"""
Yield Curve Calculator
======================

Term structure analysis and yield curve construction implementing CFA Institute
standard methodologies for fixed income analysis.

Core algorithms migrated from FinceptTerminal yield_curve.py (834 lines → ~400 lines)

Features:
- Spot rate curve bootstrapping
- Forward rate calculation
- Yield curve interpolation (linear, cubic spline)
- Nelson-Siegel model fitting
- Svensson model fitting
- Par curve construction
- Spread analysis (Z-spread, G-spread)

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
from scipy import interpolate, optimize
from typing import Dict, Any, List, Optional, Tuple, Callable
from domain.quantlib.base_calculator import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError, ConvergenceError


class YieldCurveCalculator(BaseCalculator):
    """
    Yield curve construction and analysis engine.

    Provides comprehensive yield curve analytics including:
    - Bootstrapping spot curves from bond prices
    - Forward rate derivation
    - Curve interpolation and fitting
    - Nelson-Siegel and Svensson models
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        super().__init__(precision, risk_free_rate)
        self._spot_curve: Optional[Callable] = None
        self._forward_curve: Optional[Callable] = None

    def calculate(self, **kwargs) -> Dict[str, Any]:
        """
        Main calculation dispatcher.

        Args:
            method: Calculation method ('bootstrap', 'forward', 'nelson_siegel', 'svensson', 'interpolate')
            **kwargs: Method-specific parameters

        Returns:
            Calculation results dictionary
        """
        method = kwargs.get('method', 'bootstrap')

        if method == 'bootstrap':
            return self.bootstrap_spot_curve(**kwargs)
        elif method == 'forward':
            return self.calculate_forward_curve(**kwargs)
        elif method == 'nelson_siegel':
            return self.fit_nelson_siegel(**kwargs)
        elif method == 'svensson':
            return self.fit_svensson(**kwargs)
        elif method == 'interpolate':
            return self.interpolate_curve(**kwargs)
        else:
            raise DataValidationError(f"Unknown method: {method}", field_name='method')

    def bootstrap_spot_curve(
        self,
        bonds: List[Dict[str, float]],
        frequency: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Bootstrap spot rate curve from coupon bond prices.

        Args:
            bonds: List of bonds with keys: price, coupon_rate, maturity, face_value
                   Must be sorted by maturity
            frequency: Coupon frequency

        Returns:
            Dictionary with bootstrapped spot curve
        """
        if not bonds:
            raise DataValidationError("Bonds list cannot be empty", field_name='bonds')

        # Sort bonds by maturity
        sorted_bonds = sorted(bonds, key=lambda x: x.get('maturity', 0))

        spot_rates = []
        discount_factors = []
        maturities = []

        for bond in sorted_bonds:
            price = bond.get('price', 1000)
            coupon_rate = bond.get('coupon_rate', 0)
            maturity = bond.get('maturity', 1)
            face_value = bond.get('face_value', 1000)

            # Validate
            if price <= 0 or maturity <= 0 or face_value <= 0:
                continue

            coupon = (coupon_rate * face_value) / frequency
            periods = int(maturity * frequency)

            if coupon_rate == 0 or len(spot_rates) == 0:
                # Zero coupon or first bond - direct calculation
                spot = (face_value / price) ** (1 / maturity) - 1
            else:
                # Bootstrap using known spot rates
                pv_coupons = 0
                for i in range(len(spot_rates)):
                    t = maturities[i]
                    if t < maturity:
                        # Discount coupon at this maturity
                        num_coupons = int(t * frequency)
                        if num_coupons <= periods:
                            pv_coupons += coupon / ((1 + spot_rates[i]) ** t)

                # Solve for current spot rate
                remaining = price - pv_coupons
                final_cf = coupon + face_value

                if remaining <= 0:
                    continue

                spot = (final_cf / remaining) ** (1 / maturity) - 1

            spot_rates.append(spot)
            discount_factors.append(1 / ((1 + spot) ** maturity))
            maturities.append(maturity)

        if not spot_rates:
            raise CalculationError("Could not bootstrap any spot rates", calculation_type='bootstrap')

        curve_points = [
            {
                'maturity': maturities[i],
                'spot_rate': spot_rates[i],
                'spot_rate_pct': spot_rates[i] * 100,
                'discount_factor': discount_factors[i]
            }
            for i in range(len(spot_rates))
        ]

        # Store interpolator
        self._spot_curve = interpolate.interp1d(
            maturities, spot_rates, kind='linear', fill_value='extrapolate'
        )

        return self._create_result_dict(
            value=spot_rates,
            method='bootstrap_spot_curve',
            parameters={
                'num_bonds': len(sorted_bonds),
                'frequency': frequency
            },
            metadata={
                'spot_curve': curve_points,
                'num_points': len(curve_points),
                'min_maturity': min(maturities),
                'max_maturity': max(maturities)
            }
        )

    def calculate_forward_curve(
        self,
        spot_rates: List[Tuple[float, float]],
        forward_periods: List[Tuple[float, float]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate forward rates from spot rate curve.

        f(t1,t2) = [(1+s2)^t2 / (1+s1)^t1]^(1/(t2-t1)) - 1

        Args:
            spot_rates: List of (maturity, rate) tuples
            forward_periods: List of (start, end) periods for forward rates

        Returns:
            Dictionary with forward curve
        """
        if not spot_rates:
            raise DataValidationError("Spot rates list cannot be empty", field_name='spot_rates')

        # Validate spot rates
        for maturity, rate in spot_rates:
            if maturity <= 0:
                raise DataValidationError("Maturity must be positive", field_name='spot_rates')

        # Default forward periods if not specified
        if forward_periods is None:
            maturities = [sr[0] for sr in spot_rates]
            forward_periods = [(maturities[i], maturities[i + 1])
                               for i in range(len(maturities) - 1)]

        # Create interpolator for spot rates
        mat_array = np.array([sr[0] for sr in spot_rates])
        rate_array = np.array([sr[1] for sr in spot_rates])
        spot_interp = interpolate.interp1d(mat_array, rate_array, kind='linear', fill_value='extrapolate')

        forward_rates = []

        for t1, t2 in forward_periods:
            if t2 <= t1:
                continue

            s1 = float(spot_interp(t1))
            s2 = float(spot_interp(t2))

            # Forward rate formula
            forward = ((1 + s2) ** t2 / (1 + s1) ** t1) ** (1 / (t2 - t1)) - 1

            forward_rates.append({
                'start': t1,
                'end': t2,
                'period': f'{t1}y x {t2}y',
                'forward_rate': forward,
                'forward_rate_pct': forward * 100,
                'spot_t1': s1,
                'spot_t2': s2
            })

        # Store interpolator
        if forward_rates:
            fwd_maturities = [(fr['start'] + fr['end']) / 2 for fr in forward_rates]
            fwd_rates = [fr['forward_rate'] for fr in forward_rates]
            self._forward_curve = interpolate.interp1d(
                fwd_maturities, fwd_rates, kind='linear', fill_value='extrapolate'
            )

        return self._create_result_dict(
            value=[fr['forward_rate'] for fr in forward_rates],
            method='forward_curve',
            parameters={
                'num_spot_rates': len(spot_rates),
                'num_forward_periods': len(forward_periods)
            },
            metadata={
                'forward_curve': forward_rates,
                'num_points': len(forward_rates)
            }
        )

    def fit_nelson_siegel(
        self,
        maturities: List[float],
        yields: List[float],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fit Nelson-Siegel model to yield curve.

        y(t) = b0 + b1*[(1-exp(-t/tau))/(t/tau)] + b2*[(1-exp(-t/tau))/(t/tau) - exp(-t/tau)]

        Args:
            maturities: List of maturities
            yields: List of yields

        Returns:
            Dictionary with fitted parameters and curve
        """
        # Validate inputs
        maturities = self._validate_numeric_input(maturities, 'maturities')
        yields = self._validate_numeric_input(yields, 'yields')

        if len(maturities) != len(yields):
            raise DataValidationError("Maturities and yields must have same length")

        maturities = np.array(maturities)
        yields = np.array(yields)

        def nelson_siegel(t, b0, b1, b2, tau):
            """Nelson-Siegel functional form."""
            if tau <= 0:
                return np.full_like(t, np.inf)
            x = t / tau
            with np.errstate(divide='ignore', invalid='ignore'):
                factor1 = np.where(x > 0, (1 - np.exp(-x)) / x, 1)
                factor2 = factor1 - np.exp(-x)
            return b0 + b1 * factor1 + b2 * factor2

        def objective(params):
            """Objective function to minimize."""
            return np.sum((nelson_siegel(maturities, *params) - yields) ** 2)

        # Initial guess
        b0_init = yields[-1] if len(yields) > 0 else 0.05  # Long-term level
        b1_init = yields[0] - yields[-1] if len(yields) > 1 else 0  # Slope
        b2_init = 0  # Curvature
        tau_init = 2  # Time constant

        try:
            result = optimize.minimize(
                objective,
                [b0_init, b1_init, b2_init, tau_init],
                method='Nelder-Mead',
                options={'maxiter': 1000}
            )
            b0, b1, b2, tau = result.x

            if not result.success:
                raise ConvergenceError("Nelson-Siegel optimization did not converge", iterations=result.nit)

        except Exception as e:
            raise ConvergenceError(f"Failed to fit Nelson-Siegel model: {str(e)}")

        # Generate fitted curve
        fitted_maturities = np.linspace(0.25, max(maturities), 50)
        fitted_yields = nelson_siegel(fitted_maturities, b0, b1, b2, tau)

        # Calculate fit statistics
        fitted_at_data = nelson_siegel(maturities, b0, b1, b2, tau)
        rmse = np.sqrt(np.mean((yields - fitted_at_data) ** 2))
        r_squared = 1 - np.sum((yields - fitted_at_data) ** 2) / np.sum((yields - np.mean(yields)) ** 2)

        return self._create_result_dict(
            value={'beta0': b0, 'beta1': b1, 'beta2': b2, 'tau': tau},
            method='nelson_siegel',
            parameters={
                'num_points': len(maturities)
            },
            metadata={
                'parameters': {
                    'beta0': b0,  # Long-term level
                    'beta1': b1,  # Short-term component
                    'beta2': b2,  # Medium-term component
                    'tau': tau    # Time decay
                },
                'interpretation': {
                    'long_term_rate': b0,
                    'slope': b1,
                    'curvature': b2
                },
                'fitted_curve': [
                    {'maturity': float(m), 'yield': float(y)}
                    for m, y in zip(fitted_maturities, fitted_yields)
                ],
                'fit_statistics': {
                    'rmse': rmse,
                    'r_squared': r_squared
                }
            }
        )

    def fit_svensson(
        self,
        maturities: List[float],
        yields: List[float],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fit Svensson model (extended Nelson-Siegel) to yield curve.

        y(t) = b0 + b1*f1(t,tau1) + b2*f2(t,tau1) + b3*f2(t,tau2)

        Args:
            maturities: List of maturities
            yields: List of yields

        Returns:
            Dictionary with fitted parameters and curve
        """
        # Validate inputs
        maturities = self._validate_numeric_input(maturities, 'maturities')
        yields = self._validate_numeric_input(yields, 'yields')

        if len(maturities) != len(yields):
            raise DataValidationError("Maturities and yields must have same length")

        maturities = np.array(maturities)
        yields = np.array(yields)

        def svensson(t, b0, b1, b2, b3, tau1, tau2):
            """Svensson functional form."""
            if tau1 <= 0 or tau2 <= 0:
                return np.full_like(t, np.inf)
            x1 = t / tau1
            x2 = t / tau2
            with np.errstate(divide='ignore', invalid='ignore'):
                f1 = np.where(x1 > 0, (1 - np.exp(-x1)) / x1, 1)
                f2_1 = f1 - np.exp(-x1)
                f2_2 = np.where(x2 > 0, (1 - np.exp(-x2)) / x2, 1) - np.exp(-x2)
            return b0 + b1 * f1 + b2 * f2_1 + b3 * f2_2

        def objective(params):
            """Objective function to minimize."""
            return np.sum((svensson(maturities, *params) - yields) ** 2)

        # Initial guess
        b0_init = yields[-1] if len(yields) > 0 else 0.05
        b1_init = yields[0] - yields[-1] if len(yields) > 1 else 0
        b2_init = 0
        b3_init = 0
        tau1_init = 2
        tau2_init = 5

        try:
            result = optimize.minimize(
                objective,
                [b0_init, b1_init, b2_init, b3_init, tau1_init, tau2_init],
                method='Nelder-Mead',
                options={'maxiter': 2000}
            )
            b0, b1, b2, b3, tau1, tau2 = result.x

            if not result.success:
                raise ConvergenceError("Svensson optimization did not converge", iterations=result.nit)

        except Exception as e:
            raise ConvergenceError(f"Failed to fit Svensson model: {str(e)}")

        # Generate fitted curve
        fitted_maturities = np.linspace(0.25, max(maturities), 50)
        fitted_yields = svensson(fitted_maturities, b0, b1, b2, b3, tau1, tau2)

        # Calculate fit statistics
        fitted_at_data = svensson(maturities, b0, b1, b2, b3, tau1, tau2)
        rmse = np.sqrt(np.mean((yields - fitted_at_data) ** 2))
        r_squared = 1 - np.sum((yields - fitted_at_data) ** 2) / np.sum((yields - np.mean(yields)) ** 2)

        return self._create_result_dict(
            value={'beta0': b0, 'beta1': b1, 'beta2': b2, 'beta3': b3, 'tau1': tau1, 'tau2': tau2},
            method='svensson',
            parameters={
                'num_points': len(maturities)
            },
            metadata={
                'parameters': {
                    'beta0': b0,
                    'beta1': b1,
                    'beta2': b2,
                    'beta3': b3,
                    'tau1': tau1,
                    'tau2': tau2
                },
                'fitted_curve': [
                    {'maturity': float(m), 'yield': float(y)}
                    for m, y in zip(fitted_maturities, fitted_yields)
                ],
                'fit_statistics': {
                    'rmse': rmse,
                    'r_squared': r_squared
                }
            }
        )

    def interpolate_curve(
        self,
        maturities: List[float],
        yields: List[float],
        target_maturities: List[float],
        method: str = 'cubic',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Interpolate yield curve at target maturities.

        Args:
            maturities: Known maturities
            yields: Known yields
            target_maturities: Maturities to interpolate
            method: Interpolation method ('linear', 'cubic')

        Returns:
            Dictionary with interpolated yields
        """
        # Validate inputs
        maturities = self._validate_numeric_input(maturities, 'maturities')
        yields = self._validate_numeric_input(yields, 'yields')
        target_maturities = self._validate_numeric_input(target_maturities, 'target_maturities')

        if len(maturities) != len(yields):
            raise DataValidationError("Maturities and yields must have same length")

        maturities = np.array(maturities)
        yields = np.array(yields)
        target_maturities = np.array(target_maturities)

        # Create interpolator
        if method == 'linear':
            interp_func = interpolate.interp1d(maturities, yields, kind='linear', fill_value='extrapolate')
        elif method == 'cubic':
            if len(maturities) < 4:
                # Fall back to linear for insufficient points
                interp_func = interpolate.interp1d(maturities, yields, kind='linear', fill_value='extrapolate')
            else:
                interp_func = interpolate.interp1d(maturities, yields, kind='cubic', fill_value='extrapolate')
        else:
            raise DataValidationError(f"Unknown interpolation method: {method}", field_name='method')

        # Interpolate
        interpolated_yields = interp_func(target_maturities)

        interpolated_points = [
            {'maturity': float(m), 'yield': float(y)}
            for m, y in zip(target_maturities, interpolated_yields)
        ]

        return self._create_result_dict(
            value=interpolated_yields,
            method=f'interpolate_{method}',
            parameters={
                'num_input_points': len(maturities),
                'num_output_points': len(target_maturities),
                'interpolation_method': method
            },
            metadata={
                'interpolated_curve': interpolated_points
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Get list of supported calculation methods."""
        return ['bootstrap', 'forward', 'nelson_siegel', 'svensson', 'interpolate']
