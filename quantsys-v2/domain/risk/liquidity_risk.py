"""
Liquidity Risk Calculator
=========================

Calculates liquidity risk metrics including:
- Liquidity-adjusted VaR (LVaR)
- Bid-ask spread costs
- Market impact costs
- Liquidation cost estimation
- Liquidity score

Liquidity risk arises from the inability to trade assets quickly
without significant price impact.

Author: QuantSys V2 Advanced Risk Module
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError,
    ConfigurationError
)


class LiquidityRiskCalculator(BaseCalculator):
    """
    Liquidity Risk Calculator

    Calculates liquidity risk metrics and liquidity-adjusted VaR.

    Key Concepts:
        - Bid-Ask Spread: Cost of immediate execution
        - Market Impact: Price movement from large trades
        - Liquidation Horizon: Time needed to liquidate position
        - Liquidity VaR: VaR + Liquidation costs

    Market Impact Models:
        - Linear: Impact = α * (Volume / ADV)
        - Square Root: Impact = β * √(Volume / ADV)
        - Power Law: Impact = γ * (Volume / ADV)^δ

    Example:
        calculator = LiquidityRiskCalculator()
        result = calculator.calculate(
            portfolio={'stock_a': 1000000, 'stock_b': 500000},
            market_data={
                'stock_a': {'price': 100, 'adv': 5000000, 'spread': 0.001},
                'stock_b': {'price': 50, 'adv': 2000000, 'spread': 0.002}
            },
            liquidation_horizon=5,
            confidence_level=0.95
        )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Liquidity Risk calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  portfolio: Dict[str, float],
                  market_data: Dict[str, Dict[str, float]],
                  liquidation_horizon: int = 1,
                  confidence_level: float = 0.95,
                  impact_model: str = 'square_root') -> Dict[str, Any]:
        """
        Calculate liquidity risk metrics.

        Args:
            portfolio: Portfolio positions (asset -> position_value)
            market_data: Market data for each asset with keys:
                - price: Current price
                - adv: Average daily volume (in currency)
                - spread: Bid-ask spread (as fraction, e.g., 0.001 = 0.1%)
                - volatility: Optional daily volatility
            liquidation_horizon: Number of days to liquidate (default: 1)
            confidence_level: Confidence level for VaR
            impact_model: Market impact model ('linear', 'square_root', 'power')

        Returns:
            Dictionary with liquidity risk metrics

        Raises:
            DataValidationError: If portfolio or market data invalid
            ConfigurationError: If invalid parameters
        """
        # Validate inputs
        if not portfolio:
            raise DataValidationError("Portfolio cannot be empty")

        if not market_data:
            raise DataValidationError("Market data cannot be empty")

        # Check all portfolio assets have market data
        missing_assets = set(portfolio.keys()) - set(market_data.keys())
        if missing_assets:
            raise DataValidationError(
                f"Missing market data for assets: {missing_assets}"
            )

        # Validate liquidation horizon
        if liquidation_horizon < 1:
            raise ConfigurationError(
                "Liquidation horizon must be at least 1 day",
                parameter='liquidation_horizon'
            )

        confidence_level = self._validate_probability(confidence_level, 'confidence_level')

        try:
            # Calculate liquidity metrics for each asset
            asset_liquidity = {}
            total_bid_ask_cost = 0.0
            total_market_impact = 0.0

            for asset, position_value in portfolio.items():
                data = market_data[asset]

                # Validate market data
                required_fields = ['price', 'adv', 'spread']
                for field in required_fields:
                    if field not in data:
                        raise DataValidationError(
                            f"Missing '{field}' in market data for {asset}"
                        )

                # Calculate liquidity metrics
                metrics = self._calculate_asset_liquidity(
                    position_value=position_value,
                    price=data['price'],
                    adv=data['adv'],
                    spread=data['spread'],
                    volatility=data.get('volatility', 0.02),
                    liquidation_horizon=liquidation_horizon,
                    impact_model=impact_model
                )

                asset_liquidity[asset] = metrics
                total_bid_ask_cost += metrics['bid_ask_cost']
                total_market_impact += metrics['market_impact_cost']

            # Calculate total liquidation cost
            total_liquidation_cost = total_bid_ask_cost + total_market_impact

            # Calculate portfolio value
            portfolio_value = sum(portfolio.values())

            # Calculate liquidity-adjusted VaR
            # LVaR = VaR + Liquidation Cost
            # Simplified VaR calculation (can be enhanced with actual returns)
            avg_volatility = np.mean([
                market_data[asset].get('volatility', 0.02)
                for asset in portfolio.keys()
            ])

            # Standard VaR (parametric)
            from scipy.stats import norm
            z_score = norm.ppf(confidence_level)
            standard_var = portfolio_value * avg_volatility * z_score * np.sqrt(liquidation_horizon)

            # Liquidity-adjusted VaR
            liquidity_var = standard_var + total_liquidation_cost

            # Calculate liquidity score (0-100, higher is better)
            liquidity_score = self._calculate_liquidity_score(
                asset_liquidity,
                portfolio,
                portfolio_value
            )

            return self._create_result_dict(
                value={
                    'liquidity_var': float(liquidity_var),
                    'standard_var': float(standard_var),
                    'bid_ask_cost': float(total_bid_ask_cost),
                    'market_impact_cost': float(total_market_impact),
                    'total_liquidation_cost': float(total_liquidation_cost),
                    'liquidation_cost_percentage': float(total_liquidation_cost / portfolio_value * 100),
                    'liquidity_score': float(liquidity_score),
                    'asset_liquidity': asset_liquidity
                },
                method='liquidity_risk',
                parameters={
                    'liquidation_horizon': liquidation_horizon,
                    'confidence_level': confidence_level,
                    'impact_model': impact_model,
                    'n_assets': len(portfolio)
                },
                metadata={
                    'portfolio_value': float(portfolio_value),
                    'interpretation': 'Higher liquidity cost indicates less liquid portfolio'
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='Liquidity Risk')

    def _calculate_asset_liquidity(self,
                                   position_value: float,
                                   price: float,
                                   adv: float,
                                   spread: float,
                                   volatility: float,
                                   liquidation_horizon: int,
                                   impact_model: str) -> Dict[str, Any]:
        """
        Calculate liquidity metrics for a single asset.

        Args:
            position_value: Position value in currency
            price: Current price
            adv: Average daily volume (in currency)
            spread: Bid-ask spread (as fraction)
            volatility: Daily volatility
            liquidation_horizon: Liquidation horizon in days
            impact_model: Market impact model

        Returns:
            Dictionary with asset liquidity metrics
        """
        # Calculate position size in shares
        position_shares = position_value / price

        # Calculate daily trading volume needed
        daily_volume_needed = position_value / liquidation_horizon

        # Calculate volume participation rate
        participation_rate = daily_volume_needed / adv if adv > 0 else 1.0

        # Bid-ask spread cost
        # Cost = Position Value * Spread / 2 (assuming mid-price execution)
        bid_ask_cost = position_value * spread / 2

        # Market impact cost
        market_impact_cost = self._calculate_market_impact(
            position_value=position_value,
            adv=adv,
            volatility=volatility,
            liquidation_horizon=liquidation_horizon,
            model=impact_model
        )

        # Total liquidation cost
        total_cost = bid_ask_cost + market_impact_cost

        # Liquidity ratio (position size / ADV)
        liquidity_ratio = position_value / adv if adv > 0 else float('inf')

        # Assess liquidity level
        if liquidity_ratio < 0.01:
            liquidity_level = 'high'
        elif liquidity_ratio < 0.05:
            liquidity_level = 'medium'
        elif liquidity_ratio < 0.10:
            liquidity_level = 'low'
        else:
            liquidity_level = 'very_low'

        return {
            'position_value': float(position_value),
            'daily_volume_needed': float(daily_volume_needed),
            'participation_rate': float(participation_rate),
            'liquidity_ratio': float(liquidity_ratio),
            'bid_ask_cost': float(bid_ask_cost),
            'market_impact_cost': float(market_impact_cost),
            'total_liquidation_cost': float(total_cost),
            'cost_percentage': float(total_cost / position_value * 100),
            'liquidity_level': liquidity_level
        }

    def _calculate_market_impact(self,
                                 position_value: float,
                                 adv: float,
                                 volatility: float,
                                 liquidation_horizon: int,
                                 model: str) -> float:
        """
        Calculate market impact cost using specified model.

        Args:
            position_value: Position value
            adv: Average daily volume
            volatility: Daily volatility
            liquidation_horizon: Liquidation horizon
            model: Impact model ('linear', 'square_root', 'power')

        Returns:
            Market impact cost
        """
        if adv <= 0:
            return position_value * 0.10  # 10% impact for illiquid assets

        # Volume ratio
        volume_ratio = position_value / (adv * liquidation_horizon)

        if model == 'linear':
            # Linear model: Impact = α * (Volume / ADV)
            # α typically 0.1 to 0.5
            alpha = 0.3
            impact_fraction = alpha * volume_ratio

        elif model == 'square_root':
            # Square root model (Almgren-Chriss): Impact = β * σ * √(Volume / ADV)
            # β typically 0.5 to 1.0
            beta = 0.7
            impact_fraction = beta * volatility * np.sqrt(volume_ratio)

        elif model == 'power':
            # Power law model: Impact = γ * (Volume / ADV)^δ
            # γ typically 0.5, δ typically 0.6
            gamma = 0.5
            delta = 0.6
            impact_fraction = gamma * (volume_ratio ** delta)

        else:
            raise ConfigurationError(
                f"Unknown impact model: {model}",
                parameter='impact_model'
            )

        # Cap impact at 50% of position value
        impact_fraction = min(impact_fraction, 0.50)

        return position_value * impact_fraction

    def _calculate_liquidity_score(self,
                                   asset_liquidity: Dict[str, Dict[str, Any]],
                                   portfolio: Dict[str, float],
                                   portfolio_value: float) -> float:
        """
        Calculate overall portfolio liquidity score (0-100).

        Higher score = more liquid portfolio

        Args:
            asset_liquidity: Liquidity metrics by asset
            portfolio: Portfolio positions
            portfolio_value: Total portfolio value

        Returns:
            Liquidity score (0-100)
        """
        # Weight by position size
        weighted_score = 0.0

        for asset, position_value in portfolio.items():
            weight = position_value / portfolio_value
            metrics = asset_liquidity[asset]

            # Score components (each 0-100)
            # 1. Liquidity ratio score (lower is better)
            liquidity_ratio = metrics['liquidity_ratio']
            if liquidity_ratio < 0.01:
                ratio_score = 100
            elif liquidity_ratio < 0.05:
                ratio_score = 80
            elif liquidity_ratio < 0.10:
                ratio_score = 60
            elif liquidity_ratio < 0.25:
                ratio_score = 40
            else:
                ratio_score = 20

            # 2. Cost score (lower cost is better)
            cost_pct = metrics['cost_percentage']
            if cost_pct < 0.1:
                cost_score = 100
            elif cost_pct < 0.5:
                cost_score = 80
            elif cost_pct < 1.0:
                cost_score = 60
            elif cost_pct < 2.0:
                cost_score = 40
            else:
                cost_score = 20

            # 3. Participation rate score (lower is better)
            participation = metrics['participation_rate']
            if participation < 0.05:
                participation_score = 100
            elif participation < 0.10:
                participation_score = 80
            elif participation < 0.20:
                participation_score = 60
            elif participation < 0.30:
                participation_score = 40
            else:
                participation_score = 20

            # Combine scores (equal weights)
            asset_score = (ratio_score + cost_score + participation_score) / 3

            # Weight by position size
            weighted_score += weight * asset_score

        return weighted_score

    def estimate_optimal_liquidation_horizon(self,
                                            portfolio: Dict[str, float],
                                            market_data: Dict[str, Dict[str, float]],
                                            max_participation_rate: float = 0.10) -> Dict[str, Any]:
        """
        Estimate optimal liquidation horizon to keep participation rate below threshold.

        Args:
            portfolio: Portfolio positions
            market_data: Market data for each asset
            max_participation_rate: Maximum acceptable participation rate

        Returns:
            Dictionary with optimal horizon and analysis
        """
        # Validate inputs
        if not portfolio or not market_data:
            raise DataValidationError("Portfolio and market data required")

        max_participation_rate = self._validate_probability(
            max_participation_rate,
            'max_participation_rate'
        )

        # Calculate required horizon for each asset
        asset_horizons = {}

        for asset, position_value in portfolio.items():
            if asset not in market_data:
                continue

            adv = market_data[asset]['adv']

            # Required horizon: position_value / (max_participation_rate * ADV)
            required_horizon = position_value / (max_participation_rate * adv)
            required_horizon = max(1, int(np.ceil(required_horizon)))

            asset_horizons[asset] = {
                'position_value': float(position_value),
                'adv': float(adv),
                'required_horizon_days': int(required_horizon),
                'participation_rate': float(position_value / (required_horizon * adv))
            }

        # Overall optimal horizon (max across assets)
        optimal_horizon = max(h['required_horizon_days'] for h in asset_horizons.values())

        # Calculate costs at optimal horizon
        result = self.calculate(
            portfolio=portfolio,
            market_data=market_data,
            liquidation_horizon=optimal_horizon,
            confidence_level=0.95
        )

        return self._create_result_dict(
            value={
                'optimal_horizon_days': int(optimal_horizon),
                'asset_horizons': asset_horizons,
                'liquidation_costs': {
                    'total_cost': result['value']['total_liquidation_cost'],
                    'cost_percentage': result['value']['liquidation_cost_percentage']
                }
            },
            method='optimal_liquidation_horizon',
            parameters={
                'max_participation_rate': max_participation_rate,
                'n_assets': len(portfolio)
            },
            metadata={
                'interpretation': 'Minimum horizon to liquidate without excessive market impact'
            }
        )

    def compare_liquidation_strategies(self,
                                      portfolio: Dict[str, float],
                                      market_data: Dict[str, Dict[str, float]],
                                      horizons: List[int] = [1, 3, 5, 10, 20]) -> Dict[str, Any]:
        """
        Compare liquidation costs across different time horizons.

        Args:
            portfolio: Portfolio positions
            market_data: Market data
            horizons: List of liquidation horizons to compare

        Returns:
            Dictionary with comparison results
        """
        comparison_results = []

        for horizon in horizons:
            try:
                result = self.calculate(
                    portfolio=portfolio,
                    market_data=market_data,
                    liquidation_horizon=horizon,
                    confidence_level=0.95
                )

                comparison_results.append({
                    'horizon_days': horizon,
                    'total_cost': result['value']['total_liquidation_cost'],
                    'cost_percentage': result['value']['liquidation_cost_percentage'],
                    'bid_ask_cost': result['value']['bid_ask_cost'],
                    'market_impact_cost': result['value']['market_impact_cost'],
                    'liquidity_var': result['value']['liquidity_var']
                })

            except Exception as e:
                self.logger.warning(f"Failed to calculate for horizon {horizon}: {e}")
                continue

        # Find optimal horizon (minimum total cost)
        if comparison_results:
            optimal = min(comparison_results, key=lambda x: x['total_cost'])
            optimal_horizon = optimal['horizon_days']
        else:
            optimal_horizon = None

        return self._create_result_dict(
            value={
                'comparison': comparison_results,
                'optimal_horizon': optimal_horizon,
                'recommendation': f"Optimal liquidation horizon: {optimal_horizon} days" if optimal_horizon else "No valid results"
            },
            method='liquidation_strategy_comparison',
            parameters={
                'horizons_tested': horizons,
                'n_assets': len(portfolio)
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Return list of supported calculation methods."""
        return ['liquidity_risk', 'optimal_horizon', 'strategy_comparison']
