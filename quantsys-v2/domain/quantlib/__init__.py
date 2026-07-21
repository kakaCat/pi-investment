"""
QuantLib Suite - Quantitative Finance Library
==============================================

Professional quantitative finance calculations and analysis tools.

Modules:
    - base_calculator: Abstract base class for all calculators
    - data_validator: Data quality validation and reporting
    - rate_calculations: Interest rate and yield calculations
    - risk: Risk management and analysis (VaR, CVaR, drawdown, market risk, attribution, stress testing)
    - ml: Machine learning integration (feature engineering, factor mining, return prediction, risk prediction, anomaly detection)
    - rl: Reinforcement learning base infrastructure (BaseRLAgent, BaseRLEnvironment)
    - finrl: FinRL framework integration (FinRLAgent, StockTradingEnv, 5 algorithms)
    - qlib: Qlib RL framework integration (QlibRLAgent, QlibTradingEnv, 5 algorithms)
    - exceptions: Custom exceptions for QuantLib

Usage:
    from domain.quantlib import BaseCalculator, DataValidator
    from domain.quantlib.exceptions import CalculationError
    from domain.quantlib.risk import VaRCalculator, CVaRCalculator
    from domain.quantlib.ml import FeatureEngineeringCalculator, FactorMiningCalculator
    from domain.quantlib.rl import BaseRLAgent, BaseRLEnvironment
    from domain.quantlib.finrl import FinRLAgent, StockTradingEnv
    from domain.quantlib.qlib import QlibRLAgent, QlibTradingEnv
"""

from .base_calculator import (
    BaseCalculator,
    CalculatorFactory,
    CalculationResult,
    validate_inputs,
    cache_result,
    timing_decorator
)

from .exceptions import (
    QuantAnalyticsError,
    DataValidationError,
    InsufficientDataError,
    CalculationError,
    ConvergenceError,
    ModelFitError,
    ConfigurationError,
    DependencyError,
    handle_calculation_error,
    safe_calculation
)

from .data_validator import (
    DataQualityReport,
    DataValidator,
    validate_returns_series,
    validate_positive_number,
    validate_probability
)

# Risk management module
from .risk import (
    VaRCalculator,
    CVaRCalculator,
    DrawdownCalculator,
    MarketRiskCalculator,
    RiskAttributionCalculator,
    StressTestCalculator
)

# ML module
from .ml import (
    FeatureEngineeringCalculator,
    FactorMiningCalculator,
    ReturnPredictionCalculator,
    RiskPredictionCalculator,
    AnomalyDetectionCalculator,
)

# RL base module
from .rl import (
    BaseRLAgent,
    BaseRLEnvironment,
)

# FinRL module (optional)
try:
    from .finrl import (
        FinRLAgent,
        StockTradingEnv,
        FINRL_AVAILABLE,
    )
except ImportError:
    FINRL_AVAILABLE = False

# Qlib RL module (optional)
try:
    from .qlib import (
        QlibRLAgent,
        QlibTradingEnv,
        QLIB_RL_AVAILABLE,
    )
except ImportError:
    QLIB_RL_AVAILABLE = False

__all__ = [
    'BaseCalculator',
    'CalculatorFactory',
    'CalculationResult',
    'validate_inputs',
    'cache_result',
    'timing_decorator',
    'QuantAnalyticsError',
    'DataValidationError',
    'InsufficientDataError',
    'CalculationError',
    'ConvergenceError',
    'ModelFitError',
    'ConfigurationError',
    'DependencyError',
    'handle_calculation_error',
    'safe_calculation',
    'DataQualityReport',
    'DataValidator',
    'validate_returns_series',
    'validate_positive_number',
    'validate_probability',
    'VaRCalculator',
    'CVaRCalculator',
    'DrawdownCalculator',
    'MarketRiskCalculator',
    'RiskAttributionCalculator',
    'StressTestCalculator',
    'FeatureEngineeringCalculator',
    'FactorMiningCalculator',
    'ReturnPredictionCalculator',
    'RiskPredictionCalculator',
    'AnomalyDetectionCalculator',
    'BaseRLAgent',
    'BaseRLEnvironment',
    'FinRLAgent',
    'StockTradingEnv',
    'FINRL_AVAILABLE',
    'QlibRLAgent',
    'QlibTradingEnv',
    'QLIB_RL_AVAILABLE',
]

__version__ = '1.0.0'
