"""
LSTM预测模型 - Team B
时序预测的深度学习模型
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# 尝试导入PyTorch，如果没有则使用简化版本
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available, using simplified version")


class LSTMPredictor:
    """
    LSTM时序预测模型

    架构:
    - LSTM层: 捕捉时序依赖
    - Dropout: 防止过拟合
    - 全连接层: 输出预测
    """

    def __init__(self,
                 input_size: int = 10,
                 hidden_size: int = 64,
                 num_layers: int = 2,
                 dropout: float = 0.2,
                 sequence_length: int = 20):
        """
        Args:
            input_size: 输入特征数
            hidden_size: 隐藏层大小
            num_layers: LSTM层数
            dropout: Dropout比例
            sequence_length: 序列长度
        """
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.sequence_length = sequence_length

        if TORCH_AVAILABLE:
            self.model = self._build_pytorch_model()
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
        else:
            self.model = None
            logger.warning("Using simplified prediction without PyTorch")

        logger.info(f"LSTMPredictor initialized: hidden={hidden_size}, layers={num_layers}")

    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        预测

        Args:
            features: (n_samples, sequence_length, input_size)

        Returns:
            predictions: (n_samples,)
        """
        if not TORCH_AVAILABLE or self.model is None:
            return self._simple_predict(features)

        self.model.eval()
        with torch.no_grad():
            # 转换为tensor
            x = torch.FloatTensor(features).to(self.device)

            # 预测
            output = self.model(x)
            predictions = torch.sigmoid(output).cpu().numpy().flatten()

        logger.debug(f"Predicted {len(predictions)} samples")
        return predictions

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """
        预测概率

        Returns:
            (n_samples, 2) - [prob_class_0, prob_class_1]
        """
        predictions = self.predict(features)

        # 转换为二分类概率
        proba = np.column_stack([1 - predictions, predictions])
        return proba

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        注: LSTM的特征重要性难以直接计算，这里返回简化版本
        """
        # 简化实现：假设所有特征同等重要
        importance = {f'feature_{i}': 1.0 / self.input_size
                     for i in range(self.input_size)}
        return importance

    def _build_pytorch_model(self):
        """构建PyTorch LSTM模型"""

        class LSTMModel(nn.Module):
            def __init__(self, input_size, hidden_size, num_layers, dropout):
                super().__init__()
                self.lstm = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    dropout=dropout if num_layers > 1 else 0,
                    batch_first=True
                )
                self.fc = nn.Linear(hidden_size, 1)

            def forward(self, x):
                # x: (batch, seq_len, input_size)
                lstm_out, _ = self.lstm(x)
                # 取最后一个时间步
                last_output = lstm_out[:, -1, :]
                output = self.fc(last_output)
                return output

        return LSTMModel(
            self.input_size,
            self.hidden_size,
            self.num_layers,
            self.dropout
        )

    def _simple_predict(self, features: np.ndarray) -> np.ndarray:
        """简化预测（无PyTorch时）"""
        # 使用简单的移动平均作为预测
        if len(features.shape) == 3:
            # (n_samples, seq_len, features) -> 取最后一个时间步的平均
            predictions = features[:, -1, :].mean(axis=1)
        else:
            predictions = features.mean(axis=1)

        # 归一化到[0, 1]
        predictions = (predictions - predictions.min()) / (predictions.max() - predictions.min() + 1e-8)

        return predictions

    def prepare_sequences(self, data: pd.DataFrame, target_col: str = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        准备序列数据

        Args:
            data: 原始数据
            target_col: 目标列名

        Returns:
            X: (n_samples, sequence_length, n_features)
            y: (n_samples,) if target_col else None
        """
        features = data.drop(columns=[target_col] if target_col else []).values

        X = []
        y = [] if target_col else None

        for i in range(len(features) - self.sequence_length):
            X.append(features[i:i + self.sequence_length])
            if target_col:
                y.append(data[target_col].iloc[i + self.sequence_length])

        X = np.array(X)
        y = np.array(y) if y else None

        logger.info(f"Prepared {len(X)} sequences of length {self.sequence_length}")

        return X, y
