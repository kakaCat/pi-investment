"""
Reversal Factor Calculators
============================

Short-term price reversal factors based on academic research.

References:
- Jegadeesh (1990): Evidence of Predictable Behavior of Security Returns
- Lou et al. (2019): Overnight Returns and Firm-Specific Investor Sentiment
"""

import numpy as np
from typing import Dict, Any, List

from domain.quantlib.factors.base import TechnicalFactorCalculator
from infrastructure.quantlib.core.base_calculator import validate_inputs, timing_decorator


class ReversalFactors(TechnicalFactorCalculator):
    """
    Short-term reversal factor calculator.

    Provides three reversal indicators:
    - reversal_1d: 1-day reversal (yesterday's return × -1)
    - reversal_5d: 5-day reversal (past 5-day return × -1)
    - overnight_return: Overnight return ((today_open - yesterday_close) / yesterday_close)
    """

    def get_supported_methods(self) -> List[str]:
        """Return list of supported reversal indicators."""
        return ['reversal_1d', 'reversal_5d', 'overnight_return']

    # =========================================================================
    # 1-Day Reversal
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def reversal_1d(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate 1-day reversal factor.

        Formula: reversal_1d = -(close[t] - close[t-1]) / close[t-1]

        Interpretation:
        - Positive value: Yesterday fell, expect bounce today (buy signal)
        - Negative value: Yesterday rose, expect pullback today (sell signal)

        Args:
            klines: K-line data

        Returns:
            Dictionary with reversal value and metadata
        """
        closes = self._extract_closes(klines)

        if len(closes) < 2:
            return self._create_result_dict(
                value=None,
                method='reversal_1d',
                parameters={'lookback': 1},
                metadata={'error': 'Insufficient data (need at least 2 days)'}
            )

        # Yesterday's return
        yesterday_return = (closes[-1] - closes[-2]) / closes[-2]

        # Reversal factor = negative of yesterday's return
        reversal = float(-yesterday_return)

        # Determine signal strength
        signal = 'neutral'
        if reversal > 0.02:  # Yesterday fell > 2%, expect bounce
            signal = 'buy'
        elif reversal < -0.02:  # Yesterday rose > 2%, expect pullback
            signal = 'sell'

        return self._create_result_dict(
            value=reversal,
            method='reversal_1d',
            parameters={'lookback': 1},
            metadata={
                'yesterday_return': float(yesterday_return),
                'signal': signal,
                'yesterday_close': float(closes[-2]),
                'today_close': float(closes[-1])
            }
        )

    # =========================================================================
    # 5-Day Reversal
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def reversal_5d(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate 5-day reversal factor.

        Formula: reversal_5d = -(close[t] - close[t-5]) / close[t-5]

        Captures weekly reversal patterns (weekend effect, behavioral biases).

        Args:
            klines: K-line data

        Returns:
            Dictionary with reversal value and metadata
        """
        closes = self._extract_closes(klines)

        if len(closes) < 6:
            return self._create_result_dict(
                value=None,
                method='reversal_5d',
                parameters={'lookback': 5},
                metadata={'error': 'Insufficient data (need at least 6 days)'}
            )

        # Past 5-day return
        ret_5d = (closes[-1] - closes[-6]) / closes[-6]

        # Reversal factor = negative of 5-day return
        reversal = float(-ret_5d)

        return self._create_result_dict(
            value=reversal,
            method='reversal_5d',
            parameters={'lookback': 5},
            metadata={
                '5d_return': float(ret_5d),
                'price_5d_ago': float(closes[-6]),
                'current_price': float(closes[-1])
            }
        )

    # =========================================================================
    # Overnight Return
    # =========================================================================

    @validate_inputs
    @timing_decorator
    def overnight_return(self, klines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate overnight return.

        Formula: overnight_return = (open[t] - close[t-1]) / close[t-1]

        Academic finding: Overnight returns predict future intraday returns.
        Positive overnight return → potential intraday reversal.

        Reference: Lou et al. (2019) - Overnight Returns and Firm-Specific Investor Sentiment

        Args:
            klines: K-line data

        Returns:
            Dictionary with overnight return and metadata
        """
        if len(klines) < 2:
            return self._create_result_dict(
                value=None,
                method='overnight_return',
                parameters={},
                metadata={'error': 'Insufficient data (need at least 2 days)'}
            )

        today = klines[-1]
        yesterday = klines[-2]

        today_open = float(today.get('open', 0))
        yesterday_close = float(yesterday.get('close', 0))

        if yesterday_close == 0:
            return self._create_result_dict(
                value=None,
                method='overnight_return',
                parameters={},
                metadata={'error': 'Invalid yesterday close price (zero)'}
            )

        # Overnight return
        overnight_ret = (today_open - yesterday_close) / yesterday_close

        return self._create_result_dict(
            value=float(overnight_ret),
            method='overnight_return',
            parameters={},
            metadata={
                'today_open': today_open,
                'yesterday_close': yesterday_close,
                'gap_pct': float(overnight_ret * 100)  # percentage gap
            }
        )
