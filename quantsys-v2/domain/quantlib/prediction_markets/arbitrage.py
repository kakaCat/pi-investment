"""
Arbitrage Calculator for Prediction Markets
===========================================

Detects arbitrage opportunities across prediction markets.
Supports cross-platform, complementary outcome, and multi-outcome
(Dutch book) arbitrage detection.

Methods:
    - cross_platform: Same event, different platforms
    - complementary: Sum of all outcomes < 1.0
    - multi_outcome: Dutch book detection
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError


class PMArbitrageCalculator(BaseCalculator):
    """Detect arbitrage opportunities in prediction markets.

    Identifies mispricing across platforms and outcomes that create
    risk-free profit opportunities.

    Example:
        calc = PMArbitrageCalculator()
        result = calc.calculate(
            market_prices={
                "polymarket": {"Yes": (0.55, 0.57), "No": (0.43, 0.45)},
                "kalshi": {"Yes": (0.52, 0.54), "No": (0.46, 0.48)}
            },
            method="cross_platform",
            transaction_cost=0.02
        )
    """

    def __init__(self, precision: int = 6):
        """Initialize arbitrage calculator.

        Args:
            precision: Number of decimal places (default 6)
        """
        super().__init__(precision=precision)

    def get_supported_methods(self) -> List[str]:
        """Get supported calculation methods."""
        return ["cross_platform", "complementary", "multi_outcome"]

    def calculate(
        self,
        market_prices: Dict[str, Any],
        method: str = "cross_platform",
        transaction_cost: float = 0.02
    ) -> Dict[str, Any]:
        """Detect arbitrage opportunities.

        Args:
            market_prices: Market price data appropriate for the method:
                - cross_platform: {platform: {outcome: (bid, ask)}}
                - complementary: {outcome: (bid, ask)} for single platform
                - multi_outcome: [(outcome_name, bid, ask), ...]
            method: 'cross_platform', 'complementary', or 'multi_outcome'
            transaction_cost: Transaction cost as decimal (default 0.02 = 2%)

        Returns:
            Standardized result dictionary with arbitrage opportunities

        Raises:
            DataValidationError: If inputs are invalid
            CalculationError: If calculation fails
        """
        self.validate_method(method)
        self._validate_numeric_input(transaction_cost, "transaction_cost")

        try:
            if method == "cross_platform":
                result = self._cross_platform_arbitrage(market_prices, transaction_cost)
            elif method == "complementary":
                result = self._complementary_arbitrage(market_prices, transaction_cost)
            elif method == "multi_outcome":
                result = self._multi_outcome_arbitrage(market_prices, transaction_cost)
            else:
                raise DataValidationError(
                    f"Unknown method: {method}",
                    field_name="method"
                )

            return self._create_result_dict(
                value=result.get("total_profit", 0.0),
                method=method,
                parameters={
                    "method": method,
                    "transaction_cost": transaction_cost
                },
                metadata=result
            )
        except (DataValidationError, CalculationError):
            raise
        except Exception as e:
            raise CalculationError(
                str(e),
                calculation_type="arbitrage"
            )

    def _cross_platform_arbitrage(
        self,
        prices: Dict[str, Dict[str, Tuple[float, float]]],
        tx_cost: float
    ) -> Dict[str, Any]:
        """Find same-event price differences across platforms.

        For each outcome, find the platform with the lowest ask and
        highest bid. If the highest bid on one platform exceeds the
        lowest ask on another by more than transaction costs,
        there is an arbitrage opportunity.

        Args:
            prices: {platform_name: {outcome: (bid, ask)}}
            tx_cost: Transaction cost as decimal

        Returns:
            Dictionary with arbitrage opportunities
        """
        platforms = list(prices.keys())
        if len(platforms) < 2:
            return {
                "opportunities": [],
                "total_profit": 0.0,
                "num_opportunities": 0,
                "insufficient_platforms": True,
            }

        # Collect all outcomes
        all_outcomes: set = set()
        for platform_data in prices.values():
            all_outcomes.update(platform_data.keys())

        if not all_outcomes:
            all_outcomes = {"default"}

        opportunities = []
        total_profit = 0.0

        for outcome in all_outcomes:
            best_bid = -1.0
            best_bid_platform = ""
            best_ask = 2.0
            best_ask_platform = ""

            for platform, outcomes in prices.items():
                if outcome not in outcomes:
                    continue
                bid, ask = outcomes[outcome]

                if bid > best_bid:
                    best_bid = bid
                    best_bid_platform = platform

                if ask < best_ask:
                    best_ask = ask
                    best_ask_platform = platform

            # Calculate profit: buy at lowest ask, sell at highest bid
            if best_bid > best_ask and best_bid_platform != best_ask_platform:
                raw_profit = best_bid - best_ask
                cost = best_ask * tx_cost + best_bid * tx_cost  # Cost on both sides
                net_profit = raw_profit - cost

                if net_profit > 0:
                    opportunity = {
                        "outcome": outcome,
                        "action": f"Buy on {best_ask_platform} at {self._round_result(best_ask)}, "
                                   f"Sell on {best_bid_platform} at {self._round_result(best_bid)}",
                        "raw_profit": self._round_result(raw_profit),
                        "transaction_cost": self._round_result(cost),
                        "net_profit": self._round_result(net_profit),
                        "return_pct": self._round_result(
                            (net_profit / best_ask * 100) if best_ask > 0 else 0.0
                        ),
                    }
                    opportunities.append(opportunity)
                    total_profit += net_profit

        # Sort by net profit descending
        opportunities.sort(key=lambda x: x["net_profit"], reverse=True)

        return {
            "opportunities": opportunities,
            "num_opportunities": len(opportunities),
            "total_profit": self._round_result(total_profit),
            "platforms_analyzed": platforms,
        }

    def _complementary_arbitrage(
        self,
        prices_by_outcome: Dict[str, Tuple[float, float]],
        tx_cost: float
    ) -> Dict[str, Any]:
        """Detect arbitrage when sum of all outcome asks < 1.0.

        If you can buy ALL outcomes for less than $1.00, you have
        a risk-free profit equal to ($1.00 - total_cost).

        For binary markets, checks if YES_ask + NO_ask < 1.0.

        Args:
            prices_by_outcome: {outcome_name: (bid, ask)}
            tx_cost: Transaction cost as decimal

        Returns:
            Dictionary with complementary arbitrage analysis
        """
        if not prices_by_outcome:
            raise DataValidationError(
                "prices_by_outcome cannot be empty",
                field_name="prices_by_outcome"
            )

        # Calculate total cost to buy all outcomes (paying ask)
        total_ask = 0.0
        total_ask_with_cost = 0.0
        outcomes_detail = []

        for outcome_name, (bid, ask) in prices_by_outcome.items():
            self._validate_numeric_input(bid, f"{outcome_name}.bid")
            self._validate_numeric_input(ask, f"{outcome_name}.ask")
            bid = float(bid)
            ask = float(ask)
            cost_with_fee = ask * (1 + tx_cost)
            total_ask += ask
            total_ask_with_cost += cost_with_fee
            outcomes_detail.append({
                "outcome": outcome_name,
                "ask": self._round_result(ask),
                "ask_with_fee": self._round_result(cost_with_fee),
            })

        # Also check selling all outcomes (receiving bid)
        total_bid = sum(float(bid) for bid, _ in prices_by_outcome.values())
        total_bid_after_cost = total_bid * (1 - tx_cost)

        # Buy all outcomes: profit if sum of asks < 1.0
        raw_profit_buy_all = 1.0 - total_ask
        net_profit_buy_all = 1.0 - total_ask_with_cost

        # Sell all outcomes: profit if sum of bids > 1.0
        raw_profit_sell_all = total_bid - 1.0
        net_profit_sell_all = total_bid_after_cost - 1.0

        is_arbitrage_buy = net_profit_buy_all > 0
        is_arbitrage_sell = net_profit_sell_all > 0
        is_arbitrage = is_arbitrage_buy or is_arbitrage_sell

        return {
            "is_arbitrage": is_arbitrage,
            "is_arbitrage_buy_all": is_arbitrage_buy,
            "is_arbitrage_sell_all": is_arbitrage_sell,
            "total_ask": self._round_result(total_ask),
            "total_ask_with_cost": self._round_result(total_ask_with_cost),
            "total_bid": self._round_result(total_bid),
            "total_bid_after_cost": self._round_result(total_bid_after_cost),
            "net_profit_buy_all": self._round_result(net_profit_buy_all),
            "net_profit_sell_all": self._round_result(net_profit_sell_all),
            "outcomes_detail": outcomes_detail,
        }

    def _multi_outcome_arbitrage(
        self,
        markets: List[Tuple[str, float, float]],
        tx_cost: float
    ) -> Dict[str, Any]:
        """Dutch book detection across multiple outcomes.

        A Dutch book exists when you can place a set of bets across
        all outcomes that guarantees a profit regardless of the result.
        This typically means sum of implied probabilities < 1.0.

        Args:
            markets: List of (outcome_name, bid, ask) tuples
            tx_cost: Transaction cost as decimal

        Returns:
            Dictionary with Dutch book analysis
        """
        if not markets:
            raise DataValidationError(
                "markets cannot be empty",
                field_name="markets"
            )

        outcomes = []
        total_ask = 0.0
        total_ask_adj = 0.0
        implied_probs = {}

        for name, bid, ask in markets:
            self._validate_numeric_input(bid, f"{name}.bid")
            self._validate_numeric_input(ask, f"{name}.ask")
            bid = float(bid)
            ask = float(ask)

            midpoint = (bid + ask) / 2.0
            implied_probs[name] = midpoint
            total_ask += ask
            total_ask_adj += ask * (1 + tx_cost)

            outcomes.append({
                "outcome": name,
                "bid": self._round_result(bid),
                "ask": self._round_result(ask),
                "midpoint": self._round_result(midpoint),
            })

        # Normalize implied probabilities
        total_implied = sum(implied_probs.values())
        if total_implied > 0:
            normalized = {k: v / total_implied for k, v in implied_probs.items()}
            probabilities_sum_to_1 = self._round_result(float(sum(normalized.values())))
        else:
            normalized = implied_probs
            probabilities_sum_to_1 = 0.0

        # Dutch book: total_ask < 1.0 means guaranteed profit
        is_dutch_book = total_ask_adj < 1.0
        guaranteed_return = 0.0
        if is_dutch_book:
            guaranteed_return = (1.0 - total_ask_adj) / total_ask_adj

        # Check individual vs basket
        # Market efficiency: sum of midpoints should be ~1.0
        efficiency_gap = abs(total_implied - 1.0)

        return {
            "is_dutch_book": is_dutch_book,
            "num_outcomes": len(markets),
            "total_ask": self._round_result(total_ask),
            "total_ask_adj": self._round_result(total_ask_adj),
            "implied_probabilities": {
                k: self._round_result(v) for k, v in normalized.items()
            },
            "normalized_probabilities_sum": probabilities_sum_to_1,
            "efficiency_gap": self._round_result(efficiency_gap),
            "guaranteed_return_pct": self._round_result(guaranteed_return * 100),
            "outcomes": outcomes,
            "market_efficiency": "efficient" if efficiency_gap < 0.05 else "inefficient",
        }
