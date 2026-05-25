"""
Feature importance analysis and visualization.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureImportanceAnalyzer:
    """
    Analyze and visualize feature importance from trained models.
    """

    def __init__(self):
        self.importance_scores = None
        self.feature_names = None

    def analyze(
        self,
        model: Any,
        feature_names: List[str],
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Analyze feature importance from model.

        Args:
            model: Trained model with feature_importances_ attribute
            feature_names: List of feature names
            X: Optional feature matrix for permutation importance
            y: Optional target labels for permutation importance

        Returns:
            Dictionary with importance scores and rankings
        """
        self.feature_names = feature_names

        # Get model-based importance
        if hasattr(model, 'feature_importances_'):
            self.importance_scores = model.feature_importances_
        else:
            logger.warning("Model does not have feature_importances_ attribute")
            self.importance_scores = np.zeros(len(feature_names))

        # Create importance dataframe
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': self.importance_scores
        }).sort_values('importance', ascending=False)

        # Calculate statistics
        top_10_features = importance_df.head(10)['feature'].tolist()
        top_10_importance = importance_df.head(10)['importance'].tolist()

        # Permutation importance (if data provided)
        permutation_importance = None
        if X is not None and y is not None:
            permutation_importance = self._calculate_permutation_importance(model, X, y)

        result = {
            'feature_importance': importance_df.to_dict('records'),
            'top_10_features': top_10_features,
            'top_10_importance': [float(x) for x in top_10_importance],
            'total_features': len(feature_names),
            'importance_sum': float(self.importance_scores.sum()),
            'importance_mean': float(self.importance_scores.mean()),
            'importance_std': float(self.importance_scores.std())
        }

        if permutation_importance is not None:
            result['permutation_importance'] = permutation_importance

        return result

    def _calculate_permutation_importance(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        n_repeats: int = 10
    ) -> Dict[str, Any]:
        """Calculate permutation importance."""
        from sklearn.inspection import permutation_importance

        logger.info("Calculating permutation importance...")

        perm_importance = permutation_importance(
            model, X, y,
            n_repeats=n_repeats,
            random_state=42,
            n_jobs=1
        )

        perm_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance_mean': perm_importance.importances_mean,
            'importance_std': perm_importance.importances_std
        }).sort_values('importance_mean', ascending=False)

        return {
            'feature_importance': perm_df.to_dict('records'),
            'top_10_features': perm_df.head(10)['feature'].tolist()
        }

    def plot_importance(
        self,
        top_n: int = 20,
        save_path: Optional[str] = None
    ):
        """Plot feature importance."""
        if self.importance_scores is None or self.feature_names is None:
            logger.error("No importance scores available")
            return

        try:
            import matplotlib.pyplot as plt

            # Create dataframe
            importance_df = pd.DataFrame({
                'feature': self.feature_names,
                'importance': self.importance_scores
            }).sort_values('importance', ascending=False).head(top_n)

            # Plot
            plt.figure(figsize=(10, 8))
            plt.barh(range(len(importance_df)), importance_df['importance'])
            plt.yticks(range(len(importance_df)), importance_df['feature'])
            plt.xlabel('Importance')
            plt.title(f'Top {top_n} Feature Importance')
            plt.gca().invert_yaxis()
            plt.tight_layout()

            if save_path:
                plt.savefig(save_path)
                logger.info(f"Feature importance plot saved to {save_path}")
            else:
                plt.show()

        except ImportError:
            logger.warning("matplotlib not available for plotting")

    def get_top_features(self, n: int = 10) -> List[str]:
        """Get top N most important features."""
        if self.importance_scores is None or self.feature_names is None:
            return []

        indices = np.argsort(self.importance_scores)[-n:][::-1]
        return [self.feature_names[i] for i in indices]

    def get_feature_groups(self, threshold: float = 0.01) -> Dict[str, List[str]]:
        """
        Group features by importance level.

        Args:
            threshold: Minimum importance threshold

        Returns:
            Dictionary with feature groups
        """
        if self.importance_scores is None or self.feature_names is None:
            return {}

        high_importance = []
        medium_importance = []
        low_importance = []

        max_importance = self.importance_scores.max()

        for name, score in zip(self.feature_names, self.importance_scores):
            if score >= max_importance * 0.5:
                high_importance.append(name)
            elif score >= threshold:
                medium_importance.append(name)
            else:
                low_importance.append(name)

        return {
            'high_importance': high_importance,
            'medium_importance': medium_importance,
            'low_importance': low_importance
        }
