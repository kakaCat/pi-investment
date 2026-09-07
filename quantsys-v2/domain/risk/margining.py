"""
Margin Calculator
==================

Margin calculation methods for derivatives and portfolios including:
- SPAN (Standard Portfolio Analysis of Risk) margin
- VaR-based margin
- Strategy-based margin (spreads, straddles, etc.)
- Maintenance margin and initial margin calculations

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple
from itertools import product
from scipy import stats

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    DataValidationError,
    InsufficientDataError,
    ConfigurationError,
)


class MarginCalculator(BaseCalculator):
    """
    Margin calculation engine supporting SPAN, VaR-based, and strategy-based methods.

    Computes required margin for portfolios of derivatives and securities
    using industry-standard methodologies.

    Methods:
        - span: SPAN margin using 16 standard scenarios
        - var_based: VaR-based margin calculation
        - strategy_based: Strategy-specific margin (spreads, combinations)

    Example:
        calculator = MarginCalculator(precision=2)
        positions = {'futures_long': 1, 'futures_short': -1}
        prices = {'futures_long': 4500, 'futures_short': 4500}
        vols = {'futures_long': 0.15, 'futures_short': 0.15}
        result = calculator.calculate(positions, prices, vols, method='span')
    """

    # SPAN default scenario arrays (price, volatility changes)
    SPAN_PRICE_SCENARIOS = [0, 1, -1, 1, -1, 0, 0, 1, -1, 1, -1, 0, 0, 1, -1, 1]
    SPAN_VOL_SCENARIOS =  [0, 0, 0,  1, 1,  1, -1, 1, 1, -1,-1, -1, 1, -1,-1, 1]

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize margin calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  positions: Dict[str, float],
                  prices: Dict[str, float],
                  volatility: Dict[str, float],
                  method: str = 'span',
                  confidence_level: float = 0.99) -> Dict[str, Any]:
        """
        Calculate margin requirements.

        Args:
            positions: {asset_id: quantity} - positive for long, negative for short
            prices: {asset_id: current_price}
            volatility: {asset_id: annualized_volatility}
            method: 'span', 'var_based', or 'strategy_based'
            confidence_level: Confidence level for VaR-based methods

        Returns:
            Dictionary with margin results

        Raises:
            DataValidationError: If positions/prices/vols are inconsistent
            ConfigurationError: If method is unsupported
            CalculationError: If computation fails
        """
        confidence_level = self._validate_probability(confidence_level, 'confidence_level')
        method = self.validate_method(method)

        # Validate consistent assets across positions, prices, vols
        pos_assets = set(positions.keys())
        price_assets = set(prices.keys())
        vol_assets = set(volatility.keys())

        if pos_assets != price_assets:
            missing_in_prices = pos_assets - price_assets
            missing_in_positions = price_assets - pos_assets
            if missing_in_prices:
                raise DataValidationError(
                    f"Assets in positions but missing prices: {missing_in_prices}",
                    field_name='prices'
                )
            if missing_in_positions:
                raise DataValidationError(
                    f"Assets in prices but missing positions: {missing_in_positions}",
                    field_name='positions'
                )

        if pos_assets != vol_assets:
            missing_in_vols = pos_assets - vol_assets
            if missing_in_vols:
                raise DataValidationError(
                    f"Assets missing volatility data: {missing_in_vols}",
                    field_name='volatility'
                )

        try:
            if method == 'span':
                result = self._span_margin(positions, prices, volatility)
            elif method == 'var_based':
                result = self._var_based_margin(positions, prices, volatility, confidence_level)
            elif method == 'strategy_based':
                result = self._strategy_based_margin(
                    'generic',
                    positions, prices
                )
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            return self._create_result_dict(
                value=result,
                method=f'margin_{method}',
                parameters={
                    'method': method,
                    'confidence_level': confidence_level,
                    'n_positions': len(positions),
                    'total_notional': float(sum(
                        abs(positions[a]) * prices[a] for a in positions
                    ))
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='Margin')

    def _span_margin(self,
                     positions: Dict[str, float],
                     prices: Dict[str, float],
                     vols: Dict[str, float],
                     price_scan_range: float = 0.05,
                     vol_scan_range: float = 0.01) -> Dict[str, Any]:
        """
        Calculate SPAN (Standard Portfolio Analysis of Risk) margin.

        SPAN uses 16 standard scenarios combining price and volatility changes
        to find the maximum potential loss for a portfolio.

        The 16 scenarios are:
        - Price unchanged, Vol unchanged      (scenario 1)
        - Price up 1/3 of PSR, Vol unchanged  (scenario 2)
        - Price down 1/3 of PSR, Vol unchanged(scenario 3)
        - Price up 2/3 of PSR, Vol unchanged  (scenario 4)
        - Price down 2/3 of PSR, Vol unchanged(scenario 5)
        - Price up 3/3 of PSR, Vol unchanged  (scenario 6)
        - Price down 3/3 of PSR, Vol unchanged(scenario 7)
        - Price unchanged, Vol up             (scenario 8)
        - Price unchanged, Vol down           (scenario 9)
        - Price up 1/3 of PSR, Vol up         (scenario 10)
        - Price down 1/3 of PSR, Vol up       (scenario 11)
        - Price up 1/3 of PSR, Vol down       (scenario 12)
        - Price down 1/3 of PSR, Vol down     (scenario 13)
        - Price up 2/3 of PSR, Vol up         (scenario 14)
        - Price down 2/3 of PSR, Vol down     (scenario 15)
        - Price up extreme move, Vol up       (scenario 16)

        Args:
            positions: Position quantities
            prices: Asset prices
            vols: Asset volatilities
            price_scan_range: Price scanning range (default: 5%)
            vol_scan_range: Volatility scanning range (default: 1%)

        Returns:
            Dictionary with SPAN margin results
        """
        assets = list(positions.keys())
        scenario_results = []

        for si in range(16):
            p_change_factor = self.SPAN_PRICE_SCENARIOS[si]
            v_change_factor = self.SPAN_VOL_SCENARIOS[si]

            scenario_loss = 0.0

            for asset in assets:
                qty = positions[asset]
                price = prices[asset]
                vol = vols[asset]

                # Price change: factor * price_scan_range applied progressively
                price_change_frac = p_change_factor * (price_scan_range / 3.0)
                new_price = price * (1 + price_change_frac)

                # Vol change
                vol_change = v_change_factor * vol_scan_range
                new_vol = vol + vol_change
                new_vol = max(new_vol, 0.001)  # Floor volatility

                # Position value change
                current_value = qty * price
                new_value = qty * new_price

                # Vol impact: first-order approximation
                # More volatility = larger potential loss for long positions
                vol_impact = qty * price * new_vol * np.sqrt(1.0 / 252.0) * v_change_factor

                # Total scenario loss for this position
                pos_pnl = new_value - current_value - vol_impact

                # Loss is negative PnL
                scenario_loss += -pos_pnl

            scenario_results.append(float(scenario_loss))

        # Scanning risk = max loss across scenarios
        scanning_risk = max(scenario_results)
        best_scenario = scenario_results.index(scanning_risk)

        # Inter-commodity spread credit (simplified)
        inter_commodity_spread_credit = 0.0
        if len(assets) >= 2:
            # Check for offsetting positions (long in one, short in another)
            has_long = any(positions[a] > 0 for a in assets)
            has_short = any(positions[a] < 0 for a in assets)
            if has_long and has_short:
                # Simple spread credit: 50% of the minimum absolute position value
                min_position_value = min(abs(positions[a]) * prices[a] for a in assets)
                inter_commodity_spread_credit = min_position_value * 0.5

        # Net SPAN margin
        net_span_margin = max(0.0, scanning_risk - inter_commodity_spread_credit)

        return {
            'scanning_risk': float(self._round_result(scanning_risk)),
            'inter_commodity_spread_credit': float(self._round_result(inter_commodity_spread_credit)),
            'net_span_margin': float(self._round_result(net_span_margin)),
            'best_scenario': best_scenario + 1,  # 1-indexed
            'scenario_results': [float(self._round_result(r)) for r in scenario_results],
            'n_scenarios': 16,
        }

    def _var_based_margin(self,
                           positions: Dict[str, float],
                           prices: Dict[str, float],
                           vols: Dict[str, float],
                           cl: float) -> Dict[str, Any]:
        """
        Calculate VaR-based margin requirement.

        Margin = z_alpha * sigma * position_value * sqrt(holding_period / 252)

        Standard holding periods:
        - 1 day for most positions
        - 2 days for options (using multiplier)

        Args:
            positions: Position quantities
            prices: Asset prices
            vols: Asset volatilities (annualized)
            cl: Confidence level

        Returns:
            Dictionary with VaR-based margin
        """
        assets = list(positions.keys())
        z_score = abs(stats.norm.ppf(1 - cl, loc=0, scale=1))

        margin_per_asset = {}
        total_margin = 0.0
        total_notional = 0.0

        for asset in assets:
            qty = positions[asset]
            price = prices[asset]
            vol = vols[asset]

            notional = abs(qty * price)
            total_notional += notional

            # Daily VaR
            daily_vol = vol / np.sqrt(252)
            daily_var = z_score * daily_vol * price

            # Margin for position
            margin = abs(qty) * daily_var
            margin_per_asset[asset] = float(self._round_result(margin))
            total_margin += margin

        return {
            'total_var_margin': float(self._round_result(total_margin)),
            'margin_per_asset': margin_per_asset,
            'total_notional': float(self._round_result(total_notional)),
            'margin_rate': float(self._round_result(total_margin / total_notional if total_notional > 0 else 0.0)),
            'z_score': float(self._round_result(z_score)),
        }

    def _strategy_based_margin(self,
                                strategy_type: str,
                                positions: Dict[str, float],
                                prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate strategy-based margin for specific strategy types.

        Supported strategies:
        - generic: Full margin on each leg
        - spread: Reduced margin for calendar/vertical spreads
        - straddle: Margin for straddle/strangle positions
        - butterfly: Margin for butterfly spreads
        - covered_call: Reduced margin for covered call

        Args:
            strategy_type: Type of strategy
            positions: Position quantities
            prices: Asset prices

        Returns:
            Dictionary with strategy-based margin
        """
        assets = list(positions.keys())
        total_notional = sum(abs(positions[a]) * prices[a] for a in assets)

        if strategy_type == 'generic':
            # Full margin on all positions
            margin = sum(abs(positions[a]) * prices[a] * 0.50 for a in assets)
            explanation = 'Full margin on each leg'

        elif strategy_type == 'spread':
            # Spread margin: margin on the larger leg only (or net)
            if len(assets) >= 2:
                values = [abs(positions[a]) * prices[a] for a in assets]
                margin = max(values) * 0.25  # Reduced rate for spreads
            else:
                margin = total_notional * 0.50
            explanation = 'Spread margin (reduced for hedged position)'

        elif strategy_type == 'straddle':
            # Straddle margin: margin on the larger leg + premium received
            if len(assets) >= 2:
                values = [abs(positions[a]) * prices[a] for a in assets]
                margin = max(values) * 0.30
            else:
                margin = total_notional * 0.50
            explanation = 'Straddle margin (max leg + premium)'

        elif strategy_type == 'butterfly':
            # Butterfly: very low margin due to capped risk
            if len(assets) >= 3:
                values = sorted([abs(positions[a]) * prices[a] for a in assets])
                # Margin is the max spread width
                margin = (values[2] - values[0]) * 0.10
            else:
                margin = total_notional * 0.50
            explanation = 'Butterfly margin (capped risk)'

        elif strategy_type == 'covered_call':
            # Covered call: reduced margin
            margin = total_notional * 0.25
            explanation = 'Covered call margin (reduced for covered position)'

        else:
            # Default to generic margin
            margin = total_notional * 0.50
            explanation = f'Generic margin (unknown strategy: {strategy_type})'

        return {
            'strategy_type': strategy_type,
            'margin': float(self._round_result(margin)),
            'total_notional': float(self._round_result(total_notional)),
            'margin_rate': float(self._round_result(margin / total_notional if total_notional > 0 else 0.0)),
            'explanation': explanation,
        }

    def calculate_maintenance_margin(self,
                                      positions: Dict[str, float],
                                      prices: Dict[str, float],
                                      margin_rate: float = 0.25) -> Dict[str, Any]:
        """
        Calculate maintenance margin requirement.

        Maintenance margin is the minimum equity required to maintain
        current positions, typically 25% of market value for equities.

        Args:
            positions: Position quantities
            prices: Asset prices
            margin_rate: Maintenance margin rate (default: 0.25)

        Returns:
            Dictionary with maintenance margin
        """
        margin_rate = self._validate_probability(margin_rate, 'margin_rate')

        total_value = 0.0
        margin_per_asset = {}

        for asset, qty in positions.items():
            if asset not in prices:
                raise DataValidationError(
                    f"Price not found for asset: {asset}",
                    field_name='prices'
                )
            price = prices[asset]
            position_value = abs(qty) * price
            total_value += position_value
            margin_per_asset[asset] = float(self._round_result(position_value * margin_rate))

        total_margin = total_value * margin_rate

        return self._create_result_dict(
            value={
                'maintenance_margin': float(self._round_result(total_margin)),
                'margin_rate': margin_rate,
                'total_position_value': float(self._round_result(total_value)),
                'margin_per_asset': margin_per_asset,
            },
            method='maintenance_margin',
            parameters={
                'margin_rate': margin_rate,
                'n_positions': len(positions)
            }
        )

    def calculate_initial_margin(self,
                                  positions: Dict[str, float],
                                  prices: Dict[str, float],
                                  margin_rate: float = 0.50) -> Dict[str, Any]:
        """
        Calculate initial margin requirement.

        Initial margin is the amount required to open new positions,
        typically 50% of market value for equities (Regulation T in US).

        Args:
            positions: Position quantities
            prices: Asset prices
            margin_rate: Initial margin rate (default: 0.50)

        Returns:
            Dictionary with initial margin
        """
        margin_rate = self._validate_probability(margin_rate, 'margin_rate')

        total_value = 0.0
        margin_per_asset = {}

        for asset, qty in positions.items():
            if asset not in prices:
                raise DataValidationError(
                    f"Price not found for asset: {asset}",
                    field_name='prices'
                )
            price = prices[asset]
            position_value = abs(qty) * price
            total_value += position_value
            margin_per_asset[asset] = float(self._round_result(position_value * margin_rate))

        total_margin = total_value * margin_rate

        return self._create_result_dict(
            value={
                'initial_margin': float(self._round_result(total_margin)),
                'margin_rate': margin_rate,
                'total_position_value': float(self._round_result(total_value)),
                'margin_per_asset': margin_per_asset,
            },
            method='initial_margin',
            parameters={
                'margin_rate': margin_rate,
                'n_positions': len(positions)
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Return list of supported margin calculation methods."""
        return ['span', 'var_based', 'strategy_based']

