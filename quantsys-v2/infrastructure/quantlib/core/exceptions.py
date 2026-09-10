"""
Quantitative Analytics Exceptions
==================================

Custom exception classes for quantitative calculations.
Inspired by FinceptTerminal's exception handling framework.
"""

from typing import Optional, Any
from functools import wraps
import logging

# 2026-09-10（w-f4aa1f6a）：统一双轨异常体系——本模块类改为继承 domain.quantlib.exceptions
# 的同名规范类（54 个非测试文件 + 测试用 domain 版；本模块 12 个文件用 infra 版）。
# 此前两边同名不同类，pytest.raises(domain 版) 接不住 infra 版抛出的异常，
# 13 个存量因子测试因此全挂。继承后双向兼容：except/raises 任一侧都成立。
# 构造签名保持 infra 原版不变（parameter_name / actual / 自定义 message 全保留）。
from domain.quantlib.exceptions import (
    QuantAnalyticsError as _DomainQuantAnalyticsError,
    DataValidationError as _DomainDataValidationError,
    InsufficientDataError as _DomainInsufficientDataError,
    CalculationError as _DomainCalculationError,
    ConvergenceError as _DomainConvergenceError,
    ModelFitError as _DomainModelFitError,
    ConfigurationError as _DomainConfigurationError,
    DependencyError as _DomainDependencyError,
)

logger = logging.getLogger(__name__)


class QuantAnalyticsError(_DomainQuantAnalyticsError):
    """Base exception for all quantitative analytics errors."""

    def __init__(self, message: str = "", error_code: Optional[str] = None):
        super().__init__(message, error_code=error_code)


class DataValidationError(_DomainDataValidationError):
    """Raised when input data validation fails."""

    def __init__(self, message: str, parameter_name: Optional[str] = None):
        self.parameter_name = parameter_name
        super().__init__(message, field_name=parameter_name)


class InsufficientDataError(_DomainInsufficientDataError):
    """Raised when there is insufficient data for calculation."""

    def __init__(self, required: int, actual: int, message: Optional[str] = None):
        self.required = required
        self.actual = actual
        super().__init__(required=required, provided=actual)
        if message is not None:
            # 保留 infra 版自定义 message（如 "TRIX requires at least 36 data points"）
            self.message = message
            self.args = (message,)


class CalculationError(_DomainCalculationError):
    """Raised when a calculation fails.（infra 签名 (method, message) 保留）"""

    def __init__(self, method: str, message: str):
        self.method = method
        self.calculation_type = method  # 兼容 domain 版属性名
        # 不传 calculation_type 给父类——避免 "method: Calculation error in method: ..." 前缀叠加
        super().__init__(f"Calculation error in {method}: {message}")


class ConvergenceError(_DomainConvergenceError):
    """Raised when an iterative algorithm fails to converge.（infra 签名 (method, iterations, message) 保留）"""

    def __init__(self, method: str, iterations: int, message: Optional[str] = None):
        self.method = method
        self.iterations = iterations
        if message is None:
            message = f"Failed to converge after {iterations} iterations in {method}"
        # 不传 iterations 给父类——避免 "(after N iterations)" 与自组文案重复
        super().__init__(message)


class ModelFitError(_DomainModelFitError):
    """Raised when a model fitting fails.（infra 签名 (model_name, message) 保留）"""

    def __init__(self, model_name: str, message: str):
        self.model_name = model_name
        self.model_type = model_name  # 兼容 domain 版属性名
        # 不传 model_type 给父类——避免 "model: Model fit error for model: ..." 前缀叠加
        super().__init__(f"Model fit error for {model_name}: {message}")


class ConfigurationError(_DomainConfigurationError):
    """Raised when configuration is invalid.（infra 原版为裸 pass，宽松构造兼容任意文案）"""

    def __init__(self, message: str = "", parameter: Optional[str] = None):
        super().__init__(message, parameter=parameter)


class DependencyError(_DomainDependencyError):
    """Raised when a required dependency is missing.（infra 签名 (package, message) 保留）"""

    def __init__(self, package: str, message: Optional[str] = None):
        self.package = package
        super().__init__(package, message=message)


# Decorator for safe calculation execution

def handle_calculation_error(func):
    """
    Decorator to handle calculation errors gracefully.
    Wraps exceptions with context about the calculation.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DataValidationError:
            # Re-raise validation errors as-is
            raise
        except InsufficientDataError:
            # Re-raise data errors as-is
            raise
        except ConvergenceError:
            # Re-raise convergence errors as-is
            raise
        except Exception as e:
            # Wrap other exceptions in CalculationError
            func_name = func.__name__
            logger.error(f"Calculation error in {func_name}: {type(e).__name__}: {e}")
            raise CalculationError(func_name, str(e)) from e
    return wrapper


def safe_calculation(default_value: Any = None):
    """
    Decorator to catch all errors and return a default value.
    Useful for non-critical calculations where failure should not stop execution.

    Args:
        default_value: Value to return on error

    Example:
        @safe_calculation(default_value=0.0)
        def calculate_sharpe_ratio(returns):
            return returns.mean() / returns.std()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    f"Safe calculation failed in {func.__name__}: {e}. "
                    f"Returning default value: {default_value}"
                )
                return default_value
        return wrapper
    return decorator


def require_dependency(package: str):
    """
    Decorator to check for required dependencies.

    Args:
        package: Name of the required package

    Example:
        @require_dependency('scipy')
        def calculate_with_scipy():
            from scipy import stats
            return stats.norm.cdf(0)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                __import__(package)
            except ImportError:
                raise DependencyError(
                    package,
                    f"Function {func.__name__} requires '{package}' package. "
                    f"Install it with: pip install {package}"
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator
