"""
Hyperparameter tuning using Optuna for Bayesian optimization.
"""
import numpy as np
from typing import Dict, Any, Callable, Optional
import logging
from sklearn.model_selection import cross_val_score

logger = logging.getLogger(__name__)

# Lazy import to avoid blocking training when optuna is not installed and tuning is not needed
_optuna = None

def _get_optuna():
    global _optuna
    if _optuna is None:
        import optuna as _optuna
    return _optuna


class HyperparameterTuner:
    """
    Hyperparameter optimization using Optuna's Bayesian optimization.
    """

    def __init__(self, n_trials: int = 100, timeout: Optional[int] = None, n_jobs: int = 1):
        """
        Args:
            n_trials: Number of optimization trials
            timeout: Timeout in seconds (None for no timeout)
            n_jobs: Number of parallel jobs (-1 for all cores)
        """
        self.n_trials = n_trials
        self.timeout = timeout
        self.n_jobs = n_jobs
        self.best_params = None
        self.best_score = None
        self.study = None

    def tune_xgboost(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        cv_splits: int = 5,
        scoring: str = 'accuracy'
    ) -> Dict[str, Any]:
        """
        Tune XGBoost hyperparameters.

        Args:
            X_train: Training features
            y_train: Training labels
            cv_splits: Number of CV splits
            scoring: Scoring metric

        Returns:
            Dictionary with best parameters and score
        """
        import xgboost as xgb

        def objective(trial):
            params = {
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0, 0.5),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 1.0),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 1.0),
                'random_state': 42
            }

            model = xgb.XGBClassifier(**params)

            # Use time series CV
            from sklearn.model_selection import TimeSeriesSplit
            tscv = TimeSeriesSplit(n_splits=cv_splits)

            scores = cross_val_score(model, X_train, y_train, cv=tscv, scoring=scoring, n_jobs=1)
            return scores.mean()

        # Create study
        optuna = _get_optuna()
        self.study = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=42)
        )

        # Optimize
        logger.info(f"Starting hyperparameter tuning with {self.n_trials} trials...")
        self.study.optimize(
            objective,
            n_trials=self.n_trials,
            timeout=self.timeout,
            n_jobs=self.n_jobs,
            show_progress_bar=True
        )

        self.best_params = self.study.best_params
        self.best_score = self.study.best_value

        logger.info(f"Best score: {self.best_score:.4f}")
        logger.info(f"Best params: {self.best_params}")

        return {
            'best_params': self.best_params,
            'best_score': float(self.best_score),
            'n_trials': len(self.study.trials),
            'best_trial': self.study.best_trial.number
        }

    def tune_lightgbm(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        cv_splits: int = 5,
        scoring: str = 'accuracy'
    ) -> Dict[str, Any]:
        """
        Tune LightGBM hyperparameters.

        Args:
            X_train: Training features
            y_train: Training labels
            cv_splits: Number of CV splits
            scoring: Scoring metric

        Returns:
            Dictionary with best parameters and score
        """
        try:
            import lightgbm as lgb
        except ImportError:
            logger.error("LightGBM not installed. Run: pip install lightgbm")
            return {'error': 'lightgbm not installed'}

        def objective(trial):
            params = {
                'num_leaves': trial.suggest_int('num_leaves', 20, 150),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 1.0),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 1.0),
                'random_state': 42,
                'verbose': -1
            }

            model = lgb.LGBMClassifier(**params)

            # Use time series CV
            from sklearn.model_selection import TimeSeriesSplit
            tscv = TimeSeriesSplit(n_splits=cv_splits)

            scores = cross_val_score(model, X_train, y_train, cv=tscv, scoring=scoring, n_jobs=1)
            return scores.mean()

        # Create study
        optuna = _get_optuna()
        self.study = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=42)
        )

        # Optimize
        logger.info(f"Starting LightGBM hyperparameter tuning with {self.n_trials} trials...")
        self.study.optimize(
            objective,
            n_trials=self.n_trials,
            timeout=self.timeout,
            n_jobs=self.n_jobs,
            show_progress_bar=True
        )

        self.best_params = self.study.best_params
        self.best_score = self.study.best_value

        logger.info(f"Best score: {self.best_score:.4f}")
        logger.info(f"Best params: {self.best_params}")

        return {
            'best_params': self.best_params,
            'best_score': float(self.best_score),
            'n_trials': len(self.study.trials),
            'best_trial': self.study.best_trial.number
        }

    def get_optimization_history(self) -> Dict[str, Any]:
        """Get optimization history for visualization."""
        if self.study is None:
            return {'error': 'No study available'}

        trials_data = []
        for trial in self.study.trials:
            trials_data.append({
                'number': trial.number,
                'value': trial.value,
                'params': trial.params,
                'state': trial.state.name
            })

        return {
            'trials': trials_data,
            'best_trial': self.study.best_trial.number,
            'best_value': float(self.study.best_value),
            'best_params': self.study.best_params
        }

    def plot_optimization_history(self, save_path: Optional[str] = None):
        """Plot optimization history."""
        if self.study is None:
            logger.error("No study available to plot")
            return

        try:
            import matplotlib.pyplot as plt

            fig = _get_optuna().visualization.matplotlib.plot_optimization_history(self.study)
            if save_path:
                plt.savefig(save_path)
                logger.info(f"Optimization history saved to {save_path}")
            else:
                plt.show()
        except ImportError:
            logger.warning("matplotlib not available for plotting")

    def plot_param_importances(self, save_path: Optional[str] = None):
        """Plot parameter importances."""
        if self.study is None:
            logger.error("No study available to plot")
            return

        try:
            import matplotlib.pyplot as plt

            fig = _get_optuna().visualization.matplotlib.plot_param_importances(self.study)
            if save_path:
                plt.savefig(save_path)
                logger.info(f"Parameter importances saved to {save_path}")
            else:
                plt.show()
        except ImportError:
            logger.warning("matplotlib not available for plotting")
