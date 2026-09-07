"""
Feature Engineering Module

Handles feature extraction, transformation, and selection
based on the new factor calculator framework.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, RobustScaler

from infrastructure.quantlib.adapters import get_factor_adapter

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Feature engineering for ML pipeline.

    Extracts features from FactorRegistry, handles missing values,
    performs scaling, and provides feature selection capabilities.
    """

    def __init__(self, scaler_type: str = "standard"):
        """
        Initialize FeatureEngineer.

        Args:
            scaler_type: "standard" (StandardScaler) or "robust" (RobustScaler)
        """
        self.scaler_type = scaler_type
        self.scaler = None
        self.feature_names: list[str] = []
        self.selected_features: list[str] | None = None
        self.factor_adapter = get_factor_adapter()

    def extract_features(
        self,
        klines_dict: dict[str, list[dict]],
        factor_names: list[str] | None = None
    ) -> pd.DataFrame:
        """
        Extract features from klines data using FactorRegistry.

        Args:
            klines_dict: Dict mapping symbol to list of kline dicts
            factor_names: List of factor names to calculate. If None, uses all registered factors.

        Returns:
            DataFrame with columns: symbol, date, factor1, factor2, ...
        """
        if factor_names is None:
            # Get all registered factors
            factor_names = self.factor_adapter.names()

        logger.info(f"Extracting {len(factor_names)} features for {len(klines_dict)} symbols")

        rows = []
        for symbol, klines in klines_dict.items():
            if not klines:
                continue

            # Calculate all factors for this symbol
            factors = self.factor_adapter.calculate_batch(factor_names, klines)

            # Get the latest date
            latest_date = klines[-1].get("date", klines[-1].get("trade_date", ""))

            row = {
                "symbol": symbol,
                "date": latest_date,
                **factors
            }
            rows.append(row)

        df = pd.DataFrame(rows)

        # Store feature names (exclude symbol and date)
        self.feature_names = [col for col in df.columns if col not in ["symbol", "date"]]

        logger.info(f"Extracted features shape: {df.shape}")
        logger.info(f"Features with missing values: {df[self.feature_names].isnull().sum().sum()}")

        return df

    def prepare_features(
        self,
        df: pd.DataFrame,
        handle_missing: str = "drop",
        fit_scaler: bool = True
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare features for training/prediction.

        Args:
            df: DataFrame with features (from extract_features)
            handle_missing: "drop" (drop rows with NaN) or "fill" (fill with median)
            fit_scaler: Whether to fit the scaler (True for training, False for prediction)

        Returns:
            Tuple of (metadata_df, features_df)
            - metadata_df: symbol, date columns
            - features_df: scaled feature values
        """
        # Separate metadata and features
        metadata_cols = ["symbol", "date"]
        metadata_df = df[metadata_cols].copy()
        features_df = df[self.feature_names].copy()

        # Handle missing values
        if handle_missing == "drop":
            # Drop rows with any NaN
            valid_mask = ~features_df.isnull().any(axis=1)
            features_df = features_df[valid_mask]
            metadata_df = metadata_df[valid_mask]
            logger.info(f"Dropped {(~valid_mask).sum()} rows with missing values")
        elif handle_missing == "fill":
            # Fill with median (fix pandas FutureWarning)
            features_df = features_df.fillna(features_df.median()).infer_objects(copy=False)

            # Handle columns that are entirely NaN (median is also NaN)
            features_df = features_df.fillna(0.0)

            # Replace inf values that may come from division errors
            import numpy as np
            features_df = features_df.replace([np.inf, -np.inf], 0.0)

            # Final validation
            if features_df.isnull().any().any():
                null_cols = features_df.columns[features_df.isnull().any()].tolist()
                logger.error(f"NaN values still present in columns: {null_cols}")
                raise ValueError(f"Features contain NaN after cleaning: {null_cols}")

            if np.isinf(features_df.values).any():
                logger.error("Inf values still present after cleaning!")
                raise ValueError("Features contain inf after cleaning")

            logger.info("Filled missing values with median, replaced inf with 0")

        # Apply feature selection if configured
        if self.selected_features is not None:
            features_df = features_df[self.selected_features]
            logger.info(f"Applied feature selection: {len(self.selected_features)} features")

        # Scale features
        if fit_scaler:
            if self.scaler_type == "standard":
                self.scaler = StandardScaler()
            elif self.scaler_type == "robust":
                self.scaler = RobustScaler()
            else:
                raise ValueError(f"Unknown scaler type: {self.scaler_type}")

            scaled_values = self.scaler.fit_transform(features_df)
            logger.info(f"Fitted {self.scaler_type} scaler")
        else:
            if self.scaler is None:
                raise ValueError("Scaler not fitted. Call with fit_scaler=True first.")
            scaled_values = self.scaler.transform(features_df)

        # Create scaled DataFrame
        scaled_df = pd.DataFrame(
            scaled_values,
            columns=features_df.columns,
            index=features_df.index
        )

        return metadata_df.reset_index(drop=True), scaled_df.reset_index(drop=True)

    def select_features_by_correlation(
        self,
        df: pd.DataFrame,
        target: pd.Series,
        threshold: float = 0.05,
        max_features: int | None = None
    ) -> list[str]:
        """
        Select features based on correlation with target.

        Args:
            df: Feature DataFrame
            target: Target series
            threshold: Minimum absolute correlation to keep feature
            max_features: Maximum number of features to select

        Returns:
            List of selected feature names
        """
        features_df = df[self.feature_names].copy()

        # Calculate correlations
        correlations = {}
        for col in features_df.columns:
            # Drop NaN for correlation calculation
            valid_mask = ~(features_df[col].isnull() | target.isnull())
            if valid_mask.sum() < 10:  # Need at least 10 samples
                continue
            corr = np.corrcoef(features_df.loc[valid_mask, col], target[valid_mask])[0, 1]
            if not np.isnan(corr):
                correlations[col] = abs(corr)

        # Sort by absolute correlation
        sorted_features = sorted(correlations.items(), key=lambda x: x[1], reverse=True)

        # Filter by threshold
        selected = [name for name, corr in sorted_features if corr >= threshold]

        # Limit to max_features
        if max_features is not None:
            selected = selected[:max_features]

        logger.info(f"Selected {len(selected)} features by correlation (threshold={threshold})")
        if selected:
            logger.info(f"Top 5 features: {selected[:5]}")

        self.selected_features = selected
        return selected

    def select_features_by_importance(
        self,
        feature_importance: dict[str, float],
        threshold: float = 0.01,
        max_features: int | None = None
    ) -> list[str]:
        """
        Select features based on model feature importance.

        Args:
            feature_importance: Dict mapping feature name to importance score
            threshold: Minimum importance to keep feature
            max_features: Maximum number of features to select

        Returns:
            List of selected feature names
        """
        # Sort by importance
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Filter by threshold
        selected = [name for name, imp in sorted_features if imp >= threshold]

        # Limit to max_features
        if max_features is not None:
            selected = selected[:max_features]

        logger.info(f"Selected {len(selected)} features by importance (threshold={threshold})")
        if selected:
            logger.info(f"Top 5 features: {selected[:5]}")

        self.selected_features = selected
        return selected

    def get_feature_stats(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Get statistics about features.

        Args:
            df: Feature DataFrame

        Returns:
            Dict with feature statistics
        """
        features_df = df[self.feature_names]

        stats = {
            "total_features": len(self.feature_names),
            "selected_features": len(self.selected_features) if self.selected_features else None,
            "missing_values": features_df.isnull().sum().to_dict(),
            "missing_rate": (features_df.isnull().sum() / len(features_df)).to_dict(),
            "feature_names": self.feature_names,
            "selected_feature_names": self.selected_features
        }

        return stats
