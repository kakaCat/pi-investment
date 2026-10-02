"""
Quantitative Base Calculator Module
====================================

Abstract base class for all quantitative calculations in QuantSys V2.
Provides common functionality, validation, and standardized interfaces.

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Union, Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import warnings


class BaseCalculator(ABC):
    """
    Abstract base class for all quantitative calculations.

    Provides common functionality, validation, and standardized interfaces
    for all quantitative analysis modules in QuantSys V2.

    Features:
        - Input validation (numeric, positive, probability, returns)
        - Result rounding and formatting
        - JSON serialization support
        - Missing data handling
        - Logging and metadata tracking

    Example:
        class MyCalculator(BaseCalculator):
            def calculate(self, data):
                validated = self._validate_numeric_input(data, 'data')
                result = np.mean(validated)
                return self._create_result_dict(result, 'mean')
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize base calculator with common parameters.

        Args:
            precision: Number of decimal places for calculations (default: 6)
            risk_free_rate: Default risk-free rate for calculations (default: 0.0)
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

    def _validate_numeric_input(self, data: Any, name: str = "data") -> Union[float, np.ndarray, pd.Series]:
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
            if not np.issubdtype(data.dtype, np.number):
                raise ValueError(f"{name} must be numeric")
            if np.any(np.isnan(data)) or np.any(np.isinf(data)):
                raise ValueError(f"{name} contains invalid values (NaN or Inf)")
            return data.astype(float)

        elif isinstance(data, pd.Series):
            if not pd.api.types.is_numeric_dtype(data):
                raise ValueError(f"{name} must be numeric")
            if data.isna().any():
                warnings.warn(f"{name} contains NaN values, they will be dropped")
                data = data.dropna()
            return data.astype(float)

        elif isinstance(data, pd.DataFrame):
            if data.empty:
                raise ValueError(f"{name} DataFrame is empty")
            # Convert all columns to numeric if possible
            try:
                numeric_data = data.select_dtypes(include=[np.number])
                if numeric_data.empty:
                    raise ValueError(f"{name} DataFrame has no numeric columns")
                return numeric_data.astype(float)
            except Exception:
                raise ValueError(f"{name} DataFrame cannot be converted to numeric")

        else:
            raise ValueError(f"{name} must be numeric (int, float, list, array, or pandas Series/DataFrame)")

    def _validate_positive(self, value: Union[float, np.ndarray], name: str = "value") -> Union[float, np.ndarray]:
        """
        Validate that value(s) are positive.

        Args:
            value: Value(s) to validate
            name: Name of the parameter for error messages

        Returns:
            Validated positive value(s)
        """
        validated = self._validate_numeric_input(value, name)

        if isinstance(validated, (int, float)):
            if validated <= 0:
                raise ValueError(f"{name} must be positive, got {validated}")
        else:
            if np.any(validated <= 0):
                raise ValueError(f"{name} must be positive for all values")

        return validated

    def _validate_probability(self, prob: Union[float, np.ndarray], name: str = "probability") -> Union[float, np.ndarray]:
        """
        Validate that probability value(s) are between 0 and 1.

        Args:
            prob: Probability value(s) to validate
            name: Name of the parameter for error messages

        Returns:
            Validated probability value(s)
        """
        validated = self._validate_numeric_input(prob, name)

        if isinstance(validated, (int, float)):
            if not 0 <= validated <= 1:
                raise ValueError(f"{name} must be between 0 and 1, got {validated}")
        else:
            if np.any((validated < 0) | (validated > 1)):
                raise ValueError(f"{name} must be between 0 and 1 for all values")

        return validated

    def _validate_returns(self, returns: Union[List, np.ndarray, pd.Series], name: str = "returns") -> np.ndarray:
        """
        Validate return data and convert to numpy array.

        Args:
            returns: Return data to validate
            name: Name of the parameter for error messages

        Returns:
            Validated returns as numpy array
        """
        validated = self._validate_numeric_input(returns, name)

        if isinstance(validated, (int, float)):
            raise ValueError(f"{name} must be a sequence of returns, not a single value")

        # Convert to numpy array
        if isinstance(validated, pd.Series):
            return validated.values
        elif isinstance(validated, pd.DataFrame):
            if validated.shape[1] == 1:
                return validated.iloc[:, 0].values
            else:
                raise ValueError(f"{name} DataFrame must have exactly one column for return calculations")

        return np.array(validated)

    def _round_result(self, result: Union[float, np.ndarray, Dict]) -> Union[float, np.ndarray, Dict]:
        """
        Round result to specified precision.

        Args:
            result: Result to round

        Returns:
            Rounded result
        """
        if isinstance(result, (int, float)):
            return round(result, self.precision)
        elif isinstance(result, np.ndarray):
            return np.round(result, self.precision)
        elif isinstance(result, dict):
            return {k: self._round_result(v) if isinstance(v, (int, float, np.ndarray)) else v
                    for k, v in result.items()}
        else:
            return result

    def _sanitize_for_json(self, obj: Any) -> Any:
        """
        Recursively sanitize objects for JSON serialization.
        Converts numpy types and Python booleans to JSON-compatible types.
        """
        if isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_for_json(x) for x in obj]
        elif isinstance(obj, tuple):
            return [self._sanitize_for_json(x) for x in obj]
        elif isinstance(obj, np.ndarray):
            return [self._sanitize_for_json(x) for x in obj.tolist()]
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, bool):
            return obj
        elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32, np.float16)):
            val = float(obj)
            if np.isnan(val) or np.isinf(val):
                return None
            return val
        elif isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    def _create_result_dict(self,
                            value: Union[float, np.ndarray],
                            method: str,
                            parameters: Dict[str, Any] = None,
                            metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create standardized result dictionary.

        Args:
            value: Calculated value
            method: Method used for calculation
            parameters: Parameters used in calculation
            metadata: Additional metadata

        Returns:
            Standardized result dictionary with all values sanitized for JSON
        """
        result = {
            'value': self._round_result(value),
            'method': method,
            'timestamp': datetime.now().isoformat(),
            'calculator': self.__class__.__name__
        }

        if parameters:
            result['parameters'] = self._sanitize_for_json(parameters)

        if metadata:
            result['metadata'] = self._sanitize_for_json(metadata)

        return result

    def _check_data_length(self, data: Union[np.ndarray, pd.Series], min_length: int = 2) -> None:
        """
        Check if data has sufficient length for calculations.

        Args:
            data: Data to check
            min_length: Minimum required length

        Raises:
            ValueError: If data length is insufficient
        """
        if len(data) < min_length:
            raise ValueError(f"Insufficient data: need at least {min_length} observations, got {len(data)}")

    def _handle_missing_data(self,
                             data: Union[np.ndarray, pd.Series],
                             method: str = 'drop') -> Union[np.ndarray, pd.Series]:
        """
        Handle missing data in input.

        Args:
            data: Input data
            method: Method to handle missing data ('drop', 'interpolate', 'forward_fill')

        Returns:
            Data with missing values handled
        """
        if isinstance(data, pd.Series):
            if method == 'drop':
                return data.dropna()
            elif method == 'interpolate':
                return data.interpolate()
            elif method == 'forward_fill':
                return data.fillna(method='ffill')
            else:
                raise ValueError(f"Unknown missing data method: {method}")

        elif isinstance(data, np.ndarray):
            if method == 'drop':
                return data[~np.isnan(data)]
            else:
                # Convert to pandas for more sophisticated handling
                series = pd.Series(data)
                return self._handle_missing_data(series, method).values

        return data

    def set_precision(self, precision: int) -> None:
        """Set calculation precision."""
        if precision < 0:
            raise ValueError("Precision must be non-negative")
        self.precision = precision

    def set_risk_free_rate(self, rate: float) -> None:
        """Set default risk-free rate."""
        self.risk_free_rate = self._validate_numeric_input(rate, "risk_free_rate")

    # 2026-10-01（REQ-261001145152-3982 t-3f2444）：**去抽象化**，改为默认实现抛明确异常。
    #
    # 背景：本类是两版 BaseCalculator 收敛后的唯一正本。原 501 行版把 calculate 声明为
    # @abstractmethod，而原 327 行版（domain/quantlib/core/base_calculator.py）**整个类没有任何
    # 抽象方法**——factor 家族（domain/factors/library/*）只实现 get_supported_methods，
    # 从不实现 calculate。两者合并后，这些子类立刻变成"抽象类无法实例化"
    # （实测：12 个测试模块收集失败，报 `Can't instantiate abstract class MomentumFactors
    # without an implementation for abstract method 'calculate'`）。
    #
    # 两组子类的要求互斥（一组以 calculate 为主入口、另一组以 get_supported_methods 为契约），
    # 而收敛目标只允许存在一个类。取舍：**放宽为默认实现**——未实现者仍可实例化，
    # 一旦真的调用 calculate 则立刻给出明确错误（而非静默返回空）。
    # 代价（如实记录）：失去"实例化即发现未实现"的编译期式护栏，改由调用时报错兜底。
    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Main calculation entry point.

        Subclasses should implement this. 若子类走的是 get_supported_methods 契约
        （factor 家族），则可不实现，但调用本方法会抛出明确异常而不是静默返回空。
        """
        raise NotImplementedError(
            f"{type(self).__name__} 未实现 calculate()。"
            "若该类属于 factor 家族，请改用其 get_supported_methods() 声明的具体方法。"
        )

    def get_supported_methods(self) -> List[str]:
        """
        Get list of supported calculation methods.
        Should be overridden by subclasses.
        """
        return ['default']

    def validate_method(self, method: str) -> str:
        """
        Validate that the specified method is supported.

        Args:
            method: Method to validate

        Returns:
            Validated method name

        Raises:
            ValueError: If method is not supported
        """
        supported = self.get_supported_methods()
        if method not in supported:
            raise ValueError(f"Method '{method}' not supported. Available methods: {supported}")
        return method


class CalculatorFactory:
    """
    Factory class for creating calculator instances.
    Provides a centralized way to instantiate different calculators.

    Example:
        CalculatorFactory.register_calculator('volatility', VolatilityCalculator)
        calc = CalculatorFactory.create_calculator('volatility', precision=4)
    """

    _calculators = {}

    @classmethod
    def register_calculator(cls, name: str, calculator_class: type) -> None:
        """Register a calculator class."""
        cls._calculators[name] = calculator_class

    @classmethod
    def create_calculator(cls, name: str, **kwargs) -> BaseCalculator:
        """Create a calculator instance."""
        if name not in cls._calculators:
            raise ValueError(f"Calculator '{name}' not registered")
        return cls._calculators[name](**kwargs)

    @classmethod
    def list_calculators(cls) -> List[str]:
        """List all registered calculators."""
        return list(cls._calculators.keys())


class CalculationResult:
    """
    Wrapper class for calculation results with additional functionality.

    Provides convenient access to result values and metadata,
    plus export capabilities.

    Example:
        result = CalculationResult({'value': 0.25, 'method': 'sharpe_ratio'})
        logger.info(result.value)  # 0.25
        result.export_json('result.json')
    """

    def __init__(self, result_dict: Dict[str, Any]):
        """Initialize with result dictionary."""
        self._data = result_dict
        self.value = result_dict.get('value')
        self.method = result_dict.get('method')
        self.timestamp = result_dict.get('timestamp')
        self.calculator = result_dict.get('calculator')

    def __repr__(self) -> str:
        return f"CalculationResult(value={self.value}, method='{self.method}')"

    def __float__(self) -> float:
        """Allow conversion to float."""
        if isinstance(self.value, (int, float)):
            return float(self.value)
        raise TypeError("Cannot convert array result to float")

    def to_dict(self) -> Dict[str, Any]:
        """Return result as dictionary."""
        return self._data.copy()

    def to_dataframe(self) -> pd.DataFrame:
        """Convert result to DataFrame if applicable."""
        if isinstance(self.value, np.ndarray):
            return pd.DataFrame({'value': self.value})
        else:
            return pd.DataFrame([self._data])

    def export_json(self, filepath: str) -> None:
        """Export result to JSON file."""
        import json
        with open(filepath, 'w') as f:
            # Handle numpy arrays in JSON serialization
            def convert_numpy(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            json.dump(self._data, f, default=convert_numpy, indent=2)


# Decorators for common functionality
def validate_inputs(func):
    """Decorator to add input validation to calculation methods."""
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error in {func.__name__}: {str(e)}")
            raise
    return wrapper


def cache_result(func):
    """Decorator to cache calculation results."""
    def wrapper(self, *args, **kwargs):
        # Simple caching based on function arguments
        cache_key = f"{func.__name__}_{hash(str(args) + str(sorted(kwargs.items())))}"

        if not hasattr(self, '_cache'):
            self._cache = {}

        if cache_key in self._cache:
            self.logger.info(f"Returning cached result for {func.__name__}")
            return self._cache[cache_key]

        result = func(self, *args, **kwargs)
        self._cache[cache_key] = result
        return result
    return wrapper


def timing_decorator(func):
    """Decorator to measure calculation time.

    2026-10-01（REQ-261001145152-3982 t-3f2444）：两版收敛时做**加法兼容**。
    原 501 行版写顶层 `result['calculation_time']`（秒，4 位小数）；
    原 327 行版写 `result['metadata']['execution_time_ms']`（毫秒，2 位小数）。
    两者都是消费方/测试的真实契约（例如 `test_*_timing_metadata` 一族断言元数据键、
    timeseries/fixed_income 侧读顶层键），**同时写两份**比二选一更安全：
    既不破坏任何一方的读取，也让同一份结果自带两种口径。
    """
    from functools import wraps

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        import time
        start_time = time.time()
        result = func(self, *args, **kwargs)
        elapsed = time.time() - start_time

        if isinstance(result, dict):
            # 501 口径：顶层秒数
            result['calculation_time'] = round(elapsed, 4)
            # 327 口径：metadata 内毫秒数（仅在结果本来就有 metadata 时补，保持原行为边界）
            if isinstance(result.get("metadata"), dict):
                result["metadata"]["execution_time_ms"] = round(elapsed * 1000, 2)

        logger = getattr(self, "logger", None)
        if logger is not None:
            logger.debug(f"{func.__name__} executed in {elapsed * 1000:.2f}ms")
        return result
    return wrapper


def handle_calculation_error(func):
    """
    Decorator to handle calculation errors gracefully.
    Wraps exceptions with context about the calculation.

    2026-10-01（REQ-261001145152-3982 t-3f2444）：本函数**逐字搬入**自
    `domain/quantlib/core/base_calculator.py`（该文件已收敛为本模块的转发壳）。
    搬入理由：`domain/quantlib/statistics` 与 `domain/quantlib/timeseries/analyzer` 共
    11 处在用它，而全仓另有两份**实现不同**的同名函数
    （`domain/quantlib/core/exceptions.py` 相似度 0.53、
    `domain/quantlib/exceptions.py` 相似度 0.31）——为做到"收敛且零行为变化"，
    必须保留消费方当前实际调用的这一份，而不是随手换成同名兄弟。
    """
    # 局部 import：避免模块级循环依赖，且保证与搬入前指向同一批异常对象
    from functools import wraps

    from domain.quantlib.core.exceptions import DataValidationError, InsufficientDataError

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
