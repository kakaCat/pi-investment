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

# ── 重模块惰性导入（2026-08-20 segfault 修复，PEP 562）──────────────────
# ml/rl/finrl/qlib 会拉起 torch / mlflow(→polars) / transformers 等重依赖，
# 它们各自携带 OpenMP 运行时；与 lightgbm/xgboost 的 Homebrew libomp 混载后
# OpenMP worker 线程在 fit 时段错误（__kmp_suspend_initialize_thread）。
# 此前 `from infrastructure.quantlib.adapters import get_factor_adapter` 这种纯因子计算
# 调用也会被动加载整套 ML/RL 栈。改为 __getattr__ 按需加载后：
#   - 对外契约不变（from domain.quantlib import X 照常工作）
#   - 只做因子/风险计算的进程不再引入 torch/polars/mlflow
import importlib as _importlib

_LAZY_IMPORTS = {
    # ML module
    'FeatureEngineeringCalculator': '.ml',
    'FactorMiningCalculator': '.ml',
    'ReturnPredictionCalculator': '.ml',
    'RiskPredictionCalculator': '.ml',
    'AnomalyDetectionCalculator': '.ml',
    # RL base module
    'BaseRLAgent': '.rl',
    'BaseRLEnvironment': '.rl',
    # FinRL module (optional)
    'FinRLAgent': '.finrl',
    'StockTradingEnv': '.finrl',
    # Qlib RL module (optional)
    'QlibRLAgent': '.qlib',
    'QlibTradingEnv': '.qlib',
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        mod = _importlib.import_module(_LAZY_IMPORTS[name], __name__)
        val = getattr(mod, name)
        globals()[name] = val
        return val
    if name == 'FINRL_AVAILABLE':
        try:
            _importlib.import_module('.finrl', __name__)
            val = True
        except ImportError:
            val = False
        globals()[name] = val
        return val
    if name == 'QLIB_RL_AVAILABLE':
        try:
            _importlib.import_module('.qlib', __name__)
            val = True
        except ImportError:
            val = False
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
