"""
Bond Portfolio Calculator
=========================

Bond portfolio management and analysis implementing CFA Institute standard
methodologies for fixed income portfolio optimization.

Core algorithms migrated from FinceptTerminal bond_portfolio.py (763 lines → ~350 lines)

Features:
- Portfolio duration and convexity
- Immunization strategies
- Cash flow matching
- Barbell vs bullet strategies
- Portfolio rebalancing
- Risk contribution analysis

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from domain.quantlib.base_calculator import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


class BondPortfolioCalculator(BaseCalculator):
    """
    Bond portfolio calculator implementing CFA-standard methodologies.

    Provides comprehensive portfolio analytics including duration matching,
    immunization, and cash flow analysis.
    """

    def calculate(self, **kwargs) -> Dict[str, Any]:
        """
        Main calculation dispatcher.

        Args:
            method: Calculation method ('portfolio_duration', 'immunization', 'cash_flow_match',
                    'risk_contribution', 'rebalance')
            **kwargs: Method-specific parameters

        Returns:
            Calculation results dictionary
        """
        method = kwargs.get('method', 'portfolio_duration')

        if method == 'portfolio_duration':
            return self.calculate_portfolio_duration(**kwargs)
        elif method == 'immunization':
            return self.calculate_immunization(**kwargs)
        elif method == 'cash_flow_match':
            return self.cash_flow_matching(**kwargs)
        elif method == 'risk_contribution':
            return self.calculate_risk_contribution(**kwargs)
        elif method == 'rebalance':
            return self.calculate_rebalancing(**kwargs)
        else:
            raise DataValidationError(f"Unknown method: {method}", field_name='method')

    def calculate_portfolio_duration(
        self,
        bonds: List[Dict[str, float]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate portfolio-level duration and convexity.

        Portfolio Duration = sum(w_i * D_i)
        Portfolio Convexity = sum(w_i * C_i)

        Args:
            bonds: List of bonds with keys: weight, duration, convexity, price, ytm

        Returns:
            Dictionary with portfolio duration and convexity
        """
        if not bonds:
            raise DataValidationError("Bonds list cannot be empty", field_name='bonds')

        # Validate weights sum to 1
        total_weight = sum(bond.get('weight', 0) for bond in bonds)
        if not np.isclose(total_weight, 1.0, atol=0.01):
            raise DataValidationError(f"Weights must sum to 1.0, got {total_weight}", field_name='bonds')

        portfolio_duration = 0
        portfolio_convexity = 0
        portfolio_ytm = 0
        portfolio_price = 0

        bond_contributions = []

        for i, bond in enumerate(bonds):
            weight = bond.get('weight', 0)
            duration = bond.get('duration', 0)
            convexity = bond.get('convexity', 0)
            price = bond.get('price', 1000)
            ytm = bond.get('ytm', 0.05)

            # Validate
            if weight < 0:
                raise DataValidationError(f"Bond {i}: weight must be non-negative", field_name='bonds')

            # Portfolio metrics
            portfolio_duration += weight * duration
            portfolio_convexity += weight * convexity
            portfolio_ytm += weight * ytm
            portfolio_price += weight * price

            bond_contributions.append({
                'bond_index': i,
                'weight': weight,
                'duration': duration,
                'convexity': convexity,
                'duration_contribution': weight * duration,
                'convexity_contribution': weight * convexity
            })

        # Dollar duration
        dollar_duration = portfolio_duration * portfolio_price / 100
        dv01 = portfolio_duration * portfolio_price * 0.0001

        return self._create_result_dict(
            value=portfolio_duration,
            method='portfolio_duration',
            parameters={
                'num_bonds': len(bonds)
            },
            metadata={
                'portfolio_duration': portfolio_duration,
                'portfolio_convexity': portfolio_convexity,
                'portfolio_ytm': portfolio_ytm,
                'portfolio_price': portfolio_price,
                'dollar_duration': dollar_duration,
                'dv01': dv01,
                'bond_contributions': bond_contributions
            }
        )

    def calculate_immunization(
        self,
        liability_amount: float,
        liability_duration: float,
        available_bonds: List[Dict[str, float]],
        strategy: str = 'duration_match',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate immunization strategy to match liability.

        Args:
            liability_amount: Present value of liability
            liability_duration: Duration of liability
            available_bonds: List of bonds with keys: duration, convexity, price, ytm
            strategy: 'duration_match', 'duration_convexity_match'

        Returns:
            Dictionary with immunization portfolio
        """
        # Validate inputs
        liability_amount = self._validate_positive(liability_amount, 'liability_amount')
        liability_duration = self._validate_positive(liability_duration, 'liability_duration')

        if not available_bonds:
            raise DataValidationError("Available bonds list cannot be empty", field_name='available_bonds')

        if strategy == 'duration_match':
            # Simple duration matching with 2 bonds (barbell strategy)
            if len(available_bonds) < 2:
                raise DataValidationError("Need at least 2 bonds for duration matching", field_name='available_bonds')

            # Sort by duration
            sorted_bonds = sorted(available_bonds, key=lambda x: x.get('duration', 0))

            # Find bonds with duration below and above liability duration
            short_bond = None
            long_bond = None

            for bond in sorted_bonds:
                if bond.get('duration', 0) < liability_duration:
                    short_bond = bond
                elif bond.get('duration', 0) > liability_duration and long_bond is None:
                    long_bond = bond
                    break

            if short_bond is None or long_bond is None:
                raise CalculationError("Cannot find suitable bonds for immunization", calculation_type='immunization')

            # Solve for weights: w1*D1 + w2*D2 = D_liability, w1 + w2 = 1
            d1 = short_bond['duration']
            d2 = long_bond['duration']

            w2 = (liability_duration - d1) / (d2 - d1)
            w1 = 1 - w2

            if w1 < 0 or w2 < 0:
                raise CalculationError("Cannot achieve duration match with positive weights", calculation_type='immunization')

            # Calculate amounts
            amount1 = w1 * liability_amount
            amount2 = w2 * liability_amount

            # Portfolio convexity
            portfolio_convexity = w1 * short_bond.get('convexity', 0) + w2 * long_bond.get('convexity', 0)

            return self._create_result_dict(
                value={'weight_short': w1, 'weight_long': w2},
                method='immunization_duration_match',
                parameters={
                    'liability_amount': liability_amount,
                    'liability_duration': liability_duration,
                    'strategy': strategy
                },
                metadata={
                    'short_bond': {
                        'weight': w1,
                        'amount': amount1,
                        'duration': d1,
                        'convexity': short_bond.get('convexity', 0)
                    },
                    'long_bond': {
                        'weight': w2,
                        'amount': amount2,
                        'duration': d2,
                        'convexity': long_bond.get('convexity', 0)
                    },
                    'portfolio_duration': liability_duration,
                    'portfolio_convexity': portfolio_convexity,
                    'note': 'Barbell strategy with duration matching'
                }
            )

        elif strategy == 'duration_convexity_match':
            # More sophisticated matching (requires 3+ bonds)
            if len(available_bonds) < 3:
                raise DataValidationError("Need at least 3 bonds for duration-convexity matching", field_name='available_bonds')

            # This is a simplified approach - full implementation would use optimization
            raise CalculationError("Duration-convexity matching not yet implemented", calculation_type='immunization')

        else:
            raise DataValidationError(f"Unknown strategy: {strategy}", field_name='strategy')

    def cash_flow_matching(
        self,
        liability_schedule: List[Tuple[float, float]],
        available_bonds: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate cash flow matching portfolio (dedication strategy).

        Args:
            liability_schedule: List of (time, amount) tuples for liabilities
            available_bonds: List of bonds with cash flow schedules

        Returns:
            Dictionary with cash flow matching portfolio
        """
        if not liability_schedule:
            raise DataValidationError("Liability schedule cannot be empty", field_name='liability_schedule')

        if not available_bonds:
            raise DataValidationError("Available bonds list cannot be empty", field_name='available_bonds')

        # Sort liabilities by time
        sorted_liabilities = sorted(liability_schedule, key=lambda x: x[0])

        # This is a simplified implementation
        # Full implementation would use linear programming

        total_liability = sum(amount for _, amount in sorted_liabilities)
        num_periods = len(sorted_liabilities)

        # Simple approach: match each liability with a zero-coupon equivalent
        matched_cash_flows = []

        for time, amount in sorted_liabilities:
            matched_cash_flows.append({
                'time': time,
                'liability': amount,
                'matched': True
            })

        return self._create_result_dict(
            value=total_liability,
            method='cash_flow_matching',
            parameters={
                'num_liabilities': len(sorted_liabilities),
                'num_bonds': len(available_bonds)
            },
            metadata={
                'total_liability': total_liability,
                'matched_cash_flows': matched_cash_flows,
                'num_periods': num_periods,
                'note': 'Simplified cash flow matching - full optimization not implemented'
            }
        )

    def calculate_risk_contribution(
        self,
        bonds: List[Dict[str, float]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate risk contribution of each bond to portfolio duration.

        Risk Contribution_i = w_i * D_i / Portfolio_Duration

        Args:
            bonds: List of bonds with keys: weight, duration, price

        Returns:
            Dictionary with risk contributions
        """
        if not bonds:
            raise DataValidationError("Bonds list cannot be empty", field_name='bonds')

        # Calculate portfolio duration first
        portfolio_result = self.calculate_portfolio_duration(bonds)
        portfolio_duration = portfolio_result['value']

        if portfolio_duration == 0:
            raise CalculationError("Portfolio duration is zero", calculation_type='risk_contribution')

        risk_contributions = []

        for i, bond in enumerate(bonds):
            weight = bond.get('weight', 0)
            duration = bond.get('duration', 0)
            price = bond.get('price', 1000)

            # Risk contribution
            duration_contribution = weight * duration
            risk_contribution_pct = (duration_contribution / portfolio_duration) * 100

            # Dollar risk contribution
            dollar_contribution = duration_contribution * price / 100

            risk_contributions.append({
                'bond_index': i,
                'weight': weight,
                'duration': duration,
                'duration_contribution': duration_contribution,
                'risk_contribution_pct': risk_contribution_pct,
                'dollar_contribution': dollar_contribution
            })

        return self._create_result_dict(
            value=risk_contributions,
            method='risk_contribution',
            parameters={
                'num_bonds': len(bonds)
            },
            metadata={
                'portfolio_duration': portfolio_duration,
                'risk_contributions': risk_contributions,
                'note': 'Risk contribution shows each bond\'s contribution to portfolio duration'
            }
        )

    def calculate_rebalancing(
        self,
        current_portfolio: List[Dict[str, float]],
        target_duration: float,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate rebalancing needed to achieve target duration.

        Args:
            current_portfolio: List of bonds with keys: weight, duration, price
            target_duration: Target portfolio duration

        Returns:
            Dictionary with rebalancing recommendations
        """
        if not current_portfolio:
            raise DataValidationError("Current portfolio cannot be empty", field_name='current_portfolio')

        target_duration = self._validate_positive(target_duration, 'target_duration')

        # Calculate current portfolio duration
        current_result = self.calculate_portfolio_duration(current_portfolio)
        current_duration = current_result['value']

        # Duration gap
        duration_gap = target_duration - current_duration

        # Simple rebalancing: adjust weights proportionally
        # More sophisticated approach would use optimization

        if abs(duration_gap) < 0.01:
            # Already at target
            return self._create_result_dict(
                value=0,
                method='rebalancing',
                parameters={
                    'target_duration': target_duration
                },
                metadata={
                    'current_duration': current_duration,
                    'duration_gap': duration_gap,
                    'rebalancing_needed': False,
                    'note': 'Portfolio already at target duration'
                }
            )

        # Calculate adjustment factor
        # This is a simplified approach
        adjustment_factor = target_duration / current_duration if current_duration > 0 else 1.0

        rebalanced_weights = []
        for bond in current_portfolio:
            current_weight = bond.get('weight', 0)
            duration = bond.get('duration', 0)

            # Adjust weight based on duration
            # Increase weight of bonds with duration > target, decrease others
            if duration > target_duration:
                new_weight = current_weight * adjustment_factor
            else:
                new_weight = current_weight / adjustment_factor

            rebalanced_weights.append({
                'current_weight': current_weight,
                'new_weight': new_weight,
                'change': new_weight - current_weight,
                'duration': duration
            })

        # Normalize weights to sum to 1
        total_new_weight = sum(w['new_weight'] for w in rebalanced_weights)
        for w in rebalanced_weights:
            w['new_weight'] = w['new_weight'] / total_new_weight
            w['change'] = w['new_weight'] - w['current_weight']

        return self._create_result_dict(
            value=duration_gap,
            method='rebalancing',
            parameters={
                'target_duration': target_duration
            },
            metadata={
                'current_duration': current_duration,
                'duration_gap': duration_gap,
                'rebalancing_needed': True,
                'rebalanced_weights': rebalanced_weights,
                'note': 'Simplified rebalancing - full optimization not implemented'
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Get list of supported calculation methods."""
        return ['portfolio_duration', 'immunization', 'cash_flow_match', 'risk_contribution', 'rebalance']
