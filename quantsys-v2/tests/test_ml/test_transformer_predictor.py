"""
Transformer预测模型测试 - Team B
"""
import pytest
import numpy as np
import pandas as pd
import sys
import os


from domain.quantlib.ml.transformer_predictor import TransformerPredictor


class TestTransformerPredictor:
    """Transformer预测模型测试"""

    @pytest.fixture
    def predictor(self):
        """创建预测器实例"""
        return TransformerPredictor(
            input_size=5,
            d_model=64,
            nhead=4,
            num_layers=2,
            sequence_length=10
        )

    def test_initialization(self, predictor):
        """测试初始化"""
        assert predictor is not None
        assert predictor.input_size == 5
        assert predictor.d_model == 64
        assert predictor.nhead == 4

    def test_predict_shape(self, predictor):
        """测试预测输出形状"""
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
