"""
Quantitative Exceptions Module
===============================

Custom exception classes for quantitative analysis in QuantSys V2.

Provides specialized exceptions for different types of errors that can occur
during quantitative calculations, with structured error information.

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

from typing import Optional, Any
from functools import wraps


class QuantAnalyticsError(Exception):
    """
    Base exception for all quantitative analytics errors.

    All custom exceptions in QuantLib inherit from this class.
    Provides structured error information with error codes.

    Example:
        raise QuantAnalyticsError("Calculation failed", error_code="CALC_001")
    """

    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization."""
        return {
            'error': self.message,
            'error_code': self.error_code,
            'error_type': self.__class__.__name__
        }


class DataValidationError(QuantAnalyticsError):
    """
    Raised when input data fails validation checks.

    Example:
        raise DataValidationError("Must be positive", field_name="price")
    """

    def __init__(self, message: str, field_name: Optional[str] = None):
        self.field_name = field_name
        super().__init__(
            message=f"{field_name}: {message}" if field_name else message,
            error_code="DATA_VALIDATION_ERROR"
        )


class InsufficientDataError(QuantAnalyticsError):
    """
    Raised when there is not enough data for the calculation.

    Example:
        raise InsufficientDataError(required=30, provided=10, calculation="volatility")
    """

    def __init__(self, required: int, provided: int, calculation: Optional[str] = None):
        self.required = required
        self.provided = provided
        self.calculation = calculation
        message = f"Insufficient data: need {required} observations, got {provided}"
        if calculation:
            message = f"{calculation}: {message}"
        super().__init__(message=message, error_code="INSUFFICIENT_DATA")


class CalculationError(QuantAnalyticsError):
    """
    Raised when a calculation fails.

    Example:
        raise CalculationError("Division by zero", calculation_type="sharpe_ratio")
    """

    def __init__(self, message: str, calculation_type: Optional[str] = None):
        self.calculation_type = calculation_type
        super().__init__(
            message=f"{calculation_type}: {message}" if calculation_type else message,
            error_code="CALCULATION_ERROR"
        )


class ConvergenceError(QuantAnalyticsError):
    """
    Raised when an optimization or iterative method fails to converge.

    Example:
        raise ConvergenceError("Failed to converge", iterations=1000)
    """

    def __init__(self, message: str, iterations: Optional[int] = None):
        self.iterations = iterations
        if iterations:
            message = f"{message} (after {iterations} iterations)"
        super().__init__(message=message, error_code="CONVERGENCE_ERROR")


class ModelFitError(QuantAnalyticsError):
    """
    Raised when a statistical model fails to fit.

    Example:
        raise ModelFitError("Singular matrix", model_type="linear_regression")
    """

    def __init__(self, message: str, model_type: Optional[str] = None):
        self.model_type = model_type
        super().__init__(
            message=f"{model_type}: {message}" if model_type else message,
            error_code="MODEL_FIT_ERROR"
        )


class ConfigurationError(QuantAnalyticsError):
    """
    Raised when configuration parameters are invalid.

    Example:
        raise ConfigurationError("Must be between 0 and 1", parameter="confidence_level")
    """

    def __init__(self, message: str, parameter: Optional[str] = None):
        self.parameter = parameter
        super().__init__(
            message=f"Invalid parameter '{parameter}': {message}" if parameter else message,
            error_code="CONFIGURATION_ERROR"
        )


class DependencyError(QuantAnalyticsError):
    """
    Raised when a required dependency is not available.

    Example:
        raise DependencyError("scipy", message="Install with: pip install scipy")
    """

    def __init__(self, dependency: str, message: Optional[str] = None):
        self.dependency = dependency
        msg = f"Required dependency '{dependency}' not available"
        if message:
            msg = f"{msg}: {message}"
        super().__init__(message=msg, error_code="DEPENDENCY_ERROR")


class DataFrameConversionError(QuantAnalyticsError):
    """
    Raised when DataFrame conversion between pandas/polars fails.

    Example:
        raise DataFrameConversionError("Cannot convert to polars DataFrame")
    """

    def __init__(self, message: str):
        super().__init__(message=message, error_code="DATAFRAME_CONVERSION_ERROR")


class TALibBridgeError(QuantAnalyticsError):
    """
    Raised when TA-Lib bridging operations fail.

    Example:
        raise TALibBridgeError("Missing required columns: ['close', 'volume']")
    """

    def __init__(self, message: str):
        super().__init__(message=message, error_code="TALIB_BRIDGE_ERROR")


class PolarsSchemaError(QuantAnalyticsError):
    """
    Raised when polars DataFrame schema is invalid.

    Example:
        raise PolarsSchemaError("Expected Float64, got Int64")
    """

    def __init__(self, message: str):
        super().__init__(message=message, error_code="POLARS_SCHEMA_ERROR")


def handle_calculation_error(func):
    """
    Decorator to handle calculation errors gracefully.

    Catches generic exceptions and converts them to CalculationError
    while preserving specific QuantAnalyticsError exceptions.

    Example:
        @handle_calculation_error
        def my_calculation(data):
            return data / 0  # Will raise CalculationError
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DataValidationError:
            raise
        except InsufficientDataError:
            raise
        except CalculationError:
            raise
        except ConvergenceError:
            raise
        except ModelFitError:
            raise
        except Exception as e:
            func_name = getattr(func, '__name__', 'unknown')
            raise CalculationError(
                message=str(e),
                calculation_type=func_name
            ) from e
    return wrapper


def safe_calculation(default_value: Any = None):
    """
    Decorator that returns a default value on error instead of raising.

    Useful for calculations where you want to continue processing
    even if some calculations fail.

    Example:
        @safe_calculation(default_value=0.0)
        def risky_calculation(data):
            return data / 0  # Returns 0.0 instead of raising
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                return default_value
        return wrapper
    return decorator
