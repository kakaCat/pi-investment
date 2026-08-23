"""
QuantLib - Quantitative Finance Technical Library
==================================================

**角色定位**: 纯技术计算库，提供金融量化计算的基础工具和算法。

**不属于此库的内容** (已迁移至其他领域):
    - 回测引擎 → domain.backtest
    - 风险管理 → domain.risk
    - 因子计算 → domain.factors

**当前模块结构**:

核心基础设施:
    - base_calculator: 计算器抽象基类、工厂、结果类型
    - data_validator: 数据质量验证和报告
    - exceptions: QuantLib 自定义异常体系

专业领域计算:
    - derivatives: 衍生品定价 (期权、波动率曲面、Greeks)
    - fixed_income: 固定收益 (债券定价、久期、凸度、收益率曲线)
    - portfolio: 投资组合优化 (均值方差、Black-Litterman、风险平价)
    - timeseries: 时间序列分析 (ARIMA、GARCH、协整、季节性)
    - statistics: 统计工具 (分布拟合、假设检验、蒙特卡洛)
    - technical: 技术指标 (移动平均、动量、趋势、波动率)

机器学习与强化学习:
    - ml: 机器学习集成 (特征工程、因子挖掘、收益预测、风险预测、异常检测)
    - rl: 强化学习基础设施 (BaseRLAgent、BaseRLEnvironment)
    - finrl: FinRL 框架集成 (optional)
    - qlib: Qlib RL 框架集成 (optional)

高级策略 (待决策是否保留):
    - cross_asset_strategies: 跨资产策略
    - hft_strategies: 高频交易策略
    - futures: 期货相关计算
    - gpu_acceleration: GPU 加速工具

工具:
    - tools: 辅助工具 (数据转换、缓存、性能分析)

Migration Guide:
    ```python
    # 旧导入 (已废弃)
    from domain.quantlib.risk import RiskAttributionCalculator
    from domain.quantlib.backtest_engine import BacktestEngine
    from domain.quantlib.factors import FactorLibrary

    # 新导入 (正确)
    from domain.risk import RiskAttributionCalculator
    from domain.backtest.engine import BacktestEngine
    from domain.factors.library import FactorLibrary

    # 技术计算 (仍在此库)
    from domain.quantlib import BaseCalculator, DataValidator
    from domain.quantlib.derivatives import BlackScholesCalculator
    from domain.quantlib.portfolio import MeanVarianceOptimizer
    ```

Examples:
    示例代码已迁移至 `docs/examples/quantlib/`

Architecture Notes:
    此库应保持为纯技术计算层，不应依赖:
    - application 层 (应用服务)
    - adapters 层 (外部系统适配器)
    - infrastructure 层 (除 infrastructure.quantlib 外)

    如需配置或数据源，应通过依赖注入，不直接导入。

Refactoring History:
    - 2026-08-23: Phase 2 完成，拆分出 backtest/risk/factors 三个业务域
    - 2026-08-23: Phase 3 清理空目录、迁移 examples、重写文档
"""

# ============================================================================
# Core Infrastructure
# ============================================================================

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

# ============================================================================
# Lazy Imports for Heavy Dependencies
# ============================================================================
# ml/rl/finrl/qlib 模块会拉起 torch/mlflow(→polars)/transformers 等重依赖，
# 它们各自携带 OpenMP 运行时；与 lightgbm/xgboost 的 Homebrew libomp 混载后
# 可能触发 OpenMP worker 线程段错误 (__kmp_suspend_initialize_thread)。
#
# 使用 PEP 562 __getattr__ 按需加载：
#   - 对外契约不变 (from domain.quantlib import X 照常工作)
#   - 只做衍生品/债券/投组计算的进程不会被动加载 ML/RL 栈
#
# 参考: memory/polars-numpy-malloc-crash.md (2026-08-13)

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
    """PEP 562: 惰性导入重依赖模块"""
    if name in _LAZY_IMPORTS:
        mod = _importlib.import_module(_LAZY_IMPORTS[name], __name__)
        val = getattr(mod, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    """支持 dir(quantlib) 和 IDE 自动补全"""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Core infrastructure
    'BaseCalculator',
    'CalculatorFactory',
    'CalculationResult',
    'validate_inputs',
    'cache_result',
    'timing_decorator',

    # Exceptions
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

    # Data validation
    'DataQualityReport',
    'DataValidator',
    'validate_returns_series',
    'validate_positive_number',
    'validate_probability',

    # Lazy imports (ML/RL)
    'FeatureEngineeringCalculator',
    'FactorMiningCalculator',
    'ReturnPredictionCalculator',
    'RiskPredictionCalculator',
    'AnomalyDetectionCalculator',
    'BaseRLAgent',
    'BaseRLEnvironment',
    'FinRLAgent',
    'StockTradingEnv',
    'QlibRLAgent',
    'QlibTradingEnv',
]
