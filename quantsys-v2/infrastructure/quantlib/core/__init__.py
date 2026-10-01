"""
QuantLib Core Module

Pure quantitative computing utilities and base classes.
"""

# 2026-10-01（REQ-261001145152-3982 t-9ccd5e）：base_calculator / exceptions 原先在本目录
# 有一份与 domain.quantlib.core 下**逐字相同**的副本（md5 一致：327 行 / 189 行）。
# 副本已删除，这里改为从 domain 正本 import —— **对外 API 与 __all__ 完全不变**
# （BaseCalculator / CalculatorFactory / 8 个异常类照旧可从 infrastructure.quantlib.core 取到），
# 只是不再维护第二份实现。
from domain.quantlib.core.base_calculator import BaseCalculator, CalculatorFactory
from infrastructure.quantlib.core.pipeline import QuantPipeline, PipelineStage
from domain.quantlib.core.exceptions import (
    QuantAnalyticsError,
    DataValidationError,
    InsufficientDataError,
    CalculationError,
    ConvergenceError,
    ModelFitError,
    ConfigurationError,
    DependencyError,
)
from infrastructure.quantlib.core.validators import (
    validate_symbol,
    validate_date,
    validate_required,
    validate_positive,
)
from infrastructure.quantlib.core.portfolio_calculator import PortfolioCalculator
from infrastructure.quantlib.core.data_cleaning import DataCleaningPipeline
from infrastructure.quantlib.core.data_validator import DataValidator, DataQualityReport

__all__ = [
    "BaseCalculator",
    "CalculatorFactory",
    "QuantPipeline",
    "PipelineStage",
    "QuantAnalyticsError",
    "DataValidationError",
    "InsufficientDataError",
    "CalculationError",
    "ConvergenceError",
    "ModelFitError",
    "ConfigurationError",
    "DependencyError",
    "validate_symbol",
    "validate_date",
    "validate_required",
    "validate_positive",
    "PortfolioCalculator",
    "DataCleaningPipeline",
    "DataValidator",
    "DataQualityReport",
]
