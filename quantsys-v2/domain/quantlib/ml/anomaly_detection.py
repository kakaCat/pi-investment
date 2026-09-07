"""
Anomaly Detection Calculator
=============================

Market, trading, and data quality anomaly detection for quantitative systems.

Features:
    - Isolation Forest for outlier detection
    - Local Outlier Factor (LOF) for density-based anomalies
    - One-Class SVM for novelty detection
    - Autoencoder for deep anomaly detection
    - Summary statistics and clustering of anomalies

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, List, Tuple
import warnings

from domain.quantlib import BaseCalculator, validate_inputs, timing_decorator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    CalculationError,
    ConfigurationError,
    DependencyError
)

warnings.filterwarnings('ignore', category=UserWarning)


class AnomalyDetectionCalculator(BaseCalculator):
    """
    Multi-method anomaly detection for quantitative data.

    Detects anomalies in market data, trading behavior, and data quality
    using isolation forest, LOF, one-class SVM, and autoencoder methods.

    Example:
        calc = AnomalyDetectionCalculator()
        result = calc.calculate(
            data=market_data_df,
            method='isolation_forest',
            contamination=0.05
        )
        print(f"Anomalies found: {result['value']['anomalies'].sum()}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0,
                 random_state: int = 42):
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)
        self.random_state = random_state
        self._detector = None

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        return self.detect_anomalies(*args, **kwargs)

    def get_supported_methods(self) -> List[str]:
        return ['isolation_forest', 'lof', 'one_class_svm', 'autoencoder',
                'zscore', 'iqr', 'combined']

    @validate_inputs
    @timing_decorator
    def detect_anomalies(self,
                         data: Union[np.ndarray, pd.DataFrame],
                         method: str = 'isolation_forest',
                         contamination: float = 0.05,
                         threshold: Optional[float] = None,
                         features: Optional[List[str]] = None,
                         return_scores: bool = True) -> Dict[str, Any]:
        """
        Detect anomalies in input data.

        Args:
            data: Input data (array or DataFrame) to analyze
            method: Detection method - 'isolation_forest', 'lof', 'one_class_svm',
                    'autoencoder', 'zscore', 'iqr', 'combined'
            contamination: Expected fraction of anomalies (0-1)
            threshold: Detection threshold override (None = auto)
            features: Specific columns to use (if DataFrame)
            return_scores: Whether to return anomaly scores

        Returns:
            Dictionary with:
                - anomalies: Boolean array indicating anomalies
                - scores: Anomaly scores (lower = more anomalous for some methods)
                - threshold: Detection threshold used
                - summary: Summary statistics about detected anomalies
        """
        if data is None:
            raise DataValidationError("Input data is None", field_name="data")

        if isinstance(data, pd.DataFrame) and data.empty:
            raise DataValidationError("Input DataFrame is empty", field_name="data")

        contamination = self._validate_probability(contamination, 'contamination')

        if contamination <= 0 or contamination >= 0.5:
            raise ConfigurationError(
                "contamination should be between 0.001 and 0.5",
                parameter="contamination"
            )

        self.validate_method(method)

        # Prepare data
        X, col_names, original_index = self._prepare_data(data, features)

        if len(X) < 10:
            raise InsufficientDataError(required=10, provided=len(X),
                                        calculation="anomaly_detection")

        # Detect anomalies
        anomalies = None
        scores = None
        used_threshold = threshold

        if method == 'isolation_forest':
            anomalies, scores, used_threshold = self._isolation_forest(
                X, contamination, threshold, return_scores
            )
        elif method == 'lof':
            anomalies, scores, used_threshold = self._local_outlier_factor(
                X, contamination, threshold, return_scores
            )
        elif method == 'one_class_svm':
            anomalies, scores, used_threshold = self._one_class_svm(
                X, contamination, threshold, return_scores
            )
        elif method == 'autoencoder':
            anomalies, scores, used_threshold = self._autoencoder(
                X, contamination, threshold, return_scores
            )
        elif method == 'zscore':
            anomalies, scores, used_threshold = self._zscore_method(
                X, threshold, return_scores
            )
        elif method == 'iqr':
            anomalies, scores, used_threshold = self._iqr_method(
                X, threshold, return_scores
            )
        elif method == 'combined':
            anomalies, scores, used_threshold = self._combined_method(
                X, contamination, threshold, return_scores
            )

        # Generate summary
        summary = self._generate_summary(anomalies, scores, col_names, data)

        return self._create_result_dict(
            value={
                'anomalies': anomalies.tolist() if isinstance(anomalies, np.ndarray) else anomalies,
                'n_anomalies': int(np.sum(anomalies)),
                'n_total': len(anomalies),
                'anomaly_rate': float(np.mean(anomalies)),
            },
            method=f'anomaly_detection_{method}',
            parameters={
                'method': method,
                'contamination': contamination,
                'threshold': used_threshold,
            },
            metadata={
                'scores': scores.tolist() if isinstance(scores, np.ndarray) and return_scores else scores,
                'summary': summary,
            }
        )

    def _prepare_data(self,
                      data: Union[np.ndarray, pd.DataFrame],
                      features: Optional[List[str]]) -> Tuple[np.ndarray, List[str], Any]:
        """Prepare data for anomaly detection."""
        if isinstance(data, pd.DataFrame):
            if features:
                cols = [c for c in features if c in data.columns]
                subset = data[cols] if cols else data
            else:
                cols = data.select_dtypes(include=[np.number]).columns.tolist()
                subset = data[cols] if cols else data

            col_names = list(subset.columns)
            original_index = data.index

            # Convert to numpy, handling NaN
            X = subset.values.astype(float)
        else:
            if isinstance(data, list):
                X = np.array(data, dtype=float)
            else:
                X = np.array(data, dtype=float)

            # Ensure 2D
            if len(X.shape) == 1:
                X = X.reshape(-1, 1)

            col_names = [f'feature_{i}' for i in range(X.shape[1])]
            original_index = None

        # Handle NaN and Inf
        mask = ~(np.isnan(X).any(axis=1) | np.isinf(X).any(axis=1))
        if not mask.all():
            X = X[mask]

        # Standardize
        if X.shape[0] > 1:
            std = np.std(X, axis=0)
            std[std == 0] = 1.0
            mean = np.mean(X, axis=0)
            X = (X - mean) / std

        return X, col_names, original_index

    def _isolation_forest(self,
                          X: np.ndarray,
                          contamination: float,
                          threshold: Optional[float],
                          return_scores: bool) -> Tuple[np.ndarray, np.ndarray, float]:
        """Isolation Forest anomaly detection."""
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            raise DependencyError("scikit-learn", message="Install with: pip install scikit-learn")

        try:
            detector = IsolationForest(
                contamination=contamination,
                random_state=self.random_state,
                n_estimators=100,
                max_samples='auto'
            )
            preds = detector.fit_predict(X)

            # Convert to boolean: -1 = anomaly, 1 = normal
            anomalies = preds == -1

            # Get anomaly scores
            scores = detector.score_samples(X)

            used_threshold = threshold
            if used_threshold is None:
                # Use default threshold based on contamination
                used_threshold = float(np.percentile(scores, contamination * 100))

        except Exception as e:
            raise CalculationError(
                f"Isolation Forest failed: {str(e)}",
                calculation_type="isolation_forest"
            )

        return anomalies, scores, used_threshold

    def _local_outlier_factor(self,
                              X: np.ndarray,
                              contamination: float,
                              threshold: Optional[float],
                              return_scores: bool) -> Tuple[np.ndarray, np.ndarray, float]:
        """Local Outlier Factor anomaly detection."""
        try:
            from sklearn.neighbors import LocalOutlierFactor
        except ImportError:
            raise DependencyError("scikit-learn", message="Install with: pip install scikit-learn")

        try:
            detector = LocalOutlierFactor(
                contamination=contamination,
                n_neighbors=min(20, max(2, len(X) // 5)),
                novelty=False
            )
            preds = detector.fit_predict(X)

            anomalies = preds == -1

            # LOF scores (negative for outliers)
            scores = detector.negative_outlier_factor_

            used_threshold = threshold
            if used_threshold is None:
                used_threshold = float(np.percentile(scores, contamination * 100))

        except Exception as e:
            raise CalculationError(
                f"LOF failed: {str(e)}",
                calculation_type="lof"
            )

        return anomalies, scores, used_threshold

    def _one_class_svm(self,
                       X: np.ndarray,
                       contamination: float,
                       threshold: Optional[float],
                       return_scores: bool) -> Tuple[np.ndarray, np.ndarray, float]:
        """One-Class SVM anomaly detection."""
        try:
            from sklearn.svm import OneClassSVM
        except ImportError:
            raise DependencyError("scikit-learn", message="Install with: pip install scikit-learn")

        try:
            nu = contamination  # nu is equivalent to contamination for OCSVM
            detector = OneClassSVM(
                nu=nu,
                kernel='rbf',
                gamma='scale'
            )
            preds = detector.fit_predict(X)

            anomalies = preds == -1

            # Decision function as scores
            scores = detector.decision_function(X)

            used_threshold = threshold
            if used_threshold is None:
                used_threshold = float(np.percentile(scores, contamination * 100))

        except Exception as e:
            raise CalculationError(
                f"One-Class SVM failed: {str(e)}",
                calculation_type="one_class_svm"
            )

        return anomalies, scores, used_threshold

    def _autoencoder(self,
                     X: np.ndarray,
                     contamination: float,
                     threshold: Optional[float],
                     return_scores: bool) -> Tuple[np.ndarray, np.ndarray, float]:
        """Autoencoder-based anomaly detection."""
        try:
            from sklearn.preprocessing import MinMaxScaler
        except ImportError:
            raise DependencyError("scikit-learn", message="Install with: pip install scikit-learn")

        has_keras = False
        try:
            from tensorflow import keras
            from tensorflow.keras.layers import Dense, Input
            from tensorflow.keras.models import Model
            has_keras = True
        except ImportError:
            try:
                import keras
                from keras.layers import Dense, Input
                from keras.models import Model
                has_keras = True
            except ImportError:
                pass

        if not has_keras:
            # Fall back to Isolation Forest
            return self._isolation_forest(X, contamination, threshold, return_scores)

        n_features = X.shape[1]
        encoding_dim = max(2, n_features // 2)

        try:
            # Build autoencoder
            input_layer = Input(shape=(n_features,))
            encoded = Dense(encoding_dim, activation='relu')(input_layer)
            encoded = Dense(max(2, encoding_dim // 2), activation='relu')(encoded)
            decoded = Dense(encoding_dim, activation='relu')(encoded)
            decoded = Dense(n_features, activation='linear')(decoded)

            autoencoder = Model(input_layer, decoded)
            autoencoder.compile(optimizer='adam', loss='mse')

            autoencoder.fit(
                X, X,
                epochs=30,
                batch_size=min(32, len(X)),
                validation_split=0.2,
                verbose=0
            )

            # Reconstruction error as anomaly score
            X_pred = autoencoder.predict(X, verbose=0)
            reconstruction_error = np.mean((X - X_pred) ** 2, axis=1)

            # Higher reconstruction error = more anomalous
            used_threshold = threshold
            if used_threshold is None:
                used_threshold = float(np.percentile(
                    reconstruction_error, (1 - contamination) * 100
                ))

            anomalies = reconstruction_error > used_threshold
            scores = -reconstruction_error  # Negative so lower = more anomalous

        except Exception:
            # Fall back to simple reconstruction error approach
            return self._isolation_forest(X, contamination, threshold, return_scores)

        return anomalies, scores, used_threshold

    def _zscore_method(self,
                       X: np.ndarray,
                       threshold: Optional[float],
                       return_scores: bool) -> Tuple[np.ndarray, np.ndarray, float]:
        """Z-score based anomaly detection."""
        # Already standardized in _prepare_data
        z_scores = np.abs(X)
        max_z = np.max(z_scores, axis=1)

        used_threshold = threshold if threshold is not None else 3.0
        anomalies = max_z > used_threshold
        scores = -max_z  # Negative so lower = more anomalous

        return anomalies, scores, used_threshold

    def _iqr_method(self,
                    X: np.ndarray,
                    threshold: Optional[float],
                    return_scores: bool) -> Tuple[np.ndarray, np.ndarray, float]:
        """IQR-based anomaly detection."""
        n_features = X.shape[1]
        anomaly_mask = np.zeros(len(X), dtype=bool)
        score_array = np.zeros(len(X))

        used_threshold = threshold if threshold is not None else 1.5

        for i in range(n_features):
            q1 = np.percentile(X[:, i], 25)
            q3 = np.percentile(X[:, i], 75)
            iqr = q3 - q1

            if iqr > 0:
                lower = q1 - used_threshold * iqr
                upper = q3 + used_threshold * iqr
                anomaly_mask |= (X[:, i] < lower) | (X[:, i] > upper)

                # Distance from bounds as score
                dist_lower = np.maximum(0, lower - X[:, i])
                dist_upper = np.maximum(0, X[:, i] - upper)
                score_array += dist_lower + dist_upper

        scores = -score_array
        anomalies = anomaly_mask

        return anomalies, scores, used_threshold

    def _combined_method(self,
                         X: np.ndarray,
                         contamination: float,
                         threshold: Optional[float],
                         return_scores: bool) -> Tuple[np.ndarray, np.ndarray, float]:
        """Ensemble anomaly detection combining multiple methods."""
        methods_results = []

        # Try each method
        method_funcs = [
            ('isolation_forest', self._isolation_forest),
            ('lof', self._local_outlier_factor),
            ('zscore', self._zscore_method),
            ('iqr', self._iqr_method),
        ]

        weights = {
            'isolation_forest': 0.4,
            'lof': 0.3,
            'zscore': 0.15,
            'iqr': 0.15,
        }

        combined_anomalies = np.zeros(len(X), dtype=float)
        used_threshold = threshold if threshold is not None else 0.0

        for method_name, func in method_funcs:
            try:
                if method_name in ['isolation_forest', 'lof']:
                    anom, scores, thresh = func(X, contamination, threshold, return_scores)
                else:
                    anom, scores, thresh = func(X, threshold, return_scores)

                combined_anomalies += weights.get(method_name, 0.1) * anom.astype(float)
                if used_threshold == 0.0:
                    used_threshold = thresh
            except Exception:
                pass

        # Threshold for combined voting: majority
        anomalies = combined_anomalies >= 0.5
        scores = -combined_anomalies  # More votes = less anomalous

        if not np.any(anomalies):
            # Ensure at least some anomalies for very imbalanced cases
            n_anomalies = max(1, int(len(X) * contamination))
            top_idx = np.argsort(scores)[:n_anomalies]
            anomalies[top_idx] = True

        return anomalies, scores, used_threshold

    def _generate_summary(self,
                          anomalies: np.ndarray,
                          scores: np.ndarray,
                          col_names: List[str],
                          original_data: Union[np.ndarray, pd.DataFrame]) -> Dict[str, Any]:
        """Generate summary statistics about detected anomalies."""
        n_total = len(anomalies)
        n_anomaly = int(np.sum(anomalies))
        anomaly_rate = float(n_anomaly / n_total) if n_total > 0 else 0.0

        summary = {
            'n_total': n_total,
            'n_anomalies': n_anomaly,
            'anomaly_rate': anomaly_rate,
            'anomaly_indices': np.where(anomalies)[0].tolist()[:20],  # Top 20
        }

        if scores is not None and len(scores) > 0:
            summary['score_stats'] = {
                'mean': float(np.mean(scores)),
                'std': float(np.std(scores)),
                'min': float(np.min(scores)),
                'max': float(np.max(scores)),
                'median': float(np.median(scores)),
            }

        # Feature-level contribution to anomalies
        if isinstance(original_data, pd.DataFrame) and n_anomaly > 0:
            feature_contributions = {}
            normal_data = original_data.iloc[~anomalies] if isinstance(anomalies, np.ndarray) else original_data
            anomaly_data = original_data.iloc[anomalies] if isinstance(anomalies, np.ndarray) else original_data

            if not normal_data.empty and not anomaly_data.empty:
                for col in original_data.select_dtypes(include=[np.number]).columns:
                    normal_mean = normal_data[col].mean()
                    normal_std = normal_data[col].std()
                    if normal_std > 0:
                        anomaly_deviation = np.abs(
                            (anomaly_data[col].mean() - normal_mean) / normal_std
                        )
                        feature_contributions[col] = float(anomaly_deviation)

            # Sort by contribution
            if feature_contributions:
                sorted_contribs = sorted(
                    feature_contributions.items(),
                    key=lambda x: x[1], reverse=True
                )
                summary['feature_contributions'] = dict(sorted_contribs[:10])

        return summary
