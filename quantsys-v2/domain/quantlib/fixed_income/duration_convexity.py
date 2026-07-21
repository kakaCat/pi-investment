"""
Duration and Convexity Calculator
==================================

Interest rate risk measurement implementing CFA Institute standard methodologies
for duration and convexity calculations.

Core algorithms migrated from FinceptTerminal duration_convexity.py (621 lines → ~300 lines)

Features:
- Macaulay Duration
- Modified Duration
- Effective Duration (for bonds with embedded options)
- Key Rate Duration
- Convexity (standard and effective)
- Dollar Duration and DV01
- Price sensitivity estimates

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
from typing import Dict, Any, List, Optional
from domain.quantlib.base_calculator import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


class DurationConvexityCalculator(BaseCalculator):
    """
    Duration and convexity calculator implementing CFA-standard methodologies.

    Duration measures the sensitivity of bond price to interest rate changes.
    Convexity captures the curvature in the price-yield relationship.
    """

    def calculate(self, **kwargs) -> Dict[str, Any]:
        """
        Main calculation dispatcher.

        Args:
            method: Calculation method ('macaulay', 'modified', 'effective', 'key_rate', 'convexity', 'effective_convexity')
            **kwargs: Method-specific parameters

        Returns:
            Calculation results dictionary
        """
        method = kwargs.get('method', 'modified')

        if method == 'macaulay':
            return self.calculate_macaulay_duration(**kwargs)
        elif method == 'modified':
            return self.calculate_modified_duration(**kwargs)
        elif method == 'effective':
            return self.calculate_effective_duration(**kwargs)
        elif method == 'key_rate':
            return self.calculate_key_rate_duration(**kwargs)
        elif method == 'convexity':
            return self.calculate_convexity(**kwargs)
        elif method == 'effective_convexity':
            return self.calculate_effective_convexity(**kwargs)
        else:
            raise DataValidationError(f"Unknown method: {method}", field_name='method')

    def calculate_macaulay_duration(
        self,
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        years_to_maturity: float = 10.0,
        ytm: float = 0.05,
        frequency: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate Macaulay Duration - weighted average time to receive cash flows.

        MacDur = sum(t * PV(CF_t)) / Price

        Args:
            face_value: Face/par value
            coupon_rate: Annual coupon rate (decimal)
            years_to_maturity: Years until maturity
            ytm: Yield to maturity (decimal)
            frequency: Coupon payments per year

        Returns:
            Dictionary with Macaulay duration and details
        """
        # Validate inputs
        face_value = self._validate_positive(face_value, 'face_value')
        coupon_rate = self._validate_numeric_input(coupon_rate, 'coupon_rate')
        years_to_maturity = self._validate_positive(years_to_maturity, 'years_to_maturity')
        ytm = self._validate_numeric_input(ytm, 'ytm')

        # Zero coupon bond - duration equals maturity
        if frequency == 0 or coupon_rate == 0:
            price = face_value / ((1 + ytm) ** years_to_maturity)
            return self._create_result_dict(
                value=years_to_maturity,
                method='macaulay_duration_zero',
                parameters={
                    'face_value': face_value,
                    'years_to_maturity': years_to_maturity,
                    'ytm': ytm
                },
                metadata={
                    'price': price,
                    'note': 'Zero coupon bond duration equals maturity'
                }
            )

        periods = int(years_to_maturity * frequency)
        periodic_rate = ytm / frequency
        coupon = (coupon_rate * face_value) / frequency

        weighted_cf_sum = 0
        price = 0

        for t in range(1, periods + 1):
            time_in_years = t / frequency
            cf = coupon if t < periods else coupon + face_value
            discount_factor = 1 / ((1 + periodic_rate) ** t)
            pv_cf = cf * discount_factor
            weighted_cf = time_in_years * pv_cf

            price += pv_cf
            weighted_cf_sum += weighted_cf

        macaulay_duration = weighted_cf_sum / price

        return self._create_result_dict(
            value=macaulay_duration,
            method='macaulay_duration',
            parameters={
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'years_to_maturity': years_to_maturity,
                'ytm': ytm,
                'frequency': frequency
            },
            metadata={
                'macaulay_duration_periods': macaulay_duration * frequency,
                'price': price,
                'weighted_sum': weighted_cf_sum,
                'num_periods': periods
            }
        )

    def calculate_modified_duration(
        self,
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        years_to_maturity: float = 10.0,
        ytm: float = 0.05,
        frequency: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate Modified Duration - price sensitivity measure.

        ModDur = MacDur / (1 + y/n)

        Args:
            face_value: Face/par value
            coupon_rate: Annual coupon rate (decimal)
            years_to_maturity: Years until maturity
            ytm: Yield to maturity (decimal)
            frequency: Coupon payments per year

        Returns:
            Dictionary with modified duration and sensitivity metrics
        """
        # Calculate Macaulay duration first
        mac_result = self.calculate_macaulay_duration(
            face_value, coupon_rate, years_to_maturity, ytm, frequency
        )
        macaulay_duration = mac_result['value']
        price = mac_result['metadata']['price']

        # Modified duration
        if frequency > 0:
            modified_duration = macaulay_duration / (1 + ytm / frequency)
        else:
            modified_duration = macaulay_duration / (1 + ytm)

        # Dollar duration (price change for 1% yield change)
        dollar_duration = modified_duration * price / 100

        # DV01 (dollar value of 1 basis point)
        dv01 = modified_duration * price * 0.0001

        # Price change estimates
        yield_change_1pct = -modified_duration * 0.01 * price
        yield_change_50bp = -modified_duration * 0.005 * price
        yield_change_10bp = -modified_duration * 0.001 * price

        return self._create_result_dict(
            value=modified_duration,
            method='modified_duration',
            parameters={
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'years_to_maturity': years_to_maturity,
                'ytm': ytm,
                'frequency': frequency
            },
            metadata={
                'macaulay_duration': macaulay_duration,
                'dollar_duration': dollar_duration,
                'dv01': dv01,
                'price': price,
                'price_change_1pct_yield': yield_change_1pct,
                'price_change_50bp_yield': yield_change_50bp,
                'price_change_10bp_yield': yield_change_10bp,
                'interpretation': f"A 1% increase in yield decreases price by approximately ${abs(yield_change_1pct):.2f}"
            }
        )

    def calculate_effective_duration(
        self,
        price: float,
        price_up: float,
        price_down: float,
        delta_yield: float = 0.01,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate Effective Duration for bonds with embedded options.

        EffDur = (P_down - P_up) / (2 * P_0 * delta_y)

        Args:
            price: Current bond price
            price_up: Price when yield increases by delta_yield
            price_down: Price when yield decreases by delta_yield
            delta_yield: Yield change magnitude (decimal)

        Returns:
            Dictionary with effective duration
        """
        # Validate inputs
        price = self._validate_positive(price, 'price')
        price_up = self._validate_positive(price_up, 'price_up')
        price_down = self._validate_positive(price_down, 'price_down')
        delta_yield = self._validate_positive(delta_yield, 'delta_yield')

        effective_duration = (price_down - price_up) / (2 * price * delta_yield)

        # Price sensitivity estimate
        pct_change_estimate = -effective_duration * delta_yield * 100

        # Dollar duration
        dollar_duration = effective_duration * price / 100
        dv01 = effective_duration * price * 0.0001

        return self._create_result_dict(
            value=effective_duration,
            method='effective_duration',
            parameters={
                'price': price,
                'price_up': price_up,
                'price_down': price_down,
                'delta_yield': delta_yield
            },
            metadata={
                'delta_yield_bps': delta_yield * 10000,
                'price_change_pct': pct_change_estimate,
                'dollar_duration': dollar_duration,
                'dv01': dv01,
                'note': 'Use for bonds with embedded options (callable, putable, MBS)'
            }
        )

    def calculate_key_rate_duration(
        self,
        spot_rates: List[float],
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        frequency: int = 2,
        delta_rate: float = 0.0001,
        key_rate_maturities: List[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate Key Rate Durations - sensitivity to specific points on yield curve.

        Args:
            spot_rates: Current spot rate curve (one rate per period)
            face_value: Face/par value
            coupon_rate: Annual coupon rate (decimal)
            frequency: Coupon payments per year
            delta_rate: Rate change for sensitivity (decimal)
            key_rate_maturities: Specific maturities to calculate KRD (in years)

        Returns:
            Dictionary with key rate durations
        """
        # Validate inputs
        spot_rates = self._validate_numeric_input(spot_rates, 'spot_rates')
        face_value = self._validate_positive(face_value, 'face_value')

        if key_rate_maturities is None:
            key_rate_maturities = [1, 2, 3, 5, 7, 10]

        coupon = (coupon_rate * face_value) / frequency
        periods = len(spot_rates)

        # Calculate base price
        base_price = 0
        for i, spot in enumerate(spot_rates):
            t = (i + 1) / frequency
            cf = coupon if i < periods - 1 else coupon + face_value
            base_price += cf / ((1 + spot) ** t)

        if base_price <= 0:
            raise CalculationError("Base price must be positive", calculation_type='key_rate_duration')

        key_rate_durations = []

        for key_maturity in key_rate_maturities:
            if key_maturity > periods / frequency:
                continue

            # Shift rate at key maturity
            shocked_rates = list(spot_rates)
            key_period = int(key_maturity * frequency) - 1

            if 0 <= key_period < len(shocked_rates):
                shocked_rates[key_period] += delta_rate

                # Calculate shocked price
                shocked_price = 0
                for i, spot in enumerate(shocked_rates):
                    t = (i + 1) / frequency
                    cf = coupon if i < periods - 1 else coupon + face_value
                    shocked_price += cf / ((1 + spot) ** t)

                krd = -(shocked_price - base_price) / (base_price * delta_rate)

                key_rate_durations.append({
                    'maturity': key_maturity,
                    'key_rate_duration': krd
                })

        total_krd = sum(k['key_rate_duration'] for k in key_rate_durations)

        return self._create_result_dict(
            value=total_krd,
            method='key_rate_duration',
            parameters={
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'frequency': frequency,
                'delta_rate': delta_rate
            },
            metadata={
                'key_rate_durations': key_rate_durations,
                'base_price': base_price,
                'num_key_rates': len(key_rate_durations),
                'note': 'KRD shows sensitivity to specific points on the yield curve'
            }
        )

    def calculate_convexity(
        self,
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        years_to_maturity: float = 10.0,
        ytm: float = 0.05,
        frequency: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate bond convexity.

        Convexity = sum(t*(t+1)*PV(CF_t)) / (Price * (1+y/n)^2 * n^2)

        Args:
            face_value: Face/par value
            coupon_rate: Annual coupon rate (decimal)
            years_to_maturity: Years until maturity
            ytm: Yield to maturity (decimal)
            frequency: Coupon payments per year

        Returns:
            Dictionary with convexity measure
        """
        # Validate inputs
        face_value = self._validate_positive(face_value, 'face_value')
        coupon_rate = self._validate_numeric_input(coupon_rate, 'coupon_rate')
        years_to_maturity = self._validate_positive(years_to_maturity, 'years_to_maturity')
        ytm = self._validate_numeric_input(ytm, 'ytm')

        # Zero coupon bond
        if frequency == 0 or coupon_rate == 0:
            price = face_value / ((1 + ytm) ** years_to_maturity)
            convexity = years_to_maturity * (years_to_maturity + 1) / ((1 + ytm) ** 2)
            return self._create_result_dict(
                value=convexity,
                method='convexity_zero',
                parameters={
                    'face_value': face_value,
                    'years_to_maturity': years_to_maturity,
                    'ytm': ytm
                },
                metadata={
                    'price': price,
                    'note': 'Zero coupon bond convexity'
                }
            )

        periods = int(years_to_maturity * frequency)
        periodic_rate = ytm / frequency
        coupon = (coupon_rate * face_value) / frequency

        price = 0
        convexity_sum = 0

        for t in range(1, periods + 1):
            cf = coupon if t < periods else coupon + face_value
            discount_factor = 1 / ((1 + periodic_rate) ** t)
            pv_cf = cf * discount_factor

            price += pv_cf
            convexity_sum += t * (t + 1) * pv_cf

        # Convexity formula
        convexity = convexity_sum / (price * ((1 + periodic_rate) ** 2) * (frequency ** 2))

        # Dollar convexity
        dollar_convexity = convexity * price / 100

        # Convexity adjustment for yield changes
        convexity_adj_1pct = 0.5 * convexity * (0.01 ** 2) * price
        convexity_adj_50bp = 0.5 * convexity * (0.005 ** 2) * price

        return self._create_result_dict(
            value=convexity,
            method='convexity',
            parameters={
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'years_to_maturity': years_to_maturity,
                'ytm': ytm,
                'frequency': frequency
            },
            metadata={
                'price': price,
                'dollar_convexity': dollar_convexity,
                'convexity_adjustment_1pct': convexity_adj_1pct,
                'convexity_adjustment_50bp': convexity_adj_50bp,
                'interpretation': 'Higher convexity means bond benefits more from yield changes'
            }
        )

    def calculate_effective_convexity(
        self,
        price: float,
        price_up: float,
        price_down: float,
        delta_yield: float = 0.01,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate Effective Convexity for bonds with embedded options.

        EffConv = (P_down + P_up - 2*P_0) / (P_0 * delta_y^2)

        Args:
            price: Current bond price
            price_up: Price when yield increases
            price_down: Price when yield decreases
            delta_yield: Yield change magnitude

        Returns:
            Dictionary with effective convexity
        """
        # Validate inputs
        price = self._validate_positive(price, 'price')
        price_up = self._validate_positive(price_up, 'price_up')
        price_down = self._validate_positive(price_down, 'price_down')
        delta_yield = self._validate_positive(delta_yield, 'delta_yield')

        effective_convexity = (price_down + price_up - 2 * price) / (price * delta_yield ** 2)

        # Convexity adjustment
        convexity_adj = 0.5 * effective_convexity * (delta_yield ** 2) * price

        return self._create_result_dict(
            value=effective_convexity,
            method='effective_convexity',
            parameters={
                'price': price,
                'price_up': price_up,
                'price_down': price_down,
                'delta_yield': delta_yield
            },
            metadata={
                'delta_yield_bps': delta_yield * 10000,
                'convexity_adjustment': convexity_adj,
                'note': 'Use for bonds with embedded options'
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Get list of supported calculation methods."""
        return ['macaulay', 'modified', 'effective', 'key_rate', 'convexity', 'effective_convexity']
