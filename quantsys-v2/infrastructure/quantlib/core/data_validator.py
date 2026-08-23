"""
Data Validator Module
=====================

Comprehensive data validation and quality control for quantitative analysis.
Inspired by FinceptTerminal's data validation framework.
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from .exceptions import DataValidationError, InsufficientDataError

logger = logging.getLogger(__name__)


@dataclass
class DataQualityReport:
    """Data quality assessment report."""
    total_records: int
    missing_values: Dict[str, int]
    outliers: Dict[str, int]
    data_types: Dict[str, str]
    date_range: Optional[Tuple[str, str]]
    quality_score: float
    issues: List[str]
    timestamp: str


class DataValidator:
    """
    Comprehensive data validation and quality control.

    Provides methods for validating returns, prices, and other financial data.
    """

    @staticmethod
    def validate_returns_series(
        returns: Union[List, np.ndarray, pd.Series],
        min_length: int = 30,
        max_abs_return: float = 1.0,
        name: str = "returns"
    ) -> np.ndarray:
        """
        Validate returns series for quantitative analysis.

        Args:
            returns: Returns data to validate
            min_length: Minimum required length
            max_abs_return: Maximum absolute return (default 100%)
            name: Name for error messages

        Returns:
            Validated returns as numpy array

        Raises:
            DataValidationError: If validation fails
            InsufficientDataError: If data is too short
        """
        # Convert to numpy array
        if isinstance(returns, pd.Series):
            arr = returns.values
        elif isinstance(returns, list):
            arr = np.array(returns, dtype=float)
        elif isinstance(returns, np.ndarray):
            arr = returns
        else:
            raise DataValidationError(
                f"Unsupported type: {type(returns)}",
                name
            )

        # Check length
        if len(arr) < min_length:
            raise InsufficientDataError(
                required=min_length,
                actual=len(arr),
                message=f"{name} has {len(arr)} points, need at least {min_length}"
            )

        # Check for NaN/Inf
        if np.any(np.isnan(arr)):
            nan_count = np.sum(np.isnan(arr))
            raise DataValidationError(
                f"Contains {nan_count} NaN values",
                name
            )

        if np.any(np.isinf(arr)):
            inf_count = np.sum(np.isinf(arr))
            raise DataValidationError(
                f"Contains {inf_count} infinite values",
                name
            )

        # Check for extreme values
        extreme_mask = np.abs(arr) > max_abs_return
        if np.any(extreme_mask):
            extreme_count = np.sum(extreme_mask)
            max_value = np.max(np.abs(arr))
            logger.warning(
                f"{name} contains {extreme_count} extreme values "
                f"(max: {max_value:.2%}, threshold: {max_abs_return:.2%})"
            )

        return arr

    @staticmethod
    def validate_positive_number(
        value: float,
        name: str = "value",
        allow_zero: bool = False
    ) -> float:
        """
        Validate that a number is positive.

        Args:
            value: Value to validate
            name: Name for error messages
            allow_zero: Whether to allow zero

        Returns:
            Validated value

        Raises:
            DataValidationError: If validation fails
        """
        if value is None:
            raise DataValidationError("Cannot be None", name)

        if not isinstance(value, (int, float)):
            raise DataValidationError(
                f"Must be numeric, got {type(value)}",
                name
            )

        if np.isnan(value) or np.isinf(value):
            raise DataValidationError("Cannot be NaN or Inf", name)

        if allow_zero:
            if value < 0:
                raise DataValidationError(
                    f"Must be non-negative, got {value}",
                    name
                )
        else:
            if value <= 0:
                raise DataValidationError(
                    f"Must be positive, got {value}",
                    name
                )

        return float(value)

    @staticmethod
    def validate_probability(
        prob: float,
        name: str = "probability"
    ) -> float:
        """
        Validate that a value is a valid probability [0, 1].

        Args:
            prob: Probability to validate
            name: Name for error messages

        Returns:
            Validated probability

        Raises:
            DataValidationError: If validation fails
        """
        if prob is None:
            raise DataValidationError("Cannot be None", name)

        if not isinstance(prob, (int, float)):
            raise DataValidationError(
                f"Must be numeric, got {type(prob)}",
                name
            )

        if np.isnan(prob) or np.isinf(prob):
            raise DataValidationError("Cannot be NaN or Inf", name)

        if not (0 <= prob <= 1):
            raise DataValidationError(
                f"Must be in [0, 1], got {prob}",
                name
            )

        return float(prob)

    @staticmethod
    def validate_price_series(
        prices: Union[List, np.ndarray, pd.Series],
        min_length: int = 30,
        name: str = "prices"
    ) -> np.ndarray:
        """
        Validate price series.

        Args:
            prices: Price data to validate
            min_length: Minimum required length
            name: Name for error messages

        Returns:
            Validated prices as numpy array

        Raises:
            DataValidationError: If validation fails
        """
        # Convert to numpy array
        if isinstance(prices, pd.Series):
            arr = prices.values
        elif isinstance(prices, list):
            arr = np.array(prices, dtype=float)
        elif isinstance(prices, np.ndarray):
            arr = prices
        else:
            raise DataValidationError(
                f"Unsupported type: {type(prices)}",
                name
            )

        # Check length
        if len(arr) < min_length:
            raise InsufficientDataError(
                required=min_length,
                actual=len(arr)
            )

        # Check for NaN/Inf
        if np.any(np.isnan(arr)):
            raise DataValidationError("Contains NaN values", name)

        if np.any(np.isinf(arr)):
            raise DataValidationError("Contains infinite values", name)

        # Check for non-positive prices
        if np.any(arr <= 0):
            negative_count = np.sum(arr <= 0)
            raise DataValidationError(
                f"Contains {negative_count} non-positive prices",
                name
            )

        return arr

    @staticmethod
    def detect_outliers(
        data: Union[List, np.ndarray, pd.Series],
        method: str = "iqr",
        threshold: float = 3.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect outliers in data.

        Args:
            data: Data to check
            method: Detection method ('iqr' or 'zscore')
            threshold: Threshold for outlier detection

        Returns:
            Tuple of (outlier_mask, outlier_indices)
        """
        if isinstance(data, pd.Series):
            arr = data.values
        elif isinstance(data, list):
            arr = np.array(data, dtype=float)
        else:
            arr = data

        if method == "iqr":
            q1 = np.percentile(arr, 25)
            q3 = np.percentile(arr, 75)
            iqr = q3 - q1
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr
            outlier_mask = (arr < lower_bound) | (arr > upper_bound)

        elif method == "zscore":
            mean = np.mean(arr)
            std = np.std(arr)
            z_scores = np.abs((arr - mean) / std) if std > 0 else np.zeros_like(arr)
            outlier_mask = z_scores > threshold

        else:
            raise ValueError(f"Unknown method: {method}")

        outlier_indices = np.where(outlier_mask)[0]
        return outlier_mask, outlier_indices

    def generate_quality_report(
        self,
        data: pd.DataFrame,
        date_column: Optional[str] = None
    ) -> DataQualityReport:
        """
        Generate comprehensive data quality report.

        Args:
            data: DataFrame to analyze
            date_column: Name of date column (if any)

        Returns:
            DataQualityReport with quality metrics
        """
        issues = []

        # Basic stats
        total_records = len(data)

        # Missing values
        missing_values = data.isnull().sum().to_dict()
        missing_pct = {k: v / total_records for k, v in missing_values.items() if v > 0}

        if missing_pct:
            issues.append(
                f"Missing values: {', '.join(f'{k}={v:.1%}' for k, v in missing_pct.items())}"
            )

        # Data types
        data_types = {col: str(dtype) for col, dtype in data.dtypes.items()}

        # Outliers (for numeric columns)
        outliers = {}
        for col in data.select_dtypes(include=[np.number]).columns:
            _, outlier_indices = self.detect_outliers(data[col].dropna())
            if len(outlier_indices) > 0:
                outliers[col] = len(outlier_indices)
                outlier_pct = len(outlier_indices) / len(data[col].dropna())
                if outlier_pct > 0.05:  # More than 5% outliers
                    issues.append(f"{col}: {outlier_pct:.1%} outliers")

        # Date range
        date_range = None
        if date_column and date_column in data.columns:
            try:
                dates = pd.to_datetime(data[date_column])
                date_range = (
                    dates.min().strftime("%Y-%m-%d"),
                    dates.max().strftime("%Y-%m-%d")
                )
            except Exception as e:
                issues.append(f"Date parsing error: {e}")

        # Calculate quality score (0-100)
        score = 100.0

        # Penalize missing values
        avg_missing_pct = np.mean(list(missing_pct.values())) if missing_pct else 0
        score -= avg_missing_pct * 50

        # Penalize outliers
        if outliers:
            avg_outlier_pct = np.mean([v / total_records for v in outliers.values()])
            score -= avg_outlier_pct * 30

        score = max(0, min(100, score))

        return DataQualityReport(
            total_records=total_records,
            missing_values=missing_values,
            outliers=outliers,
            data_types=data_types,
            date_range=date_range,
            quality_score=round(score, 2),
            issues=issues,
            timestamp=datetime.now().isoformat()
        )


# Convenience functions

def validate_returns_series(
    returns: Union[List, np.ndarray, pd.Series],
    min_length: int = 30
) -> np.ndarray:
    """Convenience function for validating returns series."""
    return DataValidator.validate_returns_series(returns, min_length)


def validate_positive_number(value: float, name: str = "value") -> float:
    """Convenience function for validating positive numbers."""
    return DataValidator.validate_positive_number(value, name)


def validate_probability(prob: float, name: str = "probability") -> float:
    """Convenience function for validating probabilities."""
    return DataValidator.validate_probability(prob, name)
