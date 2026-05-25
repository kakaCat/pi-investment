"""Data quality validation module.

This module checks for data quality issues like missing values, outliers,
suspended trading days, and other anomalies in stock data.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np


class DataValidator:
    """Validate stock data quality and detect anomalies."""

    def __init__(
        self,
        missing_threshold: float = 0.1,
        outlier_std: float = 5.0,
    ):
        """Initialize data validator.

        Args:
            missing_threshold: Maximum allowed ratio of missing values (0-1)
            outlier_std: Number of standard deviations for outlier detection
        """
        self.missing_threshold = missing_threshold
        self.outlier_std = outlier_std

    def validate(self, df: pd.DataFrame) -> dict:
        """Run all validation checks on a DataFrame.

        Args:
            df: DataFrame with stock data

        Returns:
            Dict with validation results: {
                "is_valid": bool,
                "missing_values": dict,
                "outliers": dict,
                "suspended_days": list,
                "errors": list[str],
                "warnings": list[str]
            }
        """
        errors = []
        warnings = []

        # Check for missing values
        missing_result = self.check_missing_values(df)
        if missing_result["has_missing"]:
            if missing_result["missing_ratio"] > self.missing_threshold:
                errors.append(
                    f"Missing value ratio {missing_result['missing_ratio']:.2%} "
                    f"exceeds threshold {self.missing_threshold:.2%}"
                )
            else:
                warnings.append(f"Found missing values: {missing_result['missing_columns']}")

        # Check for outliers
        outlier_result = self.detect_outliers(df)
        if outlier_result["has_outliers"]:
            warnings.append(
                f"Found {outlier_result['outlier_count']} outliers in "
                f"{outlier_result['outlier_columns']}"
            )

        # Check for suspended trading
        suspended_result = self.detect_suspended_days(df)
        if suspended_result["has_suspended"]:
            warnings.append(
                f"Found {len(suspended_result['suspended_days'])} suspended trading days"
            )

        # Check for duplicate dates
        duplicate_result = self.check_duplicates(df)
        if duplicate_result["has_duplicates"]:
            errors.append(
                f"Found {duplicate_result['duplicate_count']} duplicate dates"
            )

        # Check data continuity
        continuity_result = self.check_continuity(df)
        if continuity_result["has_gaps"]:
            warnings.append(
                f"Found {continuity_result['gap_count']} date gaps "
                f"(max gap: {continuity_result['max_gap_days']} days)"
            )

        return {
            "is_valid": len(errors) == 0,
            "missing_values": missing_result,
            "outliers": outlier_result,
            "suspended_days": suspended_result,
            "duplicates": duplicate_result,
            "continuity": continuity_result,
            "errors": errors,
            "warnings": warnings,
        }

    def check_missing_values(self, df: pd.DataFrame) -> dict:
        """Check for missing values in critical columns.

        Args:
            df: DataFrame to check

        Returns:
            Dict with missing value statistics
        """
        if df.empty:
            return {
                "has_missing": False,
                "missing_ratio": 0.0,
                "missing_columns": [],
                "missing_counts": {},
            }

        critical_cols = ["date", "open", "high", "low", "close"]
        available_cols = [col for col in critical_cols if col in df.columns]

        missing_counts = {}
        for col in available_cols:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                missing_counts[col] = missing_count

        total_values = len(df) * len(available_cols)
        total_missing = sum(missing_counts.values())
        missing_ratio = total_missing / total_values if total_values > 0 else 0.0

        return {
            "has_missing": len(missing_counts) > 0,
            "missing_ratio": missing_ratio,
            "missing_columns": list(missing_counts.keys()),
            "missing_counts": missing_counts,
        }

    def detect_outliers(
        self,
        df: pd.DataFrame,
        columns: Optional[list[str]] = None,
    ) -> dict:
        """Detect outliers using z-score method.

        Args:
            df: DataFrame to check
            columns: Columns to check (default: price columns)

        Returns:
            Dict with outlier detection results
        """
        if df.empty:
            return {
                "has_outliers": False,
                "outlier_count": 0,
                "outlier_columns": [],
                "outlier_indices": [],
            }

        if columns is None:
            columns = ["open", "high", "low", "close"]

        available_cols = [col for col in columns if col in df.columns]
        if not available_cols:
            return {
                "has_outliers": False,
                "outlier_count": 0,
                "outlier_columns": [],
                "outlier_indices": [],
            }

        outlier_indices = set()
        outlier_columns = []

        for col in available_cols:
            values = df[col]
            if values.isna().all() or len(values.dropna()) < 3:
                continue

            mean = values.mean()
            std = values.std()

            if std == 0 or pd.isna(std):
                continue

            z_scores = np.abs((values - mean) / std)
            col_outliers = df[z_scores > self.outlier_std].index.tolist()

            if col_outliers:
                outlier_columns.append(col)
                outlier_indices.update(col_outliers)

        return {
            "has_outliers": len(outlier_indices) > 0,
            "outlier_count": len(outlier_indices),
            "outlier_columns": outlier_columns,
            "outlier_indices": sorted(list(outlier_indices)),
        }

    def detect_suspended_days(self, df: pd.DataFrame) -> dict:
        """Detect suspended trading days (volume = 0 or amount = 0).

        Args:
            df: DataFrame with volume/amount data

        Returns:
            Dict with suspended day detection results
        """
        if df.empty or "volume" not in df.columns:
            return {
                "has_suspended": False,
                "suspended_days": [],
                "suspended_count": 0,
            }

        # Suspended if volume is 0 or very close to 0
        suspended_mask = (df["volume"].fillna(0) < 1e-6)

        if "amount" in df.columns:
            suspended_mask |= (df["amount"].fillna(0) < 1e-6)

        suspended_indices = df[suspended_mask].index.tolist()
        suspended_dates = []

        if "date" in df.columns:
            suspended_dates = df.loc[suspended_indices, "date"].tolist()

        return {
            "has_suspended": len(suspended_indices) > 0,
            "suspended_days": suspended_dates,
            "suspended_count": len(suspended_indices),
        }

    def check_duplicates(self, df: pd.DataFrame) -> dict:
        """Check for duplicate dates.

        Args:
            df: DataFrame with date column

        Returns:
            Dict with duplicate detection results
        """
        if df.empty or "date" not in df.columns:
            return {
                "has_duplicates": False,
                "duplicate_count": 0,
                "duplicate_dates": [],
            }

        duplicates = df[df.duplicated(subset=["date"], keep=False)]
        duplicate_dates = duplicates["date"].unique().tolist()

        return {
            "has_duplicates": len(duplicate_dates) > 0,
            "duplicate_count": len(duplicate_dates),
            "duplicate_dates": duplicate_dates,
        }

    def check_continuity(self, df: pd.DataFrame, max_gap_days: int = 10) -> dict:
        """Check for date gaps in the data.

        Args:
            df: DataFrame with date column
            max_gap_days: Maximum allowed gap in days

        Returns:
            Dict with continuity check results
        """
        if df.empty or "date" not in df.columns or len(df) < 2:
            return {
                "has_gaps": False,
                "gap_count": 0,
                "max_gap_days": 0,
                "gaps": [],
            }

        # Convert date to datetime (support mixed formats)
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], format='mixed', errors='coerce')
        df = df.sort_values("date").reset_index(drop=True)

        # Calculate gaps
        df["date_diff"] = df["date"].diff().dt.days

        # Find gaps (excluding weekends, approximately)
        # A gap > 5 days is suspicious (weekend + holidays)
        gaps = df[df["date_diff"] > 5].copy()

        gap_list = []
        for _, row in gaps.iterrows():
            gap_list.append({
                "date": row["date"],
                "gap_days": int(row["date_diff"]),
            })

        max_gap = int(df["date_diff"].max()) if not df["date_diff"].isna().all() else 0

        return {
            "has_gaps": len(gap_list) > 0,
            "gap_count": len(gap_list),
            "max_gap_days": max_gap,
            "gaps": gap_list,
        }

    def check_price_consistency(self, df: pd.DataFrame) -> dict:
        """Check if OHLC prices are consistent (high >= low, etc).

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dict with consistency check results
        """
        if df.empty:
            return {
                "is_consistent": True,
                "inconsistent_count": 0,
                "inconsistent_indices": [],
            }

        required_cols = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            return {
                "is_consistent": True,
                "inconsistent_count": 0,
                "inconsistent_indices": [],
            }

        # Check: high >= low
        invalid_high_low = df[df["high"] < df["low"]].index.tolist()

        # Check: high >= open, close
        invalid_high_open = df[df["high"] < df["open"]].index.tolist()
        invalid_high_close = df[df["high"] < df["close"]].index.tolist()

        # Check: low <= open, close
        invalid_low_open = df[df["low"] > df["open"]].index.tolist()
        invalid_low_close = df[df["low"] > df["close"]].index.tolist()

        all_invalid = set(
            invalid_high_low
            + invalid_high_open
            + invalid_high_close
            + invalid_low_open
            + invalid_low_close
        )

        return {
            "is_consistent": len(all_invalid) == 0,
            "inconsistent_count": len(all_invalid),
            "inconsistent_indices": sorted(list(all_invalid)),
        }

    def fix_missing_values(
        self,
        df: pd.DataFrame,
        method: str = "ffill",
    ) -> pd.DataFrame:
        """Fill missing values using specified method.

        Args:
            df: DataFrame with missing values
            method: "ffill" (forward fill), "bfill" (backward fill), "interpolate"

        Returns:
            DataFrame with missing values filled
        """
        if df.empty:
            return df.copy()

        result = df.copy()
        price_cols = ["open", "high", "low", "close"]
        available_cols = [col for col in price_cols if col in result.columns]

        if method == "ffill":
            result[available_cols] = result[available_cols].ffill()
        elif method == "bfill":
            result[available_cols] = result[available_cols].bfill()
        elif method == "interpolate":
            result[available_cols] = result[available_cols].interpolate(method="linear")
        else:
            raise ValueError(f"Invalid method: {method}")

        return result

    def remove_outliers(
        self,
        df: pd.DataFrame,
        columns: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Remove rows with outliers.

        Args:
            df: DataFrame to clean
            columns: Columns to check for outliers

        Returns:
            DataFrame with outliers removed
        """
        if df.empty:
            return df.copy()

        outlier_result = self.detect_outliers(df, columns)
        if not outlier_result["has_outliers"]:
            return df.copy()

        # Remove rows with outliers
        clean_df = df.drop(index=outlier_result["outlier_indices"])
        return clean_df.reset_index(drop=True)
