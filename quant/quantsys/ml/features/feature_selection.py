"""
Feature selection using various methods.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from sklearn.feature_selection import (
    SelectKBest, f_classif, mutual_info_classif,
    RFE, SelectFromModel
)
import logging

logger = logging.getLogger(__name__)


class FeatureSelector:
    """
    Feature selection using multiple methods:
    - Statistical tests (ANOVA F-test, mutual information)
    - Recursive Feature Elimination (RFE)
    - Model-based selection (feature importance)
    """

    def __init__(self, method: str = 'model_based', n_features: int = 30):
        """
        Args:
            method: 'statistical', 'rfe', 'model_based', or 'combined'
            n_features: Number of features to select
        """
        self.method = method
        self.n_features = n_features
        self.selected_features = None
        self.feature_scores = None

    def select_features(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        model: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Select features using specified method.

        Args:
            X: Feature matrix
            y: Target labels
            feature_names: List of feature names
            model: Optional model for model-based selection

        Returns:
            Dictionary with selected features and scores
        """
        if self.method == 'statistical':
            return self._select_statistical(X, y, feature_names)
        elif self.method == 'rfe':
            return self._select_rfe(X, y, feature_names, model)
        elif self.method == 'model_based':
            return self._select_model_based(X, y, feature_names, model)
        elif self.method == 'combined':
            return self._select_combined(X, y, feature_names, model)
        else:
            raise ValueError(f"Unknown method: {self.method}")

    def _select_statistical(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, Any]:
        """Select features using statistical tests."""
        logger.info("Selecting features using statistical tests...")

        # ANOVA F-test
        selector_f = SelectKBest(f_classif, k=min(self.n_features, X.shape[1]))
        selector_f.fit(X, y)
        f_scores = selector_f.scores_

        # Mutual information
        mi_scores = mutual_info_classif(X, y, random_state=42)

        # Combine scores (normalized)
        f_scores_norm = f_scores / f_scores.max()
        mi_scores_norm = mi_scores / (mi_scores.max() + 1e-10)
        combined_scores = (f_scores_norm + mi_scores_norm) / 2

        # Select top features
        top_indices = np.argsort(combined_scores)[-self.n_features:]
        self.selected_features = [feature_names[i] for i in top_indices]
        self.feature_scores = {
            feature_names[i]: float(combined_scores[i])
            for i in range(len(feature_names))
        }

        logger.info(f"Selected {len(self.selected_features)} features")

        return {
            'selected_features': self.selected_features,
            'feature_scores': self.feature_scores,
            'method': 'statistical'
        }

    def _select_rfe(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        model: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Select features using Recursive Feature Elimination."""
        logger.info("Selecting features using RFE...")

        if model is None:
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(n_estimators=50, random_state=42)

        selector = RFE(model, n_features_to_select=self.n_features, step=1)
        selector.fit(X, y)

        self.selected_features = [
            feature_names[i] for i in range(len(feature_names))
            if selector.support_[i]
        ]

        self.feature_scores = {
            feature_names[i]: float(selector.ranking_[i])
            for i in range(len(feature_names))
        }

        logger.info(f"Selected {len(self.selected_features)} features")

        return {
            'selected_features': self.selected_features,
            'feature_scores': self.feature_scores,
            'method': 'rfe'
        }

    def _select_model_based(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        model: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Select features using model feature importance."""
        logger.info("Selecting features using model-based selection...")

        if model is None:
            import xgboost as xgb
            model = xgb.XGBClassifier(
                max_depth=5,
                n_estimators=100,
                learning_rate=0.1,
                random_state=42
            )

        model.fit(X, y)

        if not hasattr(model, 'feature_importances_'):
            logger.error("Model does not have feature_importances_ attribute")
            return {'error': 'Model does not support feature importance'}

        importances = model.feature_importances_

        # Select top features
        top_indices = np.argsort(importances)[-self.n_features:]
        self.selected_features = [feature_names[i] for i in top_indices]
        self.feature_scores = {
            feature_names[i]: float(importances[i])
            for i in range(len(feature_names))
        }

        logger.info(f"Selected {len(self.selected_features)} features")

        return {
            'selected_features': self.selected_features,
            'feature_scores': self.feature_scores,
            'method': 'model_based'
        }

    def _select_combined(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        model: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Select features using combined methods."""
        logger.info("Selecting features using combined methods...")

        # Get scores from all methods
        stat_result = self._select_statistical(X, y, feature_names)
        model_result = self._select_model_based(X, y, feature_names, model)

        # Normalize and combine scores
        stat_scores = np.array([stat_result['feature_scores'][name] for name in feature_names])
        model_scores = np.array([model_result['feature_scores'][name] for name in feature_names])

        stat_scores_norm = stat_scores / (stat_scores.max() + 1e-10)
        model_scores_norm = model_scores / (model_scores.max() + 1e-10)

        combined_scores = (stat_scores_norm + model_scores_norm) / 2

        # Select top features
        top_indices = np.argsort(combined_scores)[-self.n_features:]
        self.selected_features = [feature_names[i] for i in top_indices]
        self.feature_scores = {
            feature_names[i]: float(combined_scores[i])
            for i in range(len(feature_names))
        }

        logger.info(f"Selected {len(self.selected_features)} features")

        return {
            'selected_features': self.selected_features,
            'feature_scores': self.feature_scores,
            'method': 'combined'
        }

    def transform(self, X: np.ndarray, feature_names: List[str]) -> np.ndarray:
        """Transform feature matrix to selected features only."""
        if self.selected_features is None:
            raise ValueError("No features selected. Run select_features() first.")

        selected_indices = [
            i for i, name in enumerate(feature_names)
            if name in self.selected_features
        ]

        return X[:, selected_indices]

    def get_feature_ranking(self) -> List[tuple]:
        """Get features ranked by importance."""
        if self.feature_scores is None:
            return []

        return sorted(
            self.feature_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
