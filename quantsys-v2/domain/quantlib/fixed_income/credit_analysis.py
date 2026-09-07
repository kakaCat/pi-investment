"""
Credit Analysis Calculator
==========================

Credit risk measurement and analysis implementing CFA Institute standard
methodologies for fixed income credit evaluation.

Core algorithms migrated from FinceptTerminal credit_analysis.py (739 lines → ~350 lines)

Features:
- Default probability calculations
- Loss given default (LGD) estimates
- Expected loss calculations
- Credit spread analysis
- Merton structural model
- Credit VaR metrics
- Historical default rates by rating

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
from scipy import stats
from typing import Dict, Any, List, Optional
from domain.quantlib.base_calculator import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


# Historical average default rates by rating (1-year, approximate)
HISTORICAL_DEFAULT_RATES = {
    'AAA': 0.0001, 'AA+': 0.0002, 'AA': 0.0003, 'AA-': 0.0004,
    'A+': 0.0006, 'A': 0.0008, 'A-': 0.0010,
    'BBB+': 0.0015, 'BBB': 0.0020, 'BBB-': 0.0030,
    'BB+': 0.0050, 'BB': 0.0080, 'BB-': 0.0120,
    'B+': 0.0200, 'B': 0.0350, 'B-': 0.0500,
    'CCC': 0.1500, 'CC': 0.2500, 'C': 0.3500, 'D': 1.0000,
}

# Historical average recovery rates by seniority
HISTORICAL_RECOVERY_RATES = {
    'senior_secured': 0.53,
    'senior_unsecured': 0.37,
    'senior_subordinated': 0.31,
    'subordinated': 0.27,
    'junior_subordinated': 0.17,
}


class CreditAnalysisCalculator(BaseCalculator):
    """
    Credit analysis calculator implementing CFA-standard methodologies.

    Provides comprehensive credit risk analytics including default probability,
    loss given default, expected loss, and credit spreads.
    """

    def calculate(self, **kwargs) -> Dict[str, Any]:
        """
        Main calculation dispatcher.

        Args:
            method: Calculation method ('expected_loss', 'cumulative_pd', 'pd_from_spread',
                    'merton', 'credit_var', 'historical_pd')
            **kwargs: Method-specific parameters

        Returns:
            Calculation results dictionary
        """
        method = kwargs.get('method', 'expected_loss')

        if method == 'expected_loss':
            return self.calculate_expected_loss(**kwargs)
        elif method == 'cumulative_pd':
            return self.calculate_cumulative_pd(**kwargs)
        elif method == 'pd_from_spread':
            return self.pd_from_credit_spread(**kwargs)
        elif method == 'merton':
            return self.pd_from_merton_model(**kwargs)
        elif method == 'credit_var':
            return self.calculate_credit_var(**kwargs)
        elif method == 'historical_pd':
            return self.get_historical_pd(**kwargs)
        else:
            raise DataValidationError(f"Unknown method: {method}", field_name='method')

    def calculate_expected_loss(
        self,
        probability_of_default: float,
        exposure: float = 1000.0,
        recovery_rate: float = 0.40,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate expected loss from credit exposure.

        EL = PD × LGD × EAD
        where LGD = 1 - Recovery Rate

        Args:
            probability_of_default: Annual PD as decimal
            exposure: Exposure at default (EAD)
            recovery_rate: Expected recovery rate as decimal

        Returns:
            Dictionary with expected loss and components
        """
        # Validate inputs
        probability_of_default = self._validate_probability(probability_of_default, 'probability_of_default')
        exposure = self._validate_positive(exposure, 'exposure')
        recovery_rate = self._validate_probability(recovery_rate, 'recovery_rate')

        # Loss given default
        lgd = 1 - recovery_rate

        # Expected loss
        expected_loss = probability_of_default * lgd * exposure

        # Unexpected loss (standard deviation)
        # UL = sqrt(PD × (1-PD)) × LGD × EAD
        unexpected_loss = np.sqrt(probability_of_default * (1 - probability_of_default)) * lgd * exposure

        return self._create_result_dict(
            value=expected_loss,
            method='expected_loss',
            parameters={
                'probability_of_default': probability_of_default,
                'exposure': exposure,
                'recovery_rate': recovery_rate
            },
            metadata={
                'lgd': lgd,
                'lgd_amount': lgd * exposure,
                'unexpected_loss': unexpected_loss,
                'pd_percent': probability_of_default * 100,
                'el_percent': (expected_loss / exposure) * 100
            }
        )

    def calculate_cumulative_pd(
        self,
        annual_pd: float,
        years: int,
        method: str = 'hazard',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate cumulative default probability over multiple years.

        Args:
            annual_pd: Annual probability of default
            years: Number of years
            method: 'hazard' (more accurate) or 'simple'

        Returns:
            Dictionary with cumulative PD
        """
        # Validate inputs
        annual_pd = self._validate_probability(annual_pd, 'annual_pd')
        if years <= 0:
            raise DataValidationError("Years must be positive", field_name='years')

        cumulative_pds = []

        for t in range(1, years + 1):
            if method == 'hazard':
                # Using hazard rate (more accurate)
                cum_pd = 1 - (1 - annual_pd) ** t
            else:
                # Simple approximation
                cum_pd = min(annual_pd * t, 1.0)

            cumulative_pds.append({
                'year': t,
                'cumulative_pd': cum_pd,
                'cumulative_pd_pct': cum_pd * 100,
                'survival_prob': 1 - cum_pd
            })

        # Marginal PDs (probability of defaulting in year t given survival to year t-1)
        marginal_pds = []
        for i, cpd in enumerate(cumulative_pds):
            if i == 0:
                marginal = cpd['cumulative_pd']
            else:
                marginal = cpd['cumulative_pd'] - cumulative_pds[i - 1]['cumulative_pd']
            marginal_pds.append({
                'year': cpd['year'],
                'marginal_pd': marginal
            })

        return self._create_result_dict(
            value=[cpd['cumulative_pd'] for cpd in cumulative_pds],
            method='cumulative_pd',
            parameters={
                'annual_pd': annual_pd,
                'years': years,
                'calculation_method': method
            },
            metadata={
                'cumulative_pds': cumulative_pds,
                'marginal_pds': marginal_pds,
                'final_survival_prob': cumulative_pds[-1]['survival_prob']
            }
        )

    def pd_from_credit_spread(
        self,
        credit_spread: float,
        recovery_rate: float = 0.40,
        risk_free_rate: float = 0.03,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Derive implied probability of default from credit spread.

        PD ≈ Spread / (1 - Recovery Rate)

        Args:
            credit_spread: Credit spread over risk-free rate (decimal)
            recovery_rate: Expected recovery rate (decimal)
            risk_free_rate: Risk-free interest rate (decimal)

        Returns:
            Dictionary with implied PD
        """
        # Validate inputs
        credit_spread = self._validate_numeric_input(credit_spread, 'credit_spread')
        recovery_rate = self._validate_probability(recovery_rate, 'recovery_rate')
        risk_free_rate = self._validate_numeric_input(risk_free_rate, 'risk_free_rate')

        lgd = 1 - recovery_rate

        if lgd <= 0:
            raise CalculationError("LGD must be positive", calculation_type='pd_from_spread')

        # Simple approximation
        pd_simple = credit_spread / lgd

        # More accurate using hazard rate model
        # Spread = PD * LGD / (1 + r)
        pd_hazard = credit_spread * (1 + risk_free_rate) / lgd

        return self._create_result_dict(
            value=pd_simple,
            method='pd_from_credit_spread',
            parameters={
                'credit_spread': credit_spread,
                'recovery_rate': recovery_rate,
                'risk_free_rate': risk_free_rate
            },
            metadata={
                'implied_pd_simple': pd_simple,
                'implied_pd_simple_pct': pd_simple * 100,
                'implied_pd_hazard': pd_hazard,
                'implied_pd_hazard_pct': pd_hazard * 100,
                'credit_spread_bps': credit_spread * 10000,
                'lgd': lgd,
                'interpretation': f"Market implies ~{pd_simple * 100:.2f}% annual default probability"
            }
        )

    def pd_from_merton_model(
        self,
        asset_value: float,
        asset_volatility: float,
        debt_face_value: float,
        risk_free_rate: float,
        time_horizon: float = 1.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate default probability using Merton structural model.

        Distance to Default (DD) = (ln(V/D) + (r - σ²/2)T) / (σ√T)
        PD = N(-DD)

        Args:
            asset_value: Current firm asset value
            asset_volatility: Asset volatility (decimal)
            debt_face_value: Face value of debt
            risk_free_rate: Risk-free rate (decimal)
            time_horizon: Time horizon in years

        Returns:
            Dictionary with Merton model results
        """
        # Validate inputs
        asset_value = self._validate_positive(asset_value, 'asset_value')
        asset_volatility = self._validate_positive(asset_volatility, 'asset_volatility')
        debt_face_value = self._validate_positive(debt_face_value, 'debt_face_value')
        risk_free_rate = self._validate_numeric_input(risk_free_rate, 'risk_free_rate')
        time_horizon = self._validate_positive(time_horizon, 'time_horizon')

        # Distance to default calculation
        d1 = (np.log(asset_value / debt_face_value) +
              (risk_free_rate + 0.5 * asset_volatility ** 2) * time_horizon) / \
             (asset_volatility * np.sqrt(time_horizon))

        d2 = d1 - asset_volatility * np.sqrt(time_horizon)

        # Probability of default
        pd = stats.norm.cdf(-d2)

        # Distance to default (in standard deviations)
        distance_to_default = d2

        return self._create_result_dict(
            value=pd,
            method='merton_model',
            parameters={
                'asset_value': asset_value,
                'asset_volatility': asset_volatility,
                'debt_face_value': debt_face_value,
                'risk_free_rate': risk_free_rate,
                'time_horizon': time_horizon
            },
            metadata={
                'pd_percent': pd * 100,
                'distance_to_default': distance_to_default,
                'd1': d1,
                'd2': d2,
                'leverage_ratio': debt_face_value / asset_value,
                'interpretation': f"DD of {distance_to_default:.2f}σ implies {pd * 100:.2f}% default probability"
            }
        )

    def calculate_credit_var(
        self,
        probability_of_default: float,
        exposure: float = 1000.0,
        recovery_rate: float = 0.40,
        confidence_level: float = 0.99,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate Credit Value at Risk (CVaR).

        Args:
            probability_of_default: Annual PD as decimal
            exposure: Exposure at default
            recovery_rate: Expected recovery rate
            confidence_level: Confidence level (e.g., 0.99 for 99%)

        Returns:
            Dictionary with Credit VaR
        """
        # Validate inputs
        probability_of_default = self._validate_probability(probability_of_default, 'probability_of_default')
        exposure = self._validate_positive(exposure, 'exposure')
        recovery_rate = self._validate_probability(recovery_rate, 'recovery_rate')
        confidence_level = self._validate_probability(confidence_level, 'confidence_level')

        lgd = 1 - recovery_rate
        expected_loss = probability_of_default * lgd * exposure

        # For binary default model
        if probability_of_default < (1 - confidence_level):
            # No default at this confidence level
            credit_var = 0
        else:
            # Default occurs at this confidence level
            credit_var = lgd * exposure - expected_loss

        # Unexpected loss
        unexpected_loss = np.sqrt(probability_of_default * (1 - probability_of_default)) * lgd * exposure

        return self._create_result_dict(
            value=credit_var,
            method='credit_var',
            parameters={
                'probability_of_default': probability_of_default,
                'exposure': exposure,
                'recovery_rate': recovery_rate,
                'confidence_level': confidence_level
            },
            metadata={
                'expected_loss': expected_loss,
                'unexpected_loss': unexpected_loss,
                'lgd': lgd,
                'worst_case_loss': lgd * exposure,
                'confidence_level_pct': confidence_level * 100
            }
        )

    def get_historical_pd(
        self,
        rating: str,
        years: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get historical default probability by credit rating.

        Args:
            rating: Credit rating string (e.g., 'BBB', 'BB+')
            years: Time horizon

        Returns:
            Dictionary with historical default rates
        """
        # Normalize rating
        rating = rating.upper().strip()

        if rating not in HISTORICAL_DEFAULT_RATES:
            raise DataValidationError(f"Unknown rating: {rating}", field_name='rating')

        annual_pd = HISTORICAL_DEFAULT_RATES[rating]

        # Calculate cumulative PD if years > 1
        if years > 1:
            cumulative_pd = 1 - (1 - annual_pd) ** years
        else:
            cumulative_pd = annual_pd

        # Get typical recovery rate for investment grade vs high yield
        if rating in ['AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-']:
            typical_recovery = HISTORICAL_RECOVERY_RATES['senior_unsecured']
            grade = 'Investment Grade'
        else:
            typical_recovery = HISTORICAL_RECOVERY_RATES['subordinated']
            grade = 'High Yield'

        return self._create_result_dict(
            value=annual_pd,
            method='historical_pd',
            parameters={
                'rating': rating,
                'years': years
            },
            metadata={
                'annual_pd': annual_pd,
                'annual_pd_pct': annual_pd * 100,
                'cumulative_pd': cumulative_pd,
                'cumulative_pd_pct': cumulative_pd * 100,
                'typical_recovery_rate': typical_recovery,
                'grade': grade,
                'note': 'Based on historical average default rates'
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Get list of supported calculation methods."""
        return ['expected_loss', 'cumulative_pd', 'pd_from_spread', 'merton', 'credit_var', 'historical_pd']
