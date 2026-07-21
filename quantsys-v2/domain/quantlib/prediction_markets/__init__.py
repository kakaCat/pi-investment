"""
Prediction Markets Quant Module
===============================

Quantitative analysis tools for prediction markets (Polymarket, Kalshi).
Includes probability extraction, sentiment analysis, arbitrage detection,
and time series analysis.

Modules:
    - probability: Implied probability calculation from market prices
    - sentiment: Sentiment signal generation from probability series
    - arbitrage: Cross-platform and multi-outcome arbitrage detection
    - time_series: Probability time series analysis and forecasting

Usage:
    from domain.quantlib.prediction_markets import (
        ProbabilityCalculator,
        SentimentCalculator,
        PMArbitrageCalculator,
        PMTimeSeriesCalculator,
    )
"""

from .probability import ProbabilityCalculator
from .sentiment import SentimentCalculator
from .arbitrage import PMArbitrageCalculator
from .time_series import PMTimeSeriesCalculator

__all__ = [
    "ProbabilityCalculator",
    "SentimentCalculator",
    "PMArbitrageCalculator",
    "PMTimeSeriesCalculator",
]
