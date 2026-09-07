"""
Transformer预测模型 - Team B
基于注意力机制的时序预测
"""
import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# 尝试导入PyTorch
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available, using simplified version")


class TransformerPredictor:
    """
    Transformer预测模型

    架构:
    - 位置编码: 捕捉序列位置信息
    - 多头注意力: 关注不同特征关系
    - 前馈网络: 非线性变换
    """

    def __init__(self,
                 input_size: int = 10,
                 d_model: int = 128,
                 nhead: int = 8,
                 num_layers: int = 3,
                 dim_feedforward: int = 512,
                 dropout: float = 0.1,
                 sequence_length: int = 20):
        """
        Args:
            input_size: 输入特征数
            d_model: 模型维度
            nhead: 注意力头数
            num_layers: Transformer层数
            dim_feedforward: 前馈网络维度
            dropout: Dropout比例
            sequence_length: 序列长度
        """
        self.input_size = input_size
        self.d_model = d_model
        self.nhead = nhead
        self.num_layers = num_layers
        self.dim_feedforward = dim_feedforward
        self.dropout = dropout
        self.sequence_length = sequence_length

        if TORCH_AVAILABLE:
            self.model = self._build_pytorch_model()
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
        else:
            self.model = None
            logger.warning("Using simplified prediction without PyTorch")

        logger.info(f"TransformerPredictor initialized: d_model={d_model}, nhead={nhead}, layers={num_layers}")

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

        注: Transformer的特征重要性通过注意力权重计算
        """
        if not TORCH_AVAILABLE or self.model is None:
            # 简化实现
            importance = {f'feature_{i}': 1.0 / self.input_size
                         for i in range(self.input_size)}
            return importance

        # 从注意力权重提取重要性
        # 这里简化实现，实际应该从模型的attention_weights提取
        importance = {f'feature_{i}': 1.0 / self.input_size
                     for i in range(self.input_size)}
        return importance

    def _build_pytorch_model(self):
        """构建PyTorch Transformer模型"""

        class PositionalEncoding(nn.Module):
            """位置编码"""
            def __init__(self, d_model, max_len=5000):
                super().__init__()
                pe = torch.zeros(max_len, d_model)
                position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
                div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
                pe[:, 0::2] = torch.sin(position * div_term)
                pe[:, 1::2] = torch.cos(position * div_term)
                pe = pe.unsqueeze(0)
                self.register_buffer('pe', pe)

            def forward(self, x):
                return x + self.pe[:, :x.size(1), :]

        class TransformerModel(nn.Module):
            def __init__(self, input_size, d_model, nhead, num_layers, dim_feedforward, dropout):
                super().__init__()
                self.embedding = nn.Linear(input_size, d_model)
                self.pos_encoder = PositionalEncoding(d_model)

                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=d_model,
                    nhead=nhead,
                    dim_feedforward=dim_feedforward,
                    dropout=dropout,
                    batch_first=True
                )
                self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)
                self.fc = nn.Linear(d_model, 1)

            def forward(self, x):
                # x: (batch, seq_len, input_size)
                x = self.embedding(x)
                x = self.pos_encoder(x)
                transformer_out = self.transformer(x)
                # 取最后一个时间步
                last_output = transformer_out[:, -1, :]
                output = self.fc(last_output)
                return output

        return TransformerModel(
            self.input_size,
            self.d_model,
            self.nhead,
            self.num_layers,
            self.dim_feedforward,
            self.dropout
        )

    def _simple_predict(self, features: np.ndarray) -> np.ndarray:
        """简化预测（无PyTorch时）"""
        # 使用加权平均作为预测
        if len(features.shape) == 3:
            # 对序列加权：越近的时间步权重越大
            weights = np.linspace(0.5, 1.0, features.shape[1])
            weighted = features * weights.reshape(1, -1, 1)
            predictions = weighted.mean(axis=(1, 2))
        else:
            predictions = features.mean(axis=1)

        # 归一化到[0, 1]
        predictions = (predictions - predictions.min()) / (predictions.max() - predictions.min() + 1e-8)

        return predictions

    def get_attention_weights(self, features: np.ndarray) -> np.ndarray:
        """
        获取注意力权重

        Args:
            features: (n_samples, sequence_length, input_size)

        Returns:
            attention_weights: (n_samples, nhead, sequence_length, sequence_length)
        """
        if not TORCH_AVAILABLE or self.model is None:
            logger.warning("Attention weights not available without PyTorch")
            return None

        # 这里需要修改模型以返回注意力权重
        # 简化实现：返回None
        logger.info("Attention weights extraction not implemented yet")
        return None
