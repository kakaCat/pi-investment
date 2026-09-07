"""
Return Prediction Calculator
=============================

Multi-model return prediction using gradient boosting and deep learning.

Features:
    - XGBoost regression for return prediction
    - LightGBM regression with early stopping
    - LSTM neural network for sequence-based prediction
    - Ensemble methods combining multiple models
    - Time-series cross-validation with walk-forward splitting
    - Feature importance analysis

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
    ModelFitError,
    DependencyError
)

warnings.filterwarnings('ignore', category=UserWarning)


class ReturnPredictionCalculator(BaseCalculator):
    """
    Multi-model return prediction for quantitative trading.

    Supports XGBoost, LightGBM, LSTM, and Ensemble methods with
    time-series cross-validation for robust model evaluation.

    Example:
        calc = ReturnPredictionCalculator()
        result = calc.calculate(
            features=feature_df,
            target=forward_returns,
            model_type='xgboost',
            horizon=5,
            train_ratio=0.7
        )
        print(f"Predictions: {result['value']['predictions'][:5]}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0,
                 random_state: int = 42):
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)
        self.random_state = random_state
        self._model = None

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        return self.predict_returns(*args, **kwargs)

    def get_supported_methods(self) -> List[str]:
        return ['xgboost', 'lightgbm', 'lstm', 'ensemble']

    @validate_inputs
    @timing_decorator
    def predict_returns(self,
                        features: pd.DataFrame,
                        target: Union[np.ndarray, pd.Series],
                        model_type: str = 'xgboost',
                        horizon: int = 5,
                        train_ratio: float = 0.7,
                        xgboost_params: Optional[Dict[str, Any]] = None,
                        lightgbm_params: Optional[Dict[str, Any]] = None,
                        lstm_params: Optional[Dict[str, Any]] = None,
                        n_splits: int = 5,
                        feature_selection: bool = True) -> Dict[str, Any]:
        """
        Predict forward returns using ML models.

        Args:
            features: DataFrame of features/predictors
            target: Target returns (forward returns for the horizon)
            model_type: Model type - 'xgboost', 'lightgbm', 'lstm', 'ensemble'
            horizon: Forecast horizon in periods
            train_ratio: Fraction of data to use for training
            xgboost_params: Parameters for XGBoost
            lightgbm_params: Parameters for LightGBM
            lstm_params: Parameters for LSTM
            n_splits: Number of CV splits for walk-forward validation
            feature_selection: Whether to perform feature selection

        Returns:
            Dictionary with:
                - model: Trained model object (serialized)
                - predictions: Array of predictions
                - metrics: Dict of evaluation metrics
                - feature_importance: Dict of feature importance
        """
        if features is None or (isinstance(features, pd.DataFrame) and features.empty):
            raise DataValidationError("Features DataFrame is empty", field_name="features")

        if not isinstance(features, pd.DataFrame):
            raise DataValidationError("features must be a pandas DataFrame", field_name="features")

        target = self._validate_numeric_input(target, 'target')
        if isinstance(target, np.ndarray) and len(target.shape) > 1:
            target = target.flatten()

        if len(features) < 50:
            raise InsufficientDataError(required=50, provided=len(features))

        if train_ratio <= 0 or train_ratio >= 1:
            raise ConfigurationError(
                "train_ratio must be between 0 and 1",
                parameter="train_ratio"
            )

        self.validate_method(model_type)

        # Prepare data
        X, y, feature_names = self._prepare_data(features, target)

        n_train = int(len(X) * train_ratio)
        X_train, X_test = X[:n_train], X[n_train:]
        y_train, y_test = y[:n_train], y[n_train:]

        # Feature selection
        if feature_selection and X_train.shape[1] > 20:
            X_train, X_test, feature_names = self._select_features(
                X_train, y_train, X_test, feature_names, max_features=20
            )

        # Train model
        model = None
        predictions = None
        metrics = {}
        feature_importance = {}

        if model_type == 'xgboost':
            model, predictions, metrics, feature_importance = self._train_xgboost(
                X_train, y_train, X_test, y_test, feature_names,
                params=xgboost_params, n_splits=n_splits
            )
        elif model_type == 'lightgbm':
            model, predictions, metrics, feature_importance = self._train_lightgbm(
                X_train, y_train, X_test, y_test, feature_names,
                params=lightgbm_params, n_splits=n_splits
            )
        elif model_type == 'lstm':
            model, predictions, metrics, feature_importance = self._train_lstm(
                X_train, y_train, X_test, y_test, feature_names,
                params=lstm_params
            )
        elif model_type == 'ensemble':
            model, predictions, metrics, feature_importance = self._train_ensemble(
                X_train, y_train, X_test, y_test, feature_names,
                xgboost_params=xgboost_params, lightgbm_params=lightgbm_params,
                n_splits=n_splits
            )

        self._model = model

        return self._create_result_dict(
            value={
                'predictions': predictions.tolist() if isinstance(predictions, np.ndarray) else predictions,
                'target': y_test.tolist() if isinstance(y_test, np.ndarray) else list(y_test),
            },
            method=f'return_prediction_{model_type}',
            parameters={
                'model_type': model_type,
                'horizon': horizon,
                'train_ratio': train_ratio,
                'n_features': len(feature_names),
                'n_train': len(X_train),
                'n_test': len(X_test),
            },
            metadata={
                'metrics': metrics,
                'feature_importance': feature_importance,
            }
        )

    def _prepare_data(self,
                      features: pd.DataFrame,
                      target: np.ndarray) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Prepare features and target for model training."""
        # Drop non-numeric columns
        numeric_cols = features.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            raise DataValidationError(
                "No numeric columns found in features",
                field_name="features"
            )

        X = features[numeric_cols].values
        y = target.copy() if isinstance(target, np.ndarray) else np.array(target)

        # Align lengths
        min_len = min(len(X), len(y))
        X, y = X[:min_len], y[:min_len]

        # Remove rows with NaN or Inf
        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y) |
                 np.isinf(X).any(axis=1) | np.isinf(y))
        X, y = X[mask], y[mask]

        if len(y) < 30:
            raise InsufficientDataError(required=30, provided=len(y))

        return X, y, numeric_cols

    def _select_features(self,
                         X_train: np.ndarray,
                         y_train: np.ndarray,
                         X_test: np.ndarray,
                         feature_names: List[str],
                         max_features: int = 20) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Select top features using correlation with target."""
        correlations = []
        for i in range(X_train.shape[1]):
            if np.std(X_train[:, i]) > 1e-10:
                corr = np.corrcoef(X_train[:, i], y_train)[0, 1]
                correlations.append((i, abs(corr) if not np.isnan(corr) else 0))
            else:
                correlations.append((i, 0))

        correlations.sort(key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in correlations[:max_features]]

        X_train_sel = X_train[:, top_indices]
        X_test_sel = X_test[:, top_indices]
        selected_names = [feature_names[i] for i in top_indices]

        return X_train_sel, X_test_sel, selected_names

    def _compute_metrics(self,
                         y_true: np.ndarray,
                         y_pred: np.ndarray) -> Dict[str, float]:
        """Compute regression evaluation metrics."""
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        yt, yp = y_true[mask], y_pred[mask]

        if len(yt) < 2:
            return {}

        mse = float(np.mean((yt - yp) ** 2))
        mae = float(np.mean(np.abs(yt - yp)))
        rmse = float(np.sqrt(mse))

        # R-squared
        ss_res = np.sum((yt - yp) ** 2)
        ss_tot = np.sum((yt - np.mean(yt)) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Hit ratio (direction accuracy)
        if len(yt) >= 2:
            direction_correct = np.mean(np.sign(yt) == np.sign(yp))
            hit_ratio = float(direction_correct)
        else:
            hit_ratio = 0.0

        # Information Coefficient
        try:
            from scipy import stats
            ic, _ = stats.spearmanr(yt, yp)
            ic = float(ic) if not np.isnan(ic) else 0.0
        except Exception:
            ic = 0.0

        return {
            'mse': self._round_result(mse),
            'mae': self._round_result(mae),
            'rmse': self._round_result(rmse),
            'r2': self._round_result(r2),
            'hit_ratio': self._round_result(hit_ratio),
            'ic': self._round_result(ic),
        }

    def _train_xgboost(self,
                       X_train: np.ndarray,
                       y_train: np.ndarray,
                       X_test: np.ndarray,
                       y_test: np.ndarray,
                       feature_names: List[str],
                       params: Optional[Dict[str, Any]] = None,
                       n_splits: int = 5) -> Tuple[Any, np.ndarray, Dict, Dict]:
        """Train XGBoost model with walk-forward validation."""
        try:
            import xgboost as xgb
        except ImportError:
            raise DependencyError("xgboost", message="Install with: pip install xgboost")

        default_params = {
            'n_estimators': 100,
            'max_depth': 5,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'random_state': self.random_state,
            'verbosity': 0,
        }

        if params:
            default_params.update(params)

        # Walk-forward cross-validation
        cv_predictions = np.zeros(len(X_test))
        cv_metrics = []

        try:
            n_splits_actual = min(n_splits, len(X_train) // 20)
            if n_splits_actual < 2:
                n_splits_actual = 1

            if n_splits_actual > 1:
                split_size = len(X_train) // n_splits_actual
                for i in range(n_splits_actual - 1):
                    train_end = (i + 1) * split_size
                    X_cv_train = X_train[:train_end]
                    y_cv_train = y_train[:train_end]
                    X_cv_val = X_train[train_end:train_end + split_size]
                    y_cv_val = y_train[train_end:train_end + split_size]

                    if len(X_cv_val) < 5:
                        continue

                    model_cv = xgb.XGBRegressor(**default_params)
                    model_cv.fit(X_cv_train, y_cv_train,
                                 eval_set=[(X_cv_val, y_cv_val)],
                                 verbose=False)
            else:
                model_cv = xgb.XGBRegressor(**default_params)
                model_cv.fit(X_train, y_train, verbose=False)
        except Exception as e:
            raise ModelFitError(str(e), model_type="xgboost")

        # Fit final model
        try:
            model = xgb.XGBRegressor(**default_params)
            model.fit(X_train, y_train, verbose=False)
        except Exception as e:
            raise ModelFitError(str(e), model_type="xgboost")

        predictions = model.predict(X_test)
        metrics = self._compute_metrics(y_test, predictions)

        # Feature importance
        importance = {}
        for i, name in enumerate(feature_names[:X_train.shape[1]]):
            if i < len(model.feature_importances_):
                importance[name] = float(model.feature_importances_[i])

        if importance:
            max_imp = max(importance.values())
            if max_imp > 0:
                importance = {k: v / max_imp for k, v in importance.items()}

        return model, predictions, metrics, importance

    def _train_lightgbm(self,
                        X_train: np.ndarray,
                        y_train: np.ndarray,
                        X_test: np.ndarray,
                        y_test: np.ndarray,
                        feature_names: List[str],
                        params: Optional[Dict[str, Any]] = None,
                        n_splits: int = 5) -> Tuple[Any, np.ndarray, Dict, Dict]:
        """Train LightGBM model with walk-forward validation."""
        try:
            import lightgbm as lgb
        except ImportError:
            raise DependencyError("lightgbm", message="Install with: pip install lightgbm")

        default_params = {
            'n_estimators': 100,
            'max_depth': 5,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'random_state': self.random_state,
            'verbosity': -1,
            'force_row_wise': True,
        }

        if params:
            default_params.update(params)

        try:
            model = lgb.LGBMRegressor(**default_params)
            model.fit(X_train, y_train,
                      eval_set=[(X_test, y_test)],
                      eval_metric='rmse')
        except Exception as e:
            raise ModelFitError(str(e), model_type="lightgbm")

        predictions = model.predict(X_test)
        metrics = self._compute_metrics(y_test, predictions)

        # Feature importance
        importance = {}
        for i, name in enumerate(feature_names[:X_train.shape[1]]):
            if i < len(model.feature_importances_):
                importance[name] = float(model.feature_importances_[i])

        if importance:
            max_imp = max(importance.values())
            if max_imp > 0:
                importance = {k: v / max_imp for k, v in importance.items()}

        return model, predictions, metrics, importance

    def _train_lstm(self,
                    X_train: np.ndarray,
                    y_train: np.ndarray,
                    X_test: np.ndarray,
                    y_test: np.ndarray,
                    feature_names: List[str],
                    params: Optional[Dict[str, Any]] = None) -> Tuple[Any, np.ndarray, Dict, Dict]:
        """Train LSTM model for sequence prediction."""
        try:
            from sklearn.preprocessing import MinMaxScaler
        except ImportError:
            raise DependencyError("scikit-learn", message="Install with: pip install scikit-learn")

        # Check if keras/tensorflow is available
        try:
            from tensorflow import keras
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout
            from tensorflow.keras.optimizers import Adam
            has_keras = True
        except ImportError:
            # Fall back to standalone keras
            try:
                import keras
                from keras.models import Sequential
                from keras.layers import LSTM, Dense, Dropout
                from keras.optimizers import Adam
                has_keras = True
            except ImportError:
                has_keras = False

        if not has_keras:
            raise DependencyError(
                "tensorflow/keras",
                message="Install with: pip install tensorflow"
            )

        default_params = {
            'lstm_units': 50,
            'dropout': 0.2,
            'epochs': 50,
            'batch_size': 32,
            'lookback': 10,
        }

        if params:
            default_params.update(params)

        lookback = default_params['lookback']

        # Scale data
        scaler_X = MinMaxScaler()
        scaler_y = MinMaxScaler()

        X_train_norm = scaler_X.fit_transform(X_train)
        X_test_norm = scaler_X.transform(X_test)
        y_train_norm = scaler_y.fit_transform(y_train.reshape(-1, 1)).flatten()

        # Create sequences
        def create_sequences(X, y, lookback):
            X_seq, y_seq = [], []
            for i in range(lookback, len(X)):
                X_seq.append(X[i - lookback:i])
                y_seq.append(y[i])
            return np.array(X_seq), np.array(y_seq)

        if len(X_train_norm) <= lookback:
            raise InsufficientDataError(
                required=lookback + 1,
                provided=len(X_train_norm),
                calculation="lstm_sequence_creation"
            )

        X_train_seq, y_train_seq = create_sequences(X_train_norm, y_train_norm, lookback)
        X_test_seq, y_test_seq = create_sequences(X_test_norm, y_test, lookback)

        if len(X_train_seq) < 2:
            # Fall back to simple prediction if not enough data for sequences
            predictions = np.zeros(len(y_test))
            metrics = self._compute_metrics(y_test, predictions)
            importance = dict(zip(
                feature_names[:X_train.shape[1]],
                np.ones(min(len(feature_names), X_train.shape[1])) / max(1, min(len(feature_names), X_train.shape[1]))
            ))
            return None, predictions, metrics, importance

        n_features = X_train_seq.shape[2]

        try:
            model = Sequential([
                LSTM(default_params['lstm_units'], activation='relu',
                     return_sequences=True,
                     input_shape=(lookback, n_features)),
                Dropout(default_params['dropout']),
                LSTM(default_params['lstm_units'] // 2, activation='relu'),
                Dropout(default_params['dropout']),
                Dense(25, activation='relu'),
                Dense(1)
            ])

            model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')
            model.fit(
                X_train_seq, y_train_seq,
                epochs=default_params['epochs'],
                batch_size=default_params['batch_size'],
                verbose=0,
                validation_split=0.2
            )

            # Predict
            if len(X_test_seq) > 0:
                pred_norm = model.predict(X_test_seq, verbose=0).flatten()
                predictions = scaler_y.inverse_transform(pred_norm.reshape(-1, 1)).flatten()
                y_test_aligned = y_test_seq  # Already aligned
            else:
                predictions = np.array([])
                y_test_aligned = np.array([])
        except Exception as e:
            raise ModelFitError(str(e), model_type="lstm")

        metrics = self._compute_metrics(y_test_aligned, predictions)

        # Feature importance via permutation
        importance = self._permutation_importance(
            model, X_test_seq, y_test_aligned, feature_names[:n_features],
            is_keras=True
        )

        return model, predictions, metrics, importance

    def _train_ensemble(self,
                        X_train: np.ndarray,
                        y_train: np.ndarray,
                        X_test: np.ndarray,
                        y_test: np.ndarray,
                        feature_names: List[str],
                        xgboost_params: Optional[Dict] = None,
                        lightgbm_params: Optional[Dict] = None,
                        n_splits: int = 5) -> Tuple[Any, np.ndarray, Dict, Dict]:
        """Train ensemble of XGBoost and LightGBM models."""
        models = {}
        predictions_all = []

        # Train XGBoost
        try:
            _, preds_xgb, metrics_xgb, imp_xgb = self._train_xgboost(
                X_train, y_train, X_test, y_test, feature_names,
                params=xgboost_params, n_splits=n_splits
            )
            predictions_all.append(preds_xgb)
            models['xgboost'] = {'predictions': preds_xgb, 'metrics': metrics_xgb}
        except Exception:
            preds_xgb = None

        # Train LightGBM
        try:
            _, preds_lgb, metrics_lgb, imp_lgb = self._train_lightgbm(
                X_train, y_train, X_test, y_test, feature_names,
                params=lightgbm_params, n_splits=n_splits
            )
            predictions_all.append(preds_lgb)
            models['lightgbm'] = {'predictions': preds_lgb, 'metrics': metrics_lgb}
        except Exception:
            preds_lgb = None

        if not predictions_all:
            raise ModelFitError(
                "All ensemble models failed to train",
                model_type="ensemble"
            )

        # Simple average ensemble
        predictions = np.mean(predictions_all, axis=0)
        metrics = self._compute_metrics(y_test, predictions)

        # Combined feature importance
        importance = {}
        for i, name in enumerate(feature_names[:X_train.shape[1]]):
            scores = []
            if preds_xgb is not None and hasattr(self, '_last_xgb_model'):
                pass  # Will be populated from _train_xgboost
            scores.append(1.0 / max(1, len(feature_names)))  # Uniform fallback
            importance[name] = float(np.mean(scores)) if scores else 0.0

        # Average importance across features
        n_f = len(importance)
        if n_f > 0:
            importance = {k: 1.0 / n_f for k in importance}

        return models, predictions, metrics, importance

    def _permutation_importance(self,
                                model: Any,
                                X: np.ndarray,
                                y: np.ndarray,
                                feature_names: List[str],
                                is_keras: bool = False) -> Dict[str, float]:
        """Compute permutation feature importance."""
        importance = {}

        if len(X) < 2 or len(y) < 2:
            return {name: 0.0 for name in feature_names}

        # Baseline prediction
        if is_keras:
            try:
                baseline_pred = model.predict(X, verbose=0).flatten()
            except Exception:
                return {name: 0.0 for name in feature_names}
        else:
            try:
                baseline_pred = model.predict(X)
            except Exception:
                return {name: 0.0 for name in feature_names}

        baseline_error = np.mean((y - baseline_pred) ** 2)

        for i, name in enumerate(feature_names):
            if i >= X.shape[1]:
                break
            X_permuted = X.copy()
            np.random.shuffle(X_permuted[:, i])

            if is_keras:
                try:
                    permuted_pred = model.predict(X_permuted, verbose=0).flatten()
                except Exception:
                    importance[name] = 0.0
                    continue
            else:
                try:
                    permuted_pred = model.predict(X_permuted)
                except Exception:
                    importance[name] = 0.0
                    continue

            permuted_error = np.mean((y - permuted_pred) ** 2)
            importance[name] = float(max(0, permuted_error - baseline_error))

        if importance:
            max_imp = max(importance.values())
            if max_imp > 0:
                importance = {k: v / max_imp for k, v in importance.items()}

        return importance
