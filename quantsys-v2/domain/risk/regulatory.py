"""
Regulatory Risk Calculator
===========================

Basel III / FRTB regulatory capital calculations including market risk
standardised approach, FRTB sensitivities-based method, CVA capital charge,
capital adequacy ratio, and leverage ratio.

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


class RegulatoryRiskCalculator(BaseCalculator):
    """
    Regulatory risk and capital adequacy calculator.

    Computes Basel III market risk capital charges, FRTB standardised approach
    and IMA metrics, CVA capital charge, capital adequacy ratio, and leverage ratio.

    Methods:
        - basel_iii_market: Basel III standardised market risk charge
        - frtb_sa: FRTB Standardised Approach (sensitivities-based)
        - frtb_ima: FRTB Internal Models Approach
        - cva_capital: CVA capital charge
        - leverage_ratio: Leverage ratio calculation

    Example:
        calculator = RegulatoryRiskCalculator(precision=4)
        result = calculator.calculate(
            positions_data={'equity': 1000000, 'bond': 500000},
            risk_data={'equity_beta': 1.2, 'bond_duration': 5.0},
            method='basel_iii_market'
        )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize regulatory risk calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  positions_data: Dict[str, Any],
                  risk_data: Dict[str, Any],
                  method: str = 'basel_iii_market',
                  confidence_level: float = 0.99) -> Dict[str, Any]:
        """
        Calculate regulatory risk metrics.

        Args:
            positions_data: Dictionary with position information
                e.g., {'equity': notional_value, 'bond': notional_value, ...}
            risk_data: Dictionary with risk factor sensitivities
                e.g., {'equity_beta': 1.2, 'bond_duration': 5.0, ...}
            method: 'basel_iii_market', 'frtb_sa', 'frtb_ima', 'cva_capital', 'leverage_ratio'
            confidence_level: Confidence level (default: 0.99)

        Returns:
            Dictionary with regulatory capital results

        Raises:
            DataValidationError: If position or risk data is invalid
            ConfigurationError: If method is unsupported
            CalculationError: If computation fails
        """
        confidence_level = self._validate_probability(confidence_level, 'confidence_level')
        method = self.validate_method(method)

        if not positions_data:
            raise DataValidationError(
                "Positions data cannot be empty",
                field_name='positions_data'
            )

        try:
            if method == 'basel_iii_market':
                result = self._basel_iii_market_risk(positions_data, risk_data, confidence_level)
            elif method == 'frtb_sa':
                result = self._frtb_standardised_approach(positions_data, risk_data)
            elif method == 'frtb_ima':
                result = self._frtb_ima(positions_data, risk_data, confidence_level)
            elif method == 'cva_capital':
                result = self._cva_capital_charge(
                    positions_data.get('cva', 0.0),
                    risk_data
                )
            elif method == 'leverage_ratio':
                result = self.calculate_leverage_ratio(
                    tier1_capital=positions_data.get('tier1_capital', 0.0),
                    exposure_measure=positions_data.get('exposure_measure', 1.0)
                )
                return result
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            return self._create_result_dict(
                value=result,
                method=f'regulatory_{method}',
                parameters={
                    'method': method,
                    'confidence_level': confidence_level
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='RegulatoryRisk')

    def _basel_iii_market_risk(self,
                                positions: Dict[str, Any],
                                risk_data: Dict[str, Any],
                                cl: float) -> Dict[str, Any]:
        """
        Calculate Basel III standardised market risk capital charge.

        Simplified standardised approach:
        - Equity risk: 8% capital charge on equity positions
        - Interest rate risk: Duration-based capital charge
        - FX risk: 8% on net open FX positions
        - Commodity risk: 15% on commodity positions

        Args:
            positions: Position data
            risk_data: Risk sensitivity data
            cl: Confidence level

        Returns:
            Dictionary with market risk capital charges
        """
        charges = {}

        # Equity risk charge
        equity_position = positions.get('equity', 0.0)
        equity_beta = risk_data.get('equity_beta', 1.0)
        # Specific risk: 8% for general market, adjusted by beta
        equity_general_risk = abs(equity_position) * 0.08 * equity_beta
        equity_specific_risk = abs(equity_position) * 0.04  # 4% specific risk
        charges['equity_general_risk'] = float(self._round_result(equity_general_risk))
        charges['equity_specific_risk'] = float(self._round_result(equity_specific_risk))
        charges['equity_total'] = float(self._round_result(equity_general_risk + equity_specific_risk))

        # Interest rate risk charge
        bond_position = positions.get('bond', 0.0)
        bond_duration = risk_data.get('bond_duration', 1.0)
        # Duration-based method: position * duration * basis point risk weight
        # Standard: 0.7% per year of duration (simplified)
        interest_rate_charge = abs(bond_position) * abs(bond_duration) * 0.007
        charges['interest_rate_risk'] = float(self._round_result(interest_rate_charge))

        # FX risk charge (8% on net open position)
        fx_position = positions.get('fx', 0.0)
        fx_charge = abs(fx_position) * 0.08
        charges['fx_risk'] = float(self._round_result(fx_charge))

        # Commodity risk charge (15%)
        commodity_position = positions.get('commodity', 0.0)
        commodity_charge = abs(commodity_position) * 0.15
        charges['commodity_risk'] = float(self._round_result(commodity_charge))

        # Total market risk capital charge (simplified: sum of components)
        total_charge = sum([
            equity_general_risk + equity_specific_risk,
            interest_rate_charge,
            fx_charge,
            commodity_charge
        ])

        charges['total_market_risk_capital'] = float(self._round_result(total_charge))

        return charges

    def _frtb_standardised_approach(self,
                                     positions: Dict[str, Any],
                                     risk_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate FRTB Standardised Approach (Sensitivities-Based Method).

        Computes delta, vega, and curvature risk charges and aggregates
        them into the total FRTB capital requirement.

        The SBM involves:
        1. Computing sensitivities (delta, vega, curvature) for each risk factor
        2. Applying risk weights to each sensitivity
        3. Aggregating within and across risk buckets using correlation matrices

        Args:
            positions: Position data (notionals, asset classes)
            risk_data: Sensitivity data (delta, vega, curvature per risk factor)

        Returns:
            Dictionary with FRTB capital charges
        """
        charges = {}

        # Delta risk charge
        delta_sensitivities = risk_data.get('delta_sensitivities', {})
        delta_charge = self._compute_sbm_component(
            delta_sensitivities,
            risk_data.get('delta_risk_weights', {}),
            risk_data.get('delta_correlations', {})
        )
        charges['delta_charge'] = float(self._round_result(delta_charge))

        # Vega risk charge
        vega_sensitivities = risk_data.get('vega_sensitivities', {})
        vega_charge = self._compute_sbm_component(
            vega_sensitivities,
            risk_data.get('vega_risk_weights', {}),
            risk_data.get('vega_correlations', {})
        )
        charges['vega_charge'] = float(self._round_result(vega_charge))

        # Curvature risk charge
        curvature_sensitivities = risk_data.get('curvature_sensitivities', {})
        curvature_charge = self._compute_curvature_component(
            curvature_sensitivities,
            risk_data.get('curvature_risk_weights', {})
        )
        charges['curvature_charge'] = float(self._round_result(curvature_charge))

        # Total FRTB SA capital charge
        # Simplified: sum of delta, vega, curvature
        total_sbm = delta_charge + vega_charge + curvature_charge

        # Default risk charge (DRC) - simplified
        drc = self._compute_default_risk_charge(positions, risk_data)
        charges['default_risk_charge'] = float(self._round_result(drc))

        total_frtb = total_sbm + drc
        charges['total_frtb_sa_capital'] = float(self._round_result(total_frtb))

        return charges

    def _compute_sbm_component(self,
                                sensitivities: Dict[str, float],
                                risk_weights: Dict[str, float],
                                correlations: Dict[str, float]) -> float:
        """
        Compute a single SBM component (delta/vega) using the bucket aggregation formula.

        K_b = sqrt(sum(WS_k^2) + sum(rho_kl * WS_k * WS_l)) for k != l within each bucket
        K_total = sqrt(sum(K_b^2) + sum(gamma_bc * S_b * S_c)) across buckets

        Simplified implementation: weighted sum of absolute sensitivities
        when full correlation matrix is not provided.

        Args:
            sensitivities: Dict of risk_factor -> sensitivity value
            risk_weights: Dict of risk_factor -> risk weight
            correlations: Dict of (factor_k, factor_l) -> correlation

        Returns:
            SBM component capital charge
        """
        if not sensitivities:
            return 0.0

        # Apply risk weights to sensitivities
        factor_names = list(sensitivities.keys())
        n = len(factor_names)

        if n == 0:
            return 0.0

        # Build weighted sensitivities
        ws = np.zeros(n)
        for i, factor in enumerate(factor_names):
            sens = sensitivities.get(factor, 0.0)
            rw = risk_weights.get(factor, 0.01)  # Default risk weight
            ws[i] = sens * rw

        # With correlations, use quadratic form: sqrt(ws^T * C * ws)
        # Without correlations, use sum of absolute weighted sensitivities
        has_correlations = len(correlations) > 0

        if has_correlations:
            corr_matrix = np.eye(n)
            for (k, l), rho in correlations.items():
                if k in factor_names and l in factor_names:
                    ki = factor_names.index(k)
                    li = factor_names.index(l)
                    corr_matrix[ki, li] = rho
                    corr_matrix[li, ki] = rho

            # K = sqrt(ws^T * C * ws)
            capital = np.sqrt(ws.T @ corr_matrix @ ws)
        else:
            # Conservative: sum of absolute weighted sensitivities
            capital = np.sum(np.abs(ws))

        return float(capital)

    def _compute_curvature_component(self,
                                      sensitivities: Dict[str, float],
                                      risk_weights: Dict[str, float]) -> float:
        """
        Compute curvature risk charge for FRTB.

        Curvature risk captures non-linear risk not captured by delta/vega.
        Simplified: CVR = sum(max(0, CVR_k)) for each risk factor,
        where CVR_k measures the loss under upward/downward shocks.

        Args:
            sensitivities: Curvature sensitivities
            risk_weights: Risk weights

        Returns:
            Curvature risk capital charge
        """
        if not sensitivities:
            return 0.0

        total_curvature = 0.0
        for factor, sens in sensitivities.items():
            rw = risk_weights.get(factor, 0.01)
            # Curvature risk = sensitivity * risk_weight^2 (simplified)
            cvr = abs(sens) * (rw ** 2)
            total_curvature += max(0.0, cvr)

        return float(total_curvature)

    def _compute_default_risk_charge(self,
                                      positions: Dict[str, Any],
                                      risk_data: Dict[str, Any]) -> float:
        """
        Compute Default Risk Charge (DRC) for FRTB.

        Simplified: Sum of notional * risk_weight * (1 - recovery) per issuer.
        Default risk weight = 0.5% for investment grade, 1.5% for high yield.

        Args:
            positions: Position data
            risk_data: Risk data

        Returns:
            DRC capital charge
        """
        drc = 0.0
        credit_positions = positions.get('credit', {})
        if isinstance(credit_positions, dict):
            for issuer, notional in credit_positions.items():
                rating = risk_data.get(f'credit_rating_{issuer}', 'IG')
                rw = 0.005 if rating.upper() == 'IG' else 0.015
                drc += abs(notional) * rw

        return float(drc)

    def _frtb_ima(self,
                   positions: Dict[str, Any],
                   risk_data: Dict[str, Any],
                   cl: float) -> Dict[str, Any]:
        """
        Calculate FRTB Internal Models Approach (IMA) capital.

        IMA capital = max(VaR_t-1 * multiplier, VaR_avg * multiplier)
        + Stress VaR component
        + Default Risk Charge (DRC)

        This is a simplified implementation.

        Args:
            positions: Position data including VaR values
            risk_data: Risk data
            cl: Confidence level

        Returns:
            Dictionary with IMA capital charges
        """
        ima = {}

        # VaR-based component
        var_current = risk_data.get('var_current', 0.0)
        var_avg_60d = risk_data.get('var_avg_60d', 0.0)
        var_multiplier = risk_data.get('var_multiplier', 3.0)

        # Larger of current VaR and 60-day average VaR, times multiplier
        var_capital = max(var_current, var_avg_60d) * var_multiplier
        ima['var_capital'] = float(self._round_result(var_capital))

        # Stressed VaR component
        svar_current = risk_data.get('svar_current', 0.0)
        svar_avg_60d = risk_data.get('svar_avg_60d', 0.0)
        svar_multiplier = risk_data.get('svar_multiplier', 3.0)

        svar_capital = max(svar_current, svar_avg_60d) * svar_multiplier
        ima['stressed_var_capital'] = float(self._round_result(svar_capital))

        # DRC
        drc = self._compute_default_risk_charge(positions, risk_data)
        ima['default_risk_charge'] = float(self._round_result(drc))

        # Total IMA capital
        total_ima = var_capital + svar_capital + drc
        ima['total_ima_capital'] = float(self._round_result(total_ima))

        return ima

    def _cva_capital_charge(self,
                             cva_value: float,
                             counterparty_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate CVA capital charge under Basel III.

        Two approaches:
        1. Standardised: Uses external credit ratings
        2. Advanced: Based on internal EE profiles and CDS spreads

        Simplified implementation: CVA_charge = sum(CVA_i * risk_weight_i)

        Args:
            cva_value: Total CVA
            counterparty_data: Counterparty-specific data

        Returns:
            Dictionary with CVA capital charge components
        """
        result = {}

        # Standardised approach CVA capital
        # Risk weights by credit quality: AAA=0.7%, AA=0.8%, A=1.0%, BBB=2.0%, BB=3.0%, B=6.0%, CCC=10%, lower=15%
        rating_weights = {
            'AAA': 0.007, 'AA': 0.008, 'A': 0.010,
            'BBB': 0.020, 'BB': 0.030, 'B': 0.060,
            'CCC': 0.100, 'CC': 0.150, 'C': 0.150,
            'D': 0.150
        }

        cva_cap_standardised = 0.0
        counterparties = counterparty_data.get('counterparties', {})
        if counterparties:
            for cpty_name, cpty_info in counterparties.items():
                cpty_cva = cpty_info.get('cva', 0.0)
                cpty_rating = cpty_info.get('rating', 'BBB')
                rw = rating_weights.get(cpty_rating.upper(), 0.02)
                cva_cap_standardised += abs(cpty_cva) * rw
        else:
            # No breakdown by counterparty, use overall CVA with BBB weight
            cva_cap_standardised = abs(cva_value) * 0.02

        result['cva_capital_standardised'] = float(self._round_result(cva_cap_standardised))

        # Advanced approach: based on EE and CDS spreads
        ee_profiles = counterparty_data.get('ee_profiles', [])
        if ee_profiles:
            cva_cap_advanced = 0.0
            for i, ee_profile in enumerate(ee_profiles):
                cds_spread = ee_profile.get('cds_spread', 0.01)
                ee = ee_profile.get('ee', 0.0)
                # Capital = 2.33 * sqrt(sum of weighted exposures)
                cva_cap_advanced += abs(ee) * cds_spread
            result['cva_capital_advanced'] = float(self._round_result(cva_cap_advanced))
        else:
            result['cva_capital_advanced'] = float(self._round_result(cva_cap_standardised * 1.5))

        return result

    def calculate_capital_adequacy_ratio(self,
                                          tier1: float,
                                          tier2: float,
                                          rwa: float) -> Dict[str, Any]:
        """
        Calculate Capital Adequacy Ratio (CAR).

        CAR = (Tier 1 Capital + Tier 2 Capital) / Risk-Weighted Assets

        Regulatory minimums:
        - CET1 ratio >= 4.5%
        - Tier 1 ratio >= 6.0%
        - Total CAR >= 8.0%

        Args:
            tier1: Tier 1 capital (CET1)
            tier2: Tier 2 capital
            rwa: Risk-weighted assets

        Returns:
            Dictionary with CAR metrics

        Raises:
            DataValidationError: If RWA is zero or negative
        """
        if rwa <= 0:
            raise DataValidationError(
                "Risk-weighted assets must be positive",
                field_name='rwa'
            )
        if tier1 < 0 or tier2 < 0:
            raise DataValidationError(
                "Capital values must be non-negative",
                field_name='tier1/tier2'
            )

        total_capital = tier1 + tier2
        car = total_capital / rwa
        tier1_ratio = tier1 / rwa

        # Determine compliance
        car_compliant = car >= 0.08
        tier1_compliant = tier1_ratio >= 0.06

        return self._create_result_dict(
            value={
                'total_car': float(self._round_result(car)),
                'tier1_ratio': float(self._round_result(tier1_ratio)),
                'tier1_capital': float(tier1),
                'tier2_capital': float(tier2),
                'total_capital': float(total_capital),
                'risk_weighted_assets': float(rwa),
            },
            method='capital_adequacy_ratio',
            parameters={
                'tier1': tier1,
                'tier2': tier2,
                'rwa': rwa
            },
            metadata={
                'car_compliant': car_compliant,
                'tier1_compliant': tier1_compliant,
                'regulatory_minimum_car': 0.08,
                'regulatory_minimum_tier1': 0.06
            }
        )

    def calculate_leverage_ratio(self,
                                  tier1_capital: float,
                                  exposure_measure: float) -> Dict[str, Any]:
        """
        Calculate Basel III Leverage Ratio.

        Leverage Ratio = Tier 1 Capital / Total Exposure Measure

        Regulatory minimum: >= 3%

        Args:
            tier1_capital: Tier 1 capital amount
            exposure_measure: Total exposure measure (on + off balance sheet)

        Returns:
            Dictionary with leverage ratio

        Raises:
            DataValidationError: If exposure is zero or negative
        """
        if exposure_measure <= 0:
            raise DataValidationError(
                "Exposure measure must be positive",
                field_name='exposure_measure'
            )
        if tier1_capital < 0:
            raise DataValidationError(
                "Tier 1 capital must be non-negative",
                field_name='tier1_capital'
            )

        leverage_ratio = tier1_capital / exposure_measure
        compliant = leverage_ratio >= 0.03

        return self._create_result_dict(
            value=float(self._round_result(leverage_ratio)),
            method='leverage_ratio',
            parameters={
                'tier1_capital': tier1_capital,
                'exposure_measure': exposure_measure
            },
            metadata={
                'compliant': compliant,
                'regulatory_minimum': 0.03,
                'interpretation': (
                    'Compliant with Basel III leverage ratio requirement'
                    if compliant else
                    'Below Basel III leverage ratio minimum of 3%'
                )
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Return list of supported regulatory calculation methods."""
        return ['basel_iii_market', 'frtb_sa', 'frtb_ima', 'cva_capital', 'leverage_ratio']
