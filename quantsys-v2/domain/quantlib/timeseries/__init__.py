"""
Time Series Modeling Module
============================

Comprehensive time series analysis and modeling tools for QuantSys V2.
Migrated and extended from FinceptTerminal.

Modules:
    - arima: ARIMA/SARIMAX modeling and forecasting
    - garch: GARCH volatility modeling
    - cointegration: Cointegration testing and pairs trading
    - causality: Granger causality testing
    - kalman: Kalman filtering and state space models

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

# ARIMA models
from domain.quantlib.timeseries.arima import ARIMACalculator

# GARCH models
from domain.quantlib.timeseries.garch import GARCHCalculator

# Cointegration
from domain.quantlib.timeseries.cointegration import CointegrationCalculator

# Granger causality
from domain.quantlib.timeseries.causality import GrangerCausalityCalculator

# Kalman filter
from domain.quantlib.timeseries.kalman import KalmanFilterCalculator

# Legacy TimeSeriesAnalyzer (from original quant)
from domain.quantlib.timeseries.analyzer import TimeSeriesAnalyzer


__all__ = [
    'ARIMACalculator',
    'GARCHCalculator',
    'CointegrationCalculator',
    'GrangerCausalityCalculator',
    'KalmanFilterCalculator',
    'TimeSeriesAnalyzer',
]


# Version info
__version__ = '2.0.0'
__author__ = 'QuantSys V2 Team'
__description__ = 'Time series modeling and analysis tools'
