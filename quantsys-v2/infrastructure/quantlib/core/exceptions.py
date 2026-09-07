"""
Quantitative Analytics Exceptions
==================================

Custom exception classes for quantitative calculations.
Inspired by FinceptTerminal's exception handling framework.
"""

from typing import Optional, Any
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class QuantAnalyticsError(Exception):
    """Base exception for all quantitative analytics errors."""
    pass


class DataValidationError(QuantAnalyticsError):
    """Raised when input data validation fails."""

    def __init__(self, message: str, parameter_name: Optional[str] = None):
        self.parameter_name = parameter_name
        if parameter_name:
            message = f"Data validation error for '{parameter_name}': {message}"
        super().__init__(message)


class InsufficientDataError(QuantAnalyticsError):
    """Raised when there is insufficient data for calculation."""

    def __init__(self, required: int, actual: int, message: Optional[str] = None):
        self.required = required
        self.actual = actual
        if message is None:
            message = f"Insufficient data: need {required} points, got {actual}"
        super().__init__(message)


class CalculationError(QuantAnalyticsError):
    """Raised when a calculation fails."""

    def __init__(self, method: str, message: str):
        self.method = method
        super().__init__(f"Calculation error in {method}: {message}")


class ConvergenceError(QuantAnalyticsError):
    """Raised when an iterative algorithm fails to converge."""

    def __init__(self, method: str, iterations: int, message: Optional[str] = None):
        self.method = method
        self.iterations = iterations
        if message is None:
            message = f"Failed to converge after {iterations} iterations in {method}"
        super().__init__(message)


class ModelFitError(QuantAnalyticsError):
    """Raised when a model fitting fails."""

    def __init__(self, model_name: str, message: str):
        self.model_name = model_name
        super().__init__(f"Model fit error for {model_name}: {message}")


class ConfigurationError(QuantAnalyticsError):
    """Raised when configuration is invalid."""
    pass


class DependencyError(QuantAnalyticsError):
    """Raised when a required dependency is missing."""

    def __init__(self, package: str, message: Optional[str] = None):
        self.package = package
        if message is None:
            message = f"Required package '{package}' is not installed"
        super().__init__(message)


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
