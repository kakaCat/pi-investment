"""
LSTM预测模型测试 - Team B
"""
import pytest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from domain.quantlib.ml.lstm_predictor import LSTMPredictor


class TestLSTMPredictor:
    """LSTM预测模型测试"""

    @pytest.fixture
    def predictor(self):
        """创建预测器实例"""
        return LSTMPredictor(
            input_size=5,
            hidden_size=32,
            num_layers=2,
            sequence_length=10
        )

    @pytest.fixture
    def sample_data(self):
        """生成样本数据"""
        np.random.seed(42)
        n_samples = 100
        n_features = 5

        data = np.random.randn(n_samples, n_features)
        return data

    def test_initialization(self, predictor):
        """测试初始化"""
        assert predictor is not None
        assert predictor.input_size == 5
        assert predictor.hidden_size == 32
        assert predictor.num_layers == 2

    def test_predict_shape(self, predictor):
        """测试预测输出形状"""
        # 创建序列数据 (batch, seq_len, features)
        X = np.random.randn(10, 10, 5)

        predictions = predictor.predict(X)

        assert predictions.shape == (10,)
        assert np.all((predictions >= 0) & (predictions <= 1))

    def test_predict_proba_shape(self, predictor):
        """测试概率预测形状"""
        X = np.random.randn(10, 10, 5)

        proba = predictor.predict_proba(X)

        assert proba.shape == (10, 2)
        assert np.allclose(proba.sum(axis=1), 1.0)

    def test_feature_importance(self, predictor):
        """测试特征重要性"""
        importance = predictor.get_feature_importance()

        assert len(importance) == 5
        assert all(v > 0 for v in importance.values())

    def test_prepare_sequences(self, predictor, sample_data):
        """测试序列准备"""
        df = pd.DataFrame(sample_data, columns=[f'f{i}' for i in range(5)])
        df['target'] = np.random.randint(0, 2, len(df))

        X, y = predictor.prepare_sequences(df, target_col='target')

        assert X.shape[1] == predictor.sequence_length
        assert X.shape[2] == 5
        assert len(y) == len(X)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
