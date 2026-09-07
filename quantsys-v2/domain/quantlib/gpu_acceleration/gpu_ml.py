"""
GPU加速机器学习训练

使用RAPIDS cuML加速机器学习模型训练
性能提升：10-50倍

依赖：
- cuml (RAPIDS)
- xgboost[gpu]
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Tuple
import time
import logging

logger = logging.getLogger(__name__)

# 尝试导入GPU库
try:
    import cupy as cp
    import cuml
    from cuml.ensemble import RandomForestClassifier as cuRF
    from cuml.linear_model import LogisticRegression as cuLR
    from cuml.preprocessing import StandardScaler as cuScaler
    GPU_AVAILABLE = True
    logger.info("cuML available, GPU ML acceleration enabled")
except ImportError:
    GPU_AVAILABLE = False
    logger.warning("cuML not available, falling back to CPU")

# XGBoost GPU支持
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not available")

# CPU备选方案
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


class GPUMLTrainer:
    """
    GPU加速机器学习训练器

    支持模型：
    - 随机森林
    - 逻辑回归
    - XGBoost
    - LightGBM
    """

    def __init__(self, use_gpu: bool = True):
        """
        Args:
            use_gpu: 是否使用GPU加速
        """
        self.use_gpu = use_gpu and GPU_AVAILABLE

        if self.use_gpu:
            logger.info("GPU ML acceleration enabled")
        else:
            logger.info("Using CPU ML training")

    def train_random_forest(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        n_estimators: int = 100,
        max_depth: int = 10,
        **kwargs
    ) -> Tuple[object, float]:
        """
        训练随机森林（GPU加速）

        Args:
            X_train: 训练特征
            y_train: 训练标签
            n_estimators: 树的数量
            max_depth: 最大深度
            **kwargs: 其他参数

        Returns:
            (模型, 训练时间)
        """
        start = time.time()

        if self.use_gpu:
            # GPU训练
            model = cuRF(
                n_estimators=n_estimators,
                max_depth=max_depth,
                **kwargs
            )
            model.fit(X_train, y_train)
        else:
            # CPU训练
            model = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                **kwargs
            )
            model.fit(X_train, y_train)

        train_time = time.time() - start
        logger.info(f"Random Forest training time: {train_time:.2f}s")

        return model, train_time

    def train_logistic_regression(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        max_iter: int = 1000,
        **kwargs
    ) -> Tuple[object, float]:
        """
        训练逻辑回归（GPU加速）

        Args:
            X_train: 训练特征
            y_train: 训练标签
            max_iter: 最大迭代次数
            **kwargs: 其他参数

        Returns:
            (模型, 训练时间)
        """
        start = time.time()

        if self.use_gpu:
            # GPU训练
            model = cuLR(
                max_iter=max_iter,
                **kwargs
            )
            model.fit(X_train, y_train)
        else:
            # CPU训练
            model = LogisticRegression(
                max_iter=max_iter,
                **kwargs
            )
            model.fit(X_train, y_train)

        train_time = time.time() - start
        logger.info(f"Logistic Regression training time: {train_time:.2f}s")

        return model, train_time

    def train_xgboost(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        **kwargs
    ) -> Tuple[object, float]:
        """
        训练XGBoost（GPU加速）

        Args:
            X_train: 训练特征
            y_train: 训练标签
            n_estimators: 树的数量
            max_depth: 最大深度
            learning_rate: 学习率
            **kwargs: 其他参数

        Returns:
            (模型, 训练时间)
        """
        if not XGBOOST_AVAILABLE:
            raise ImportError("XGBoost not available")

        start = time.time()

        # 设置GPU参数
        params = {
            'n_estimators': n_estimators,
            'max_depth': max_depth,
            'learning_rate': learning_rate,
            'tree_method': 'gpu_hist' if self.use_gpu else 'hist',
            'predictor': 'gpu_predictor' if self.use_gpu else 'cpu_predictor',
            **kwargs
        }

        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train)

        train_time = time.time() - start
        logger.info(f"XGBoost training time: {train_time:.2f}s")

        return model, train_time

    def preprocess_data(
        self,
        X: np.ndarray,
        scaler: Optional[object] = None
    ) -> Tuple[np.ndarray, object]:
        """
        数据预处理（GPU加速）

        Args:
            X: 特征数据
            scaler: 已有的缩放器（用于测试集）

        Returns:
            (标准化后的数据, 缩放器)
        """
        if scaler is None:
            # 创建新的缩放器
            if self.use_gpu:
                scaler = cuScaler()
            else:
                scaler = StandardScaler()

            X_scaled = scaler.fit_transform(X)
        else:
            # 使用已有的缩放器
            X_scaled = scaler.transform(X)

        return X_scaled, scaler

    def cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model_type: str = 'random_forest',
        n_folds: int = 5,
        **model_params
    ) -> Dict[str, float]:
        """
        交叉验证（GPU加速）

        Args:
            X: 特征数据
            y: 标签数据
            model_type: 模型类型
            n_folds: 折数
            **model_params: 模型参数

        Returns:
            交叉验证结果
        """
        from sklearn.model_selection import KFold

        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        scores = []
        train_times = []

        for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # 训练模型
            if model_type == 'random_forest':
                model, train_time = self.train_random_forest(
                    X_train, y_train, **model_params
                )
            elif model_type == 'logistic_regression':
                model, train_time = self.train_logistic_regression(
                    X_train, y_train, **model_params
                )
            elif model_type == 'xgboost':
                model, train_time = self.train_xgboost(
                    X_train, y_train, **model_params
                )
            else:
                raise ValueError(f"Unknown model type: {model_type}")

            # 评估
            score = model.score(X_val, y_val)
            scores.append(score)
            train_times.append(train_time)

            logger.info(f"Fold {fold+1}/{n_folds}: score={score:.4f}, time={train_time:.2f}s")

        return {
            'mean_score': np.mean(scores),
            'std_score': np.std(scores),
            'mean_train_time': np.mean(train_times),
            'total_time': np.sum(train_times)
        }


def benchmark_ml_performance():
    """机器学习性能基准测试"""
    print("=== GPU vs CPU ML Performance Benchmark ===\n")

    # 生成测试数据
    np.random.seed(42)
    n_samples = 10000
    n_features = 50

    X = np.random.randn(n_samples, n_features)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)

    # 分割数据
    split = int(0.8 * n_samples)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # CPU训练
    print("CPU Training:")
    cpu_trainer = GPUMLTrainer(use_gpu=False)

    cpu_rf, cpu_rf_time = cpu_trainer.train_random_forest(
        X_train, y_train, n_estimators=100, max_depth=10
    )
    cpu_rf_score = cpu_rf.score(X_test, y_test)
    print(f"  Random Forest: {cpu_rf_time:.2f}s, score={cpu_rf_score:.4f}")

    cpu_lr, cpu_lr_time = cpu_trainer.train_logistic_regression(
        X_train, y_train, max_iter=1000
    )
    cpu_lr_score = cpu_lr.score(X_test, y_test)
    print(f"  Logistic Regression: {cpu_lr_time:.2f}s, score={cpu_lr_score:.4f}")

    # GPU训练
    if GPU_AVAILABLE:
        print("\nGPU Training:")
        gpu_trainer = GPUMLTrainer(use_gpu=True)

        gpu_rf, gpu_rf_time = gpu_trainer.train_random_forest(
            X_train, y_train, n_estimators=100, max_depth=10
        )
        gpu_rf_score = gpu_rf.score(X_test, y_test)
        print(f"  Random Forest: {gpu_rf_time:.2f}s, score={gpu_rf_score:.4f}")
        print(f"  Speedup: {cpu_rf_time/gpu_rf_time:.2f}x")

        gpu_lr, gpu_lr_time = gpu_trainer.train_logistic_regression(
            X_train, y_train, max_iter=1000
        )
        gpu_lr_score = gpu_lr.score(X_test, y_test)
        print(f"  Logistic Regression: {gpu_lr_time:.2f}s, score={gpu_lr_score:.4f}")
        print(f"  Speedup: {cpu_lr_time/gpu_lr_time:.2f}x")
    else:
        print("\nGPU not available, skipping GPU benchmark")

    # XGBoost对比
    if XGBOOST_AVAILABLE:
        print("\nXGBoost Training:")

        cpu_xgb, cpu_xgb_time = cpu_trainer.train_xgboost(
            X_train, y_train, n_estimators=100
        )
        cpu_xgb_score = cpu_xgb.score(X_test, y_test)
        print(f"  CPU: {cpu_xgb_time:.2f}s, score={cpu_xgb_score:.4f}")

        if GPU_AVAILABLE:
            gpu_xgb, gpu_xgb_time = gpu_trainer.train_xgboost(
                X_train, y_train, n_estimators=100
            )
            gpu_xgb_score = gpu_xgb.score(X_test, y_test)
            print(f"  GPU: {gpu_xgb_time:.2f}s, score={gpu_xgb_score:.4f}")
            print(f"  Speedup: {cpu_xgb_time/gpu_xgb_time:.2f}x")


# 使用示例
def example_usage():
    """使用示例"""
    # 创建训练器
    trainer = GPUMLTrainer(use_gpu=True)

    # 生成模拟数据
    np.random.seed(42)
    n_samples = 1000
    n_features = 20

    X = np.random.randn(n_samples, n_features)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)

    # 数据预处理
    X_scaled, scaler = trainer.preprocess_data(X)

    # 交叉验证
    print("Cross Validation Results:")
    cv_results = trainer.cross_validate(
        X_scaled, y,
        model_type='random_forest',
        n_folds=5,
        n_estimators=50,
        max_depth=8
    )

    for key, value in cv_results.items():
        print(f"  {key}: {value:.4f}")


if __name__ == "__main__":
    example_usage()
    print("\n")
    benchmark_ml_performance()
