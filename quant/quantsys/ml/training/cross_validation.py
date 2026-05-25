"""
Time Series Cross-Validation for stock prediction models.

CRITICAL: Stock data has temporal dependencies. We MUST use time-aware splits
to avoid look-ahead bias and data leakage.
"""
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from typing import Tuple, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TimeSeriesCV:
    """
    Time series cross-validation with walk-forward analysis.

    Ensures training data always comes before test data to prevent look-ahead bias.
    """

    def __init__(self, n_splits: int = 5, test_size: int = None, gap: int = 0):
        """
        Args:
            n_splits: Number of splits for cross-validation
            test_size: Size of test set (if None, uses equal splits)
            gap: Number of samples to exclude between train and test (prevents data leakage)
        """
        self.n_splits = n_splits
        self.test_size = test_size
        self.gap = gap
        self.tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size, gap=gap)

    def split(self, X: np.ndarray, y: np.ndarray = None) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate time series splits.

        Returns:
            List of (train_indices, test_indices) tuples
        """
        return list(self.tscv.split(X, y))

    def validate_model(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        metrics: List[str] = ['accuracy', 'precision', 'recall', 'f1', 'auc']
    ) -> Dict[str, Any]:
        """
        Perform time series cross-validation and return metrics.

        Args:
            model: Sklearn-compatible model with fit() and predict() methods
            X: Feature matrix (n_samples, n_features)
            y: Target labels (n_samples,)
            metrics: List of metrics to compute

        Returns:
            Dictionary with CV scores and statistics
        """
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score,
            f1_score, roc_auc_score, confusion_matrix
        )

        scores = {metric: [] for metric in metrics}
        fold_results = []

        for fold_idx, (train_idx, test_idx) in enumerate(self.tscv.split(X, y)):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            # Train model on this fold
            model.fit(X_train, y_train)

            # Predict on test set
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else None

            # Calculate metrics
            fold_metrics = {}

            if 'accuracy' in metrics:
                fold_metrics['accuracy'] = accuracy_score(y_test, y_pred)

            if 'precision' in metrics:
                fold_metrics['precision'] = precision_score(y_test, y_pred, zero_division=0)

            if 'recall' in metrics:
                fold_metrics['recall'] = recall_score(y_test, y_pred, zero_division=0)

            if 'f1' in metrics:
                fold_metrics['f1'] = f1_score(y_test, y_pred, zero_division=0)

            if 'auc' in metrics and y_pred_proba is not None:
                try:
                    fold_metrics['auc'] = roc_auc_score(y_test, y_pred_proba)
                except ValueError:
                    fold_metrics['auc'] = 0.0

            # Store fold results
            for metric in metrics:
                if metric in fold_metrics:
                    scores[metric].append(fold_metrics[metric])

            fold_results.append({
                'fold': fold_idx + 1,
                'train_size': len(train_idx),
                'test_size': len(test_idx),
                'metrics': fold_metrics,
                'confusion_matrix': confusion_matrix(y_test, y_pred).tolist()
            })

            logger.info(
                f"Fold {fold_idx + 1}/{self.n_splits}: "
                f"Train={len(train_idx)}, Test={len(test_idx)}, "
                f"Accuracy={fold_metrics.get('accuracy', 0):.3f}"
            )

        # Calculate statistics
        cv_results = {
            'n_splits': self.n_splits,
            'fold_results': fold_results,
            'mean_scores': {},
            'std_scores': {},
            'min_scores': {},
            'max_scores': {}
        }

        for metric in metrics:
            if scores[metric]:
                cv_results['mean_scores'][metric] = float(np.mean(scores[metric]))
                cv_results['std_scores'][metric] = float(np.std(scores[metric]))
                cv_results['min_scores'][metric] = float(np.min(scores[metric]))
                cv_results['max_scores'][metric] = float(np.max(scores[metric]))

        return cv_results

    def get_train_test_split(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_ratio: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Get a single time-aware train/test split.

        Args:
            X: Feature matrix
            y: Target labels
            test_ratio: Ratio of data to use for testing

        Returns:
            X_train, X_test, y_train, y_test
        """
        split_idx = int(len(X) * (1 - test_ratio))

        X_train = X[:split_idx]
        X_test = X[split_idx:]
        y_train = y[:split_idx]
        y_test = y[split_idx:]

        logger.info(
            f"Time-aware split: Train={len(X_train)} ({len(X_train)/len(X)*100:.1f}%), "
            f"Test={len(X_test)} ({len(X_test)/len(X)*100:.1f}%)"
        )

        return X_train, X_test, y_train, y_test


def print_cv_results(cv_results: Dict[str, Any]) -> None:
    """Pretty print cross-validation results."""
    print("\n" + "="*60)
    print("TIME SERIES CROSS-VALIDATION RESULTS")
    print("="*60)
    print(f"Number of folds: {cv_results['n_splits']}")
    print("\nMean Scores (± std):")
    print("-"*60)

    for metric, mean_score in cv_results['mean_scores'].items():
        std_score = cv_results['std_scores'][metric]
        min_score = cv_results['min_scores'][metric]
        max_score = cv_results['max_scores'][metric]
        print(f"{metric:12s}: {mean_score:.4f} ± {std_score:.4f}  (min={min_score:.4f}, max={max_score:.4f})")

    print("\nPer-Fold Results:")
    print("-"*60)
    for fold_result in cv_results['fold_results']:
        fold_num = fold_result['fold']
        train_size = fold_result['train_size']
        test_size = fold_result['test_size']
        metrics = fold_result['metrics']

        print(f"\nFold {fold_num}: Train={train_size}, Test={test_size}")
        for metric, score in metrics.items():
            print(f"  {metric}: {score:.4f}")

    print("="*60 + "\n")
