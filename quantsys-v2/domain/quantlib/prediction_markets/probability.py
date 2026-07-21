"""
Probability Calculator for Prediction Markets
=============================================

Extracts implied probabilities from prediction market prices.
Supports multiple methods for binary and multi-outcome markets.

Methods:
    - midpoint: (bid + ask) / 2
    - last_price: Last traded price
    - bid_ask_adjusted: Spread-adjusted probability
"""

import numpy as np
from typing import Dict, List, Any, Optional, Union

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import CalculationError, DataValidationError


class ProbabilityCalculator(BaseCalculator):
    """Calculate implied probabilities from prediction market prices.

    Extracts and normalizes probabilities from raw market data.
    Supports binary markets, multi-outcome events, and confidence
    interval calculation using Wilson score intervals.

    Example:
        calc = ProbabilityCalculator()
        result = calc.calculate(
            prices={"Yes": 0.62, "No": 0.40},
            method="midpoint",
            bid=0.60, ask=0.64
        )
    """

    def __init__(self, precision: int = 6):
        """Initialize probability calculator.

        Args:
            precision: Number of decimal places (default 6)
        """
        super().__init__(precision=precision)

    def get_supported_methods(self) -> List[str]:
        """Get supported calculation methods."""
        return ["midpoint", "last_price", "bid_ask_adjusted"]

    def calculate(
        self,
        prices: Union[Dict[str, float], float],
        method: str = "midpoint",
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        last: Optional[float] = None
    ) -> Dict[str, Any]:
        """Calculate implied probability from market prices.

        Args:
            prices: Dict of {outcome: price} for multi-outcome, or float for binary
            method: 'midpoint', 'last_price', or 'bid_ask_adjusted'
            bid: Bid price (required for 'midpoint' and 'bid_ask_adjusted')
            ask: Ask price (required for 'midpoint' and 'bid_ask_adjusted')
            last: Last traded price (required for 'last_price')

        Returns:
            Standardized result dictionary with probability values

        Raises:
            DataValidationError: If inputs are invalid
            CalculationError: If calculation fails
        """
        self.validate_method(method)

        try:
            if method == "midpoint":
                if bid is None or ask is None:
                    raise DataValidationError(
                        "Bid and ask prices are required for midpoint method",
                        field_name="bid/ask"
                    )
                result = self._midpoint_probability(bid, ask)
            elif method == "last_price":
                if last is None:
                    # Try to infer from prices dict or float
                    if isinstance(prices, dict):
                        last = float(np.mean(list(prices.values())))
                    else:
                        last = float(prices)
                result = self._last_price_probability(last)
            elif method == "bid_ask_adjusted":
                if bid is None or ask is None:
                    raise DataValidationError(
                        "Bid and ask prices are required for bid_ask_adjusted method",
                        field_name="bid/ask"
                    )
                result = self._bid_ask_adjusted(bid, ask)
            else:
                raise DataValidationError(
                    f"Unknown method: {method}",
                    field_name="method"
                )

            return self._create_result_dict(
                value=result.get("probability", 0.0),
                method=method,
                parameters={
                    "method": method,
                    "bid": bid,
                    "ask": ask,
                    "last": last
                },
                metadata=result
            )
        except (DataValidationError, CalculationError):
            raise
        except Exception as e:
            raise CalculationError(
                str(e),
                calculation_type="probability"
            )

    def _midpoint_probability(self, bid: float, ask: float) -> Dict[str, Any]:
        """Calculate probability using midpoint of bid-ask spread.

        P = (bid + ask) / 2

        Args:
            bid: Best bid price
            ask: Best ask price

        Returns:
            Dictionary with probability and spread information
        """
        self._validate_numeric_input(bid, "bid")
        self._validate_numeric_input(ask, "ask")

        midpoint = (bid + ask) / 2.0
        spread = ask - bid
        spread_pct = (spread / ask * 100) if ask > 0 else 0.0

        # Clamp to [0, 1]
        probability = max(0.0, min(1.0, midpoint))

        return {
            "probability": self._round_result(probability),
            "bid": self._round_result(bid),
            "ask": self._round_result(ask),
            "spread": self._round_result(spread),
            "spread_pct": self._round_result(spread_pct),
        }

    def _last_price_probability(self, last_price: Union[float, Dict[str, float]]) -> Dict[str, Any]:
        """Calculate probability using last traded price.

        For multi-outcome markets, normalizes to sum to 1.0.

        Args:
            last_price: Last traded price (float) or dict of outcome prices

        Returns:
            Dictionary with probability and last price information
        """
        if isinstance(last_price, dict):
            prices = {k: float(v) for k, v in last_price.items()}
            total = sum(prices.values())
            if total > 0:
                probabilities = {k: v / total for k, v in prices.items()}
            else:
                probabilities = prices
            return {
                "probability": self._round_result(probabilities),
                "last_prices": {k: self._round_result(float(v)) for k, v in last_price.items()},
                "raw_total": self._round_result(total) if isinstance(total, (int, float)) else total,
            }

        self._validate_numeric_input(last_price, "last_price")
        probability = max(0.0, min(1.0, float(last_price)))

        return {
            "probability": self._round_result(probability),
            "last_price": self._round_result(float(last_price)),
        }

    def _bid_ask_adjusted(self, bid: float, ask: float) -> Dict[str, Any]:
        """Calculate probability adjusted for bid-ask spread.

        Weights the midpoint by the spread tightness. Tighter spreads
        indicate higher confidence in the price.

        P = midpoint * (1 - spread_weight) where spread_weight increases
        with spread width, capping at 0.5 for very wide spreads.

        Args:
            bid: Best bid price
            ask: Best ask price

        Returns:
            Dictionary with adjusted probability
        """
        self._validate_numeric_input(bid, "bid")
        self._validate_numeric_input(ask, "ask")

        midpoint = (bid + ask) / 2.0

        if ask > 0:
            spread_ratio = (ask - bid) / ask
        else:
            spread_ratio = 0.0

        # Spread weight: 0 for zero spread, approaches 0.3 for wide spreads
        spread_weight = min(0.3, spread_ratio * 1.5)

        # Adjust: tighten toward 0.5 as spread increases (uncertainty)
        adjusted = midpoint * (1.0 - spread_weight) + 0.5 * spread_weight

        probability = max(0.0, min(1.0, adjusted))

        return {
            "probability": self._round_result(probability),
            "midpoint": self._round_result(midpoint),
            "bid": self._round_result(bid),
            "ask": self._round_result(ask),
            "spread_ratio": self._round_result(spread_ratio),
            "spread_weight": self._round_result(spread_weight),
            "confidence": self._round_result(1.0 - spread_weight),
        }

    def calculate_implied_distribution(
        self,
        outcomes: List[str],
        probabilities: List[float]
    ) -> Dict[str, Any]:
        """Normalize outcome probabilities to sum to 1.0.

        Useful for multi-outcome markets where raw prices may not
        sum to 1.0 due to market inefficiencies or bid-ask spreads.

        Args:
            outcomes: List of outcome labels
            probabilities: List of raw probability values

        Returns:
            Dictionary with normalized distribution and entropy
        """
        self._validate_numeric_input(np.array(probabilities), "probabilities")

        if len(outcomes) != len(probabilities):
            raise DataValidationError(
                f"Length mismatch: {len(outcomes)} outcomes vs {len(probabilities)} probabilities",
                field_name="outcomes/probabilities"
            )

        prob_array = np.array(probabilities, dtype=float)
        total = np.sum(prob_array)

        if total <= 0:
            raise DataValidationError(
                "Sum of probabilities must be positive",
                field_name="probabilities"
            )

        normalized = prob_array / total

        # Calculate entropy as measure of uncertainty
        entropy = 0.0
        for p in normalized:
            if p > 0:
                entropy -= p * np.log2(p)

        distribution = [
            {"outcome": outcomes[i], "probability": self._round_result(float(normalized[i]))}
            for i in range(len(outcomes))
        ]

        return {
            "distribution": distribution,
            "raw_total": self._round_result(float(total)),
            "normalized_total": self._round_result(float(np.sum(normalized))),
            "entropy_bits": self._round_result(float(entropy)),
            "num_outcomes": len(outcomes),
        }

    def calculate_confidence_interval(
        self,
        probability: float,
        sample_size: int,
        confidence: float = 0.95
    ) -> Dict[str, Any]:
        """Calculate Wilson score confidence interval for a probability.

        Wilson score interval is more accurate than the normal approximation
        for binomial proportions, especially near 0 or 1 and small samples.

        Args:
            probability: Observed probability (0 to 1)
            sample_size: Number of observations/trades
            confidence: Confidence level (default 0.95 for 95%)

        Returns:
            Dictionary with lower/upper bounds and margin of error

        Raises:
            DataValidationError: If inputs are invalid
        """
        self._validate_probability(probability, "probability")
        self._validate_positive(sample_size, "sample_size")
        self._validate_probability(confidence, "confidence")

        try:
            p = float(probability)
            n = int(sample_size)
            z_alpha = confidence

            # Wilson score interval
            # z for confidence level
            # For 95%: z ≈ 1.96, for 99%: z ≈ 2.576
            from math import sqrt

            if confidence == 0.95:
                z = 1.96
            elif confidence == 0.99:
                z = 2.576
            elif confidence == 0.90:
                z = 1.645
            elif confidence == 0.68:
                z = 1.0
            else:
                # Approximate z for arbitrary confidence
                from math import erfinv
                z = sqrt(2) * erfinv(confidence)

            denominator = 1 + z**2 / n
            centre_adjusted_probability = (p + z**2 / (2 * n)) / denominator
            adjusted_standard_deviation = sqrt(
                (p * (1 - p) / n + z**2 / (4 * n**2)) / denominator**2
            )
            if denominator**2 <= 0:
                raise CalculationError("Division by zero in Wilson interval", "confidence_interval")

            lower_bound = centre_adjusted_probability - z * adjusted_standard_deviation
            upper_bound = centre_adjusted_probability + z * adjusted_standard_deviation

            # Clamp to [0, 1]
            lower_bound = max(0.0, lower_bound)
            upper_bound = min(1.0, upper_bound)

            margin = upper_bound - centre_adjusted_probability

            return self._create_result_dict(
                value={
                    "lower": self._round_result(lower_bound),
                    "upper": self._round_result(upper_bound),
                    "center": self._round_result(centre_adjusted_probability),
                },
                method="wilson_score",
                parameters={
                    "probability": probability,
                    "sample_size": sample_size,
                    "confidence": confidence,
                    "z_score": self._round_result(z)
                },
                metadata={
                    "margin_of_error": self._round_result(margin),
                    "interval_width": self._round_result(upper_bound - lower_bound),
                }
            )
        except (DataValidationError, CalculationError):
            raise
        except Exception as e:
            raise CalculationError(
                str(e),
                calculation_type="confidence_interval"
            )
