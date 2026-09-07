"""
Team B: 机器学习模块接口定义
负责人: 算法工程师
版本: 1.0
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List
import numpy as np
import pandas as pd


class IModelPredictor(ABC):
    """模型预测器接口"""

    @abstractmethod
    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        预测

        Args:
            features: 特征矩阵 (n_samples, n_features)

        Returns:
            预测值 (n_samples,)
        """
        pass

    @abstractmethod
    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """
        预测概率

        Returns:
            概率矩阵 (n_samples, n_classes)
        """
        pass

    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性"""
        pass


class IModelTrainer(ABC):
    """模型训练器接口"""

    @abstractmethod
    def train(self,
             X_train: pd.DataFrame,
             y_train: pd.Series,
             X_val: pd.DataFrame = None,
             y_val: pd.Series = None) -> Any:
        """训练模型"""
        pass

    @abstractmethod
    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict:
        """评估模型"""
        pass
