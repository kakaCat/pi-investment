"""
Bond Pricing Calculator
=======================

Bond valuation and pricing calculations implementing CFA Institute standard
methodologies for fixed income securities analysis.

Core algorithms migrated from FinceptTerminal bond_pricing.py (760 lines → ~400 lines)

Features:
- Zero coupon bond pricing
- Fixed-rate coupon bond pricing
- Perpetual bond pricing
- Callable/putable bond pricing
- Yield to maturity (YTM) calculation
- Yield to call (YTC) calculation
- Yield to worst (YTW) calculation
- Accrued interest calculation
- Clean and dirty price calculation

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
from scipy import optimize
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date

from domain.quantlib.base_calculator import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


class BondPricingCalculator(BaseCalculator):
    """
    Bond pricing calculator implementing CFA-standard valuation methods.

    Supports:
    - Zero coupon bonds
    - Fixed-rate coupon bonds
    - Perpetual bonds
    - Callable bonds
    - Putable bonds
    """

    def calculate(self, **kwargs) -> Dict[str, Any]:
        """
        Main calculation dispatcher for bond pricing.

        Args:
            method: Calculation method ('price', 'ytm', 'ytc', 'ytw', 'accrued')
            **kwargs: Method-specific parameters

        Returns:
            Calculation results dictionary
        """
        method = kwargs.get('method', 'price')

        if method == 'price':
            return self.calculate_price(**kwargs)
        elif method == 'ytm':
            return self.calculate_ytm(**kwargs)
        elif method == 'ytc':
            return self.calculate_ytc(**kwargs)
        elif method == 'ytw':
            return self.calculate_ytw(**kwargs)
        elif method == 'accrued':
            return self.calculate_accrued_interest(**kwargs)
        else:
            raise DataValidationError(f"Unknown method: {method}", field_name='method')

    def calculate_price(
        self,
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        ytm: float = 0.05,
        years_to_maturity: float = 10.0,
        frequency: int = 2,
        bond_type: str = 'coupon',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate bond price given yield to maturity.

        PV = sum(C/(1+y/n)^t) + FV/(1+y/n)^N

        Args:
            face_value: Face/par value of the bond
            coupon_rate: Annual coupon rate (decimal)
            ytm: Yield to maturity (decimal)
            years_to_maturity: Years until maturity
            frequency: Coupon payments per year (0=zero coupon, 1=annual, 2=semi-annual, 4=quarterly)
            bond_type: 'zero', 'coupon', 'perpetual'

        Returns:
            Dictionary with price and component details
        """
        # Validate inputs
        face_value = self._validate_positive(face_value, 'face_value')
        coupon_rate = self._validate_numeric_input(coupon_rate, 'coupon_rate')
        ytm = self._validate_numeric_input(ytm, 'ytm')
        years_to_maturity = self._validate_positive(years_to_maturity, 'years_to_maturity')

        if frequency not in [0, 1, 2, 4, 12]:
            raise DataValidationError("Frequency must be 0, 1, 2, 4, or 12", field_name='frequency')

        # Zero coupon bond
        if bond_type == 'zero' or frequency == 0:
            price = face_value / ((1 + ytm) ** years_to_maturity)
            return self._create_result_dict(
                value=price,
                method='bond_pricing_zero',
                parameters={
                    'face_value': face_value,
                    'ytm': ytm,
                    'years_to_maturity': years_to_maturity,
                    'bond_type': 'zero_coupon'
                },
                metadata={
                    'pv_coupons': 0.0,
                    'pv_principal': price,
                    'current_yield': 0.0,
                    'premium_discount': 'discount' if price < face_value else 'par'
                }
            )

        # Perpetual bond
        if bond_type == 'perpetual':
            if ytm <= 0:
                raise CalculationError("YTM must be positive for perpetual bonds", calculation_type='perpetual_bond')
            coupon_payment = face_value * coupon_rate / frequency
            price = coupon_payment / (ytm / frequency)
            current_yield = (face_value * coupon_rate) / price

            return self._create_result_dict(
                value=price,
                method='bond_pricing_perpetual',
                parameters={
                    'face_value': face_value,
                    'coupon_rate': coupon_rate,
                    'ytm': ytm,
                    'frequency': frequency,
                    'bond_type': 'perpetual'
                },
                metadata={
                    'periodic_coupon': coupon_payment,
                    'current_yield': current_yield,
                    'note': 'Perpetual bond has no maturity'
                }
            )

        # Fixed-rate coupon bond
        periods = int(years_to_maturity * frequency)
        periodic_rate = ytm / frequency
        coupon_payment = (coupon_rate * face_value) / frequency

        # PV of coupon payments (annuity formula)
        if periodic_rate > 0:
            pv_coupons = coupon_payment * (1 - (1 + periodic_rate) ** -periods) / periodic_rate
        else:
            pv_coupons = coupon_payment * periods

        # PV of principal
        pv_principal = face_value / ((1 + periodic_rate) ** periods)

        # Total price
        price = pv_coupons + pv_principal

        # Additional metrics
        current_yield = (face_value * coupon_rate) / price if price > 0 else 0
        premium_discount = 'premium' if price > face_value else 'discount' if price < face_value else 'par'

        return self._create_result_dict(
            value=price,
            method='bond_pricing_coupon',
            parameters={
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'ytm': ytm,
                'years_to_maturity': years_to_maturity,
                'frequency': frequency,
                'bond_type': 'fixed_coupon'
            },
            metadata={
                'pv_coupons': pv_coupons,
                'pv_principal': pv_principal,
                'num_periods': periods,
                'periodic_coupon': coupon_payment,
                'periodic_rate': periodic_rate,
                'current_yield': current_yield,
                'premium_discount': premium_discount,
                'price_percent': (price / face_value) * 100
            }
        )

    def calculate_ytm(
        self,
        price: float,
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        years_to_maturity: float = 10.0,
        frequency: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate yield to maturity given bond price.

        Uses numerical optimization (Brent's method) to solve for YTM.

        Args:
            price: Current market price
            face_value: Face/par value
            coupon_rate: Annual coupon rate (decimal)
            years_to_maturity: Years until maturity
            frequency: Coupon payments per year

        Returns:
            Dictionary with YTM and related metrics
        """
        # Validate inputs
        price = self._validate_positive(price, 'price')
        face_value = self._validate_positive(face_value, 'face_value')
        coupon_rate = self._validate_numeric_input(coupon_rate, 'coupon_rate')
        years_to_maturity = self._validate_positive(years_to_maturity, 'years_to_maturity')

        coupon_payment = (coupon_rate * face_value) / frequency if frequency > 0 else 0
        periods = int(years_to_maturity * frequency) if frequency > 0 else years_to_maturity

        def price_diff(y):
            """Calculate difference between calculated price and market price."""
            if frequency == 0:
                return face_value / ((1 + y) ** years_to_maturity) - price

            periodic_rate = y / frequency
            if periodic_rate <= -1:
                return float('inf')

            if periodic_rate != 0:
                pv_coupons = coupon_payment * (1 - (1 + periodic_rate) ** -periods) / periodic_rate
            else:
                pv_coupons = coupon_payment * periods

            pv_principal = face_value / ((1 + periodic_rate) ** periods)
            return pv_coupons + pv_principal - price

        try:
            # Use Brent's method for robust convergence
            ytm = optimize.brentq(price_diff, -0.99, 2.0, xtol=1e-10)
        except ValueError:
            # Fallback to Newton's method
            try:
                ytm = optimize.newton(price_diff, coupon_rate, tol=1e-10, maxiter=100)
            except:
                raise CalculationError("Could not converge to YTM solution", calculation_type='ytm')

        # Calculate related metrics
        current_yield = (coupon_rate * face_value) / price if price > 0 else 0

        # Bond equivalent yield (for comparison)
        if frequency == 2:
            bey = ytm
        else:
            bey = 2 * ((1 + ytm / frequency) ** (frequency / 2) - 1) if frequency > 0 else ytm

        # Effective annual yield
        eay = (1 + ytm / frequency) ** frequency - 1 if frequency > 0 else ytm

        return self._create_result_dict(
            value=ytm,
            method='ytm',
            parameters={
                'price': price,
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'years_to_maturity': years_to_maturity,
                'frequency': frequency
            },
            metadata={
                'ytm_percent': ytm * 100,
                'current_yield': current_yield,
                'current_yield_percent': current_yield * 100,
                'bond_equivalent_yield': bey,
                'effective_annual_yield': eay,
                'is_premium': price > face_value,
                'is_discount': price < face_value
            }
        )

    def calculate_ytc(
        self,
        price: float,
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        years_to_call: float = 5.0,
        call_price: float = 1050.0,
        frequency: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate yield to call for callable bonds.

        Args:
            price: Current market price
            face_value: Face/par value
            coupon_rate: Annual coupon rate (decimal)
            years_to_call: Years until first call date
            call_price: Call redemption price
            frequency: Coupon payments per year

        Returns:
            Dictionary with YTC and related metrics
        """
        # Validate inputs
        price = self._validate_positive(price, 'price')
        face_value = self._validate_positive(face_value, 'face_value')
        call_price = self._validate_positive(call_price, 'call_price')
        years_to_call = self._validate_positive(years_to_call, 'years_to_call')

        coupon_payment = (coupon_rate * face_value) / frequency
        periods = int(years_to_call * frequency)

        def price_diff(y):
            periodic_rate = y / frequency
            if periodic_rate <= -1:
                return float('inf')

            if periodic_rate != 0:
                pv_coupons = coupon_payment * (1 - (1 + periodic_rate) ** -periods) / periodic_rate
            else:
                pv_coupons = coupon_payment * periods

            pv_call = call_price / ((1 + periodic_rate) ** periods)
            return pv_coupons + pv_call - price

        try:
            ytc = optimize.brentq(price_diff, -0.99, 2.0, xtol=1e-10)
        except:
            try:
                ytc = optimize.newton(price_diff, coupon_rate, tol=1e-10, maxiter=100)
            except:
                raise CalculationError("Could not converge to YTC solution", calculation_type='ytc')

        return self._create_result_dict(
            value=ytc,
            method='ytc',
            parameters={
                'price': price,
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'years_to_call': years_to_call,
                'call_price': call_price,
                'frequency': frequency
            },
            metadata={
                'ytc_percent': ytc * 100,
                'call_premium': call_price - face_value,
                'call_premium_percent': ((call_price - face_value) / face_value) * 100
            }
        )

    def calculate_ytw(
        self,
        price: float,
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        years_to_maturity: float = 10.0,
        call_schedule: List[Tuple[float, float]] = None,
        frequency: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate yield to worst (minimum of YTM and all YTCs).

        Args:
            price: Current market price
            face_value: Face/par value
            coupon_rate: Annual coupon rate (decimal)
            years_to_maturity: Years until maturity
            call_schedule: List of (years_to_call, call_price) tuples
            frequency: Coupon payments per year

        Returns:
            Dictionary with YTW and all yield scenarios
        """
        # Calculate YTM
        ytm_result = self.calculate_ytm(price, face_value, coupon_rate, years_to_maturity, frequency)
        ytm = ytm_result['value']

        yields = [{'type': 'YTM', 'years': years_to_maturity, 'yield': ytm}]

        # Calculate YTC for each call date
        if call_schedule:
            for years_to_call, call_price in call_schedule:
                try:
                    ytc_result = self.calculate_ytc(
                        price, face_value, coupon_rate, years_to_call, call_price, frequency
                    )
                    ytc = ytc_result['value']
                    yields.append({'type': 'YTC', 'years': years_to_call, 'yield': ytc, 'call_price': call_price})
                except:
                    continue

        # Find minimum yield (worst case)
        ytw_scenario = min(yields, key=lambda x: x['yield'])
        ytw = ytw_scenario['yield']

        return self._create_result_dict(
            value=ytw,
            method='ytw',
            parameters={
                'price': price,
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'years_to_maturity': years_to_maturity,
                'frequency': frequency
            },
            metadata={
                'ytw_percent': ytw * 100,
                'ytw_scenario': ytw_scenario,
                'all_yields': yields,
                'num_scenarios': len(yields)
            }
        )

    def calculate_accrued_interest(
        self,
        face_value: float = 1000.0,
        coupon_rate: float = 0.05,
        frequency: int = 2,
        days_since_last_coupon: int = 45,
        day_count_convention: str = '30/360',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate accrued interest between coupon payment dates.

        Args:
            face_value: Face/par value
            coupon_rate: Annual coupon rate (decimal)
            frequency: Coupon payments per year
            days_since_last_coupon: Days since last coupon payment
            day_count_convention: '30/360', 'ACT/360', 'ACT/365', 'ACT/ACT'

        Returns:
            Dictionary with accrued interest
        """
        # Validate inputs
        face_value = self._validate_positive(face_value, 'face_value')
        coupon_rate = self._validate_numeric_input(coupon_rate, 'coupon_rate')

        if days_since_last_coupon < 0:
            raise DataValidationError("Days since last coupon must be non-negative", field_name='days_since_last_coupon')

        # Annual coupon payment
        annual_coupon = face_value * coupon_rate

        # Days in coupon period
        if day_count_convention == '30/360':
            days_in_period = 360 / frequency
        elif day_count_convention == 'ACT/360':
            days_in_period = 360 / frequency
        elif day_count_convention == 'ACT/365':
            days_in_period = 365 / frequency
        elif day_count_convention == 'ACT/ACT':
            days_in_period = 365.25 / frequency
        else:
            raise DataValidationError(f"Unknown day count convention: {day_count_convention}", field_name='day_count_convention')

        # Accrued interest
        accrued = (annual_coupon / frequency) * (days_since_last_coupon / days_in_period)

        return self._create_result_dict(
            value=accrued,
            method='accrued_interest',
            parameters={
                'face_value': face_value,
                'coupon_rate': coupon_rate,
                'frequency': frequency,
                'days_since_last_coupon': days_since_last_coupon,
                'day_count_convention': day_count_convention
            },
            metadata={
                'days_in_period': days_in_period,
                'fraction_of_period': days_since_last_coupon / days_in_period,
                'periodic_coupon': annual_coupon / frequency
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Get list of supported calculation methods."""
        return ['price', 'ytm', 'ytc', 'ytw', 'accrued']
