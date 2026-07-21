"""
Quantitative Base Calculator Module
====================================

Base class for all quantitative calculations, inspired by FinceptTerminal's QuantLib Suite.

Provides:
- Unified input validation framework
- Standardized result format
- Decorator support for timing, validation, and error handling
- Logging and metadata tracking
"""

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Union, Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
from functools import wraps
import time

# Import exceptions for decorator
from .exceptions import DataValidationError, InsufficientDataError


class BaseCalculator(ABC):
    """
    Abstract base class for all quantitative calculations.

    Provides common functionality, validation, and standardized interfaces
    for all quantitative analysis modules.
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize base calculator with common parameters.

        Args:
            precision: Number of decimal places for calculations
            risk_free_rate: Default risk-free rate for calculations
        """
        self.precision = precision
        self.risk_free_rate = risk_free_rate
        self.logger = self._setup_logger()
        self.calculation_metadata = {}

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for the calculator."""
        logger = logging.getLogger(f"{self.__class__.__name__}")
        logger.setLevel(logging.INFO)
        return logger

    def _validate_numeric_input(
        self,
        data: Any,
        name: str = "data"
    ) -> Union[float, np.ndarray, pd.Series]:
        """
        Validate and convert input to appropriate numeric type.

        Args:
            data: Input data to validate
            name: Name of the parameter for error messages

        Returns:
            Validated numeric data

        Raises:
            ValueError: If data cannot be converted to numeric
        """
        if data is None:
            raise ValueError(f"{name} cannot be None")

        # Handle different input types
        if isinstance(data, (int, float)):
            if np.isnan(data) or np.isinf(data):
                raise ValueError(f"{name} contains invalid values (NaN or Inf)")
            return float(data)

        elif isinstance(data, (list, tuple)):
            try:
                arr = np.array(data, dtype=float)
                if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
                    raise ValueError(f"{name} contains invalid values (NaN or Inf)")
                return arr
            except (ValueError, TypeError):
                raise ValueError(f"{name} cannot be converted to numeric array")

        elif isinstance(data, np.ndarray):
            if np.any(np.isnan(data)) or np.any(np.isinf(data)):
                raise ValueError(f"{name} contains invalid values (NaN or Inf)")
            return data

        elif isinstance(data, pd.Series):
            if data.isnull().any() or np.isinf(data).any():
                raise ValueError(f"{name} contains invalid values (NaN or Inf)")
            return data

        else:
            raise ValueError(f"{name} has unsupported type: {type(data)}")

    def _validate_returns(
        self,
        returns: Union[List, np.ndarray, pd.Series],
        name: str = "returns"
    ) -> np.ndarray:
        """
        Validate returns series.

        Args:
            returns: Returns data to validate
            name: Name of the parameter for error messages

        Returns:
            Validated returns as numpy array
        """
        validated = self._validate_numeric_input(returns, name)

        if isinstance(validated, (pd.Series, np.ndarray)):
            arr = np.array(validated)
        else:
            arr = np.array([validated])

        # Check for extreme values
        if np.any(np.abs(arr) > 10):
            self.logger.warning(f"{name} contains extreme values (>1000%)")

        return arr

    def _validate_positive_number(
        self,
        value: float,
        name: str = "value"
    ) -> float:
        """
        Validate that a number is positive.

        Args:
            value: Value to validate
            name: Name of the parameter for error messages

        Returns:
            Validated value
        """
        validated = self._validate_numeric_input(value, name)
        if validated <= 0:
            raise ValueError(f"{name} must be positive, got {validated}")
        return float(validated)

    def _validate_probability(
        self,
        prob: float,
        name: str = "probability"
    ) -> float:
        """
        Validate that a value is a valid probability [0, 1].

        Args:
            prob: Probability to validate
            name: Name of the parameter for error messages

        Returns:
            Validated probability
        """
        validated = self._validate_numeric_input(prob, name)
        if not (0 <= validated <= 1):
            raise ValueError(f"{name} must be in [0, 1], got {validated}")
        return float(validated)

    def _check_data_length(
        self,
        data: Union[List, np.ndarray, pd.Series],
        min_length: int = 2
    ) -> None:
        """
        Check that data has sufficient length.

        Args:
            data: Data to check
            min_length: Minimum required length

        Raises:
            ValueError: If data is too short
        """
        length = len(data)
        if length < min_length:
            raise ValueError(
                f"Insufficient data: got {length} points, need at least {min_length}"
            )

    def _create_result_dict(
        self,
        value: Any,
        method: str,
        parameters: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create standardized result dictionary.

        Args:
            value: Calculation result
            method: Method name used
            parameters: Input parameters
            metadata: Additional metadata

        Returns:
            Standardized result dictionary
        """
        result = {
            "value": value,
            "method": method,
            "parameters": parameters,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "calculator": self.__class__.__name__
        }

        return result

    @abstractmethod
    def get_supported_methods(self) -> List[str]:
        """
        Get list of supported calculation methods.

        Returns:
            List of method names
        """
        pass


# Decorators

def validate_inputs(func):
    """
    Decorator to validate inputs before calculation.
    Catches common validation errors and provides clear messages.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except ValueError as e:
            self.logger.error(f"Input validation failed in {func.__name__}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise
    return wrapper


def timing_decorator(func):
    """
    Decorator to measure execution time.
    Adds execution_time_ms to result metadata.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        result = func(self, *args, **kwargs)
        execution_time = (time.time() - start_time) * 1000  # Convert to ms

        # Add timing to metadata if result is a dict
        if isinstance(result, dict) and "metadata" in result:
            result["metadata"]["execution_time_ms"] = round(execution_time, 2)

        self.logger.debug(f"{func.__name__} executed in {execution_time:.2f}ms")
        return result
    return wrapper


def handle_calculation_error(func):
    """
    Decorator to handle calculation errors gracefully.
    Wraps exceptions with context about the calculation.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except (ValueError, DataValidationError, InsufficientDataError) as e:
            # Re-raise validation errors as-is
            self.logger.error(f"Validation error in {func.__name__}: {e}")
            raise
        except Exception as e:
            error_msg = f"Calculation error in {func.__name__}: {type(e).__name__}: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    return wrapper


class CalculatorFactory:
    """
    Factory for creating calculator instances.
    Allows registration and retrieval of calculator classes.
    """

    _calculators: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, calculator_class: type) -> None:
        """Register a calculator class."""
        if not issubclass(calculator_class, BaseCalculator):
            raise ValueError(f"{calculator_class} must inherit from BaseCalculator")
        cls._calculators[name] = calculator_class

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseCalculator:
        """Create a calculator instance by name."""
        if name not in cls._calculators:
            raise ValueError(f"Calculator '{name}' not registered")
        return cls._calculators[name](**kwargs)

    @classmethod
    def list_calculators(cls) -> List[str]:
        """List all registered calculators."""
        return list(cls._calculators.keys())
