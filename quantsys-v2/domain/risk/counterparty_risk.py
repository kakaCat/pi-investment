"""
Counterparty Risk Calculator
=============================

XVA (Valuation Adjustment) calculations including CVA, DVA, bilateral CVA,
FVA, credit exposure metrics, and default probability estimation from CDS spreads.

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    DataValidationError,
    InsufficientDataError,
    ConfigurationError,
)


class CounterpartyRiskCalculator(BaseCalculator):
    """
    Counterparty risk and XVA calculation engine.

    Computes Credit Valuation Adjustment (CVA), Debit Valuation Adjustment (DVA),
    bilateral CVA, Funding Valuation Adjustment (FVA), and credit exposure metrics.

    Methods:
        - cva: Credit Valuation Adjustment
        - dva: Debit Valuation Adjustment
        - bilateral_cva: Bilateral CVA
        - fva: Funding Valuation Adjustment

    Example:
        calculator = CounterpartyRiskCalculator(precision=4)
        exposures = [(1.0, 1000000), (2.0, 800000), (3.0, 500000)]
        result = calculator.calculate(exposures, default_probabilities=0.02,
                                       recovery_rate=0.4, risk_free_rate=0.03)
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize counterparty risk calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Default risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  exposure_profile: List[Tuple[float, float]],
                  default_probabilities: Union[List[float], float],
                  recovery_rate: float = 0.4,
                  risk_free_rate: float = 0.0,
                  method: str = 'cva',
                  notional: float = 1.0) -> Dict[str, Any]:
        """
        Calculate counterparty risk metrics.

        Args:
            exposure_profile: List of (time, expected_exposure) tuples
            default_probabilities: List of marginal default probabilities per period or constant CDS-implied PD
            recovery_rate: Recovery rate (LGD = 1 - recovery_rate) (default: 0.4)
            risk_free_rate: Risk-free rate for discounting (default: from instance)
            method: 'cva', 'dva', 'bilateral_cva', or 'fva'
            notional: Notional amount for scaling (default: 1.0)

        Returns:
            Dictionary with XVA results

        Raises:
            DataValidationError: If exposure profile or probabilities are invalid
            ConfigurationError: If method is unsupported
            CalculationError: If computation fails
        """
        # Validate inputs
        if not exposure_profile or len(exposure_profile) == 0:
            raise DataValidationError(
                "Exposure profile cannot be empty",
                field_name='exposure_profile'
            )

        recovery_rate = self._validate_probability(recovery_rate, 'recovery_rate')

        # Validate method
        method = self.validate_method(method)

        # Extract times and exposures
        times = np.array([t for t, e in exposure_profile])
        exposures = np.array([e for t, e in exposure_profile])

        # Compute discount factors
        discount_factors = np.exp(-risk_free_rate * times)

        try:
            if method == 'cva':
                # Handle default probabilities: can be list or single float
                if isinstance(default_probabilities, (int, float)):
                    # Convert single PD to marginal PD curve using constant hazard rate
                    hazard_rate = -np.log(1 - default_probabilities)
                    pd_curve = self._build_pd_curve(times, hazard_rate)
                else:
                    pd_curve = np.array(default_probabilities)

                cva_value = self._calculate_cva(exposures, pd_curve, recovery_rate, discount_factors)
                return self._create_result_dict(
                    value=float(cva_value * notional),
                    method='cva',
                    parameters={
                        'recovery_rate': recovery_rate,
                        'risk_free_rate': risk_free_rate,
                        'notional': notional,
                        'n_time_points': len(exposure_profile)
                    },
                    metadata={
                        'interpretation': 'Credit Valuation Adjustment (expected loss from counterparty default)'
                    }
                )

            elif method == 'dva':
                # DVA uses own default probability
                if isinstance(default_probabilities, (int, float)):
                    hazard_rate = -np.log(1 - default_probabilities)
                    pd_curve = self._build_pd_curve(times, hazard_rate)
                else:
                    pd_curve = np.array(default_probabilities)

                # For DVA, exposure is negative expected exposure (ENE)
                ene = -exposures  # ENE = -EE for DVA perspective
                dva_value = self._calculate_dva(ene, pd_curve, recovery_rate, discount_factors)
                return self._create_result_dict(
                    value=float(dva_value * notional),
                    method='dva',
                    parameters={
                        'recovery_rate': recovery_rate,
                        'risk_free_rate': risk_free_rate,
                        'notional': notional,
                        'n_time_points': len(exposure_profile)
                    },
                    metadata={
                        'interpretation': 'Debit Valuation Adjustment (benefit from own default)'
                    }
                )

            elif method == 'bilateral_cva':
                # bilateral_cva requires both own and counterparty PD
                # default_probabilities should be (own_pd, counterparty_pd) tuple/list
                if isinstance(default_probabilities, (list, tuple)):
                    if len(default_probabilities) == 2 and isinstance(default_probabilities[0], (int, float)):
                        own_pd = default_probabilities[0]
                        cpty_pd = default_probabilities[1]
                        own_hazard = -np.log(1 - own_pd)
                        cpty_hazard = -np.log(1 - cpty_pd)
                        own_pd_curve = self._build_pd_curve(times, own_hazard)
                        cpty_pd_curve = self._build_pd_curve(times, cpty_hazard)
                    else:
                        own_pd_curve = np.array(default_probabilities[0])
                        cpty_pd_curve = np.array(default_probabilities[1])
                else:
                    raise DataValidationError(
                        "Bilateral CVA requires (own_pd, cpty_pd) tuple",
                        field_name='default_probabilities'
                    )

                ene = -exposures  # ENE
                bcva_value = self._calculate_bilateral_cva(
                    exposures, ene, own_pd_curve, cpty_pd_curve,
                    recovery_rate, discount_factors
                )
                return self._create_result_dict(
                    value=float(bcva_value * notional),
                    method='bilateral_cva',
                    parameters={
                        'recovery_rate': recovery_rate,
                        'risk_free_rate': risk_free_rate,
                        'notional': notional,
                        'n_time_points': len(exposure_profile)
                    },
                    metadata={
                        'interpretation': 'Bilateral CVA (net of CVA and DVA)'
                    }
                )

            elif method == 'fva':
                # FVA uses funding spread curve
                # default_probabilities is treated as funding spread (bps) per period
                if isinstance(default_probabilities, (int, float)):
                    funding_spread_curve = np.full(len(times), default_probabilities)
                else:
                    funding_spread_curve = np.array(default_probabilities)

                fva_value = self._calculate_fva(exposures, funding_spread_curve, discount_factors)
                return self._create_result_dict(
                    value=float(fva_value * notional),
                    method='fva',
                    parameters={
                        'risk_free_rate': risk_free_rate,
                        'notional': notional,
                        'n_time_points': len(exposure_profile)
                    },
                    metadata={
                        'interpretation': 'Funding Valuation Adjustment (cost of funding uncollateralized positions)'
                    }
                )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='CounterpartyRisk')

    def _build_pd_curve(self, times: np.ndarray, hazard_rate: float) -> np.ndarray:
        """
        Build cumulative default probability curve from constant hazard rate.

        PD_cum(t) = 1 - exp(-hazard_rate * t)
        Marginal PD_i = PD_cum(t_i) - PD_cum(t_{i-1})

        Args:
            times: Time points
            hazard_rate: Constant hazard rate

        Returns:
            Array of marginal default probabilities
        """
        # Cumulative PD at each time point
        cum_pd = 1 - np.exp(-hazard_rate * times)

        # Marginal PDs
        marginal_pd = np.zeros(len(times))
        marginal_pd[0] = cum_pd[0]
        for i in range(1, len(times)):
            marginal_pd[i] = cum_pd[i] - cum_pd[i - 1]

        return marginal_pd

    def _calculate_cva(self,
                       EE: np.ndarray,
                       PD_curve: np.ndarray,
                       recovery: float,
                       DF: np.ndarray) -> float:
        """
        Calculate Credit Valuation Adjustment.

        CVA = (1 - recovery) * sum(DF_i * EE_i * marginal_PD_i)

        Args:
            EE: Expected exposure at each time point
            PD_curve: Marginal default probabilities
            recovery: Recovery rate
            DF: Discount factors

        Returns:
            CVA value
        """
        loss_given_default = 1 - recovery
        cva = loss_given_default * np.sum(DF * EE * PD_curve)
        return float(cva)

    def _calculate_dva(self,
                       ENE: np.ndarray,
                       own_PD: np.ndarray,
                       recovery: float,
                       DF: np.ndarray) -> float:
        """
        Calculate Debit Valuation Adjustment.

        DVA = (1 - recovery) * sum(DF_i * ENE_i * own_marginal_PD_i)

        Args:
            ENE: Expected negative exposure
            own_PD: Own marginal default probabilities
            recovery: Recovery rate
            DF: Discount factors

        Returns:
            DVA value
        """
        # ENE should only be positive (representing benefit from own default)
        ene_positive = np.maximum(ENE, 0)
        loss_given_default = 1 - recovery
        dva = loss_given_default * np.sum(DF * ene_positive * own_PD)
        return float(dva)

    def _calculate_bilateral_cva(self,
                                 EE: np.ndarray,
                                 ENE: np.ndarray,
                                 own_PD: np.ndarray,
                                 cpty_PD: np.ndarray,
                                 recovery: float,
                                 DF: np.ndarray) -> float:
        """
        Calculate Bilateral CVA.

        BCVA = CVA - DVA
        CVA = (1-R) * sum(DF_i * EE_i * cpty_marginal_PD_i * (1 - own_survival_i))
        DVA = (1-R) * sum(DF_i * ENE_i * own_marginal_PD_i * (1 - cpty_survival_i))

        Args:
            EE: Expected exposure
            ENE: Expected negative exposure
            own_PD: Own marginal default probabilities
            cpty_PD: Counterparty marginal default probabilities
            recovery: Recovery rate
            DF: Discount factors

        Returns:
            Bilateral CVA value
        """
        loss_given_default = 1 - recovery

        # Build survival probabilities
        cpty_cum_pd = np.cumsum(cpty_PD)
        cpty_survival = 1 - cpty_cum_pd

        own_cum_pd = np.cumsum(own_PD)
        own_survival = 1 - own_cum_pd

        # CVA: loss from counterparty default, conditional on own survival
        cva = loss_given_default * np.sum(DF * EE * cpty_PD * own_survival)

        # DVA: benefit from own default, conditional on counterparty survival
        ene_positive = np.maximum(ENE, 0)
        dva = loss_given_default * np.sum(DF * ene_positive * own_PD * cpty_survival)

        bcva = cva - dva
        return float(bcva)

    def _calculate_fva(self,
                       EE: np.ndarray,
                       funding_spread_curve: np.ndarray,
                       DF: np.ndarray) -> float:
        """
        Calculate Funding Valuation Adjustment.

        FVA = sum(funding_spread_i * DF_i * EE_i * delta_t_i)

        Simplified approach: discrete FVA with average EE between time points.

        Args:
            EE: Expected exposure
            funding_spread_curve: Funding spread at each time point
            DF: Discount factors

        Returns:
            FVA value
        """
        # Use piecewise constant EE for each period
        fva = 0.0

        for i in range(len(EE)):
            # EE at this time point times the spread
            spread = funding_spread_curve[i]
            exposure = EE[i]
            df = DF[i]
            fva += spread * df * exposure

        return float(fva)

    def calculate_default_probability_from_cds(self,
                                                cds_spread: float,
                                                recovery_rate: float = 0.4,
                                                T: float = 5.0) -> float:
        """
        Calculate default probability implied by CDS spread.

        PD = 1 - exp(-cds_spread * T / (1 - recovery_rate))

        Args:
            cds_spread: CDS spread (as decimal, e.g., 0.01 for 100 bps)
            recovery_rate: Recovery rate (default: 0.4)
            T: Time horizon in years (default: 5.0)

        Returns:
            Implied default probability

        Raises:
            DataValidationError: If CDS spread is negative
        """
        if cds_spread < 0:
            raise DataValidationError(
                "CDS spread must be non-negative",
                field_name='cds_spread'
            )

        recovery_rate = self._validate_probability(recovery_rate, 'recovery_rate')

        if recovery_rate >= 1.0:
            raise DataValidationError(
                "Recovery rate must be less than 1",
                field_name='recovery_rate'
            )

        loss_given_default = 1 - recovery_rate
        hazard_rate = cds_spread / loss_given_default
        pd = 1 - np.exp(-hazard_rate * T)

        return self._create_result_dict(
            value=float(self._round_result(pd)),
            method='cds_implied_pd',
            parameters={
                'cds_spread': cds_spread,
                'recovery_rate': recovery_rate,
                'T': T,
                'implied_hazard_rate': float(self._round_result(hazard_rate))
            },
            metadata={
                'interpretation': f'Implied {T}-year default probability from CDS spread'
            }
        )

    def calculate_credit_exposure(self,
                                   mtm_distributions: List[np.ndarray]) -> Dict[str, Any]:
        """
        Calculate credit exposure metrics from MTM distributions.

        Computes Expected Exposure (EE), Potential Future Exposure (PFE)
        at 95% and 99% confidence levels, and Expected Positive Exposure (EPE).

        Args:
            mtm_distributions: List of numpy arrays, each representing the MTM
                               distribution at a time point

        Returns:
            Dictionary with EE, PFE, EPE

        Raises:
            DataValidationError: If input is empty
        """
        if not mtm_distributions or len(mtm_distributions) == 0:
            raise DataValidationError(
                "MTM distributions list cannot be empty",
                field_name='mtm_distributions'
            )

        n_points = len(mtm_distributions)
        ee_list = []
        pfe_95_list = []
        pfe_99_list = []

        for mtm in mtm_distributions:
            mtm_arr = np.array(mtm)
            # EE = mean of positive exposures
            ee = np.mean(np.maximum(mtm_arr, 0))
            ee_list.append(ee)

            # PFE at 95% and 99%
            pfe_95 = np.percentile(mtm_arr, 95)
            pfe_99 = np.percentile(mtm_arr, 99)
            pfe_95_list.append(pfe_95)
            pfe_99_list.append(pfe_99)

        # EPE = time-averaged EE
        epe = np.mean(ee_list)

        return self._create_result_dict(
            value={
                'expected_exposure': [float(self._round_result(e)) for e in ee_list],
                'pfe_95': [float(self._round_result(p)) for p in pfe_95_list],
                'pfe_99': [float(self._round_result(p)) for p in pfe_99_list],
                'expected_positive_exposure': float(self._round_result(epe)),
                'max_pfe_95': float(self._round_result(max(pfe_95_list))),
                'max_pfe_99': float(self._round_result(max(pfe_99_list))),
            },
            method='credit_exposure',
            parameters={
                'n_time_points': n_points,
                'confidence_levels': [0.95, 0.99]
            },
            metadata={
                'interpretation': 'Credit exposure metrics: EE, PFE at 95/99%, EPE'
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Return list of supported XVA methods."""
        return ['cva', 'dva', 'bilateral_cva', 'fva']
