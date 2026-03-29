#!/usr/bin/env python3
"""
信号置信度预测器 - XGBoost
"""
import pickle
import os
import numpy as np

MODEL_PATH = '.pi-invest/quant/models/signal_confidence.pkl'


def predict(features: dict) -> dict:
    """
    预测信号置信度

    Args:
        features: {
            'rsi': float,
            'ma5_ma20_ratio': float,
            'ma20_ma60_ratio': float,
            'macd_histogram': float,
            'bb_position': float,
            'volume_ratio': float,
            'conditions_matched_ratio': float,
            'action': int  # 0=buy, 1=sell
        }

    Returns:
        {'confidence': float | None, 'model': 'xgboost' | 'none'}
    """
    if not os.path.exists(MODEL_PATH):
        return {"confidence": None, "model": "none"}

    try:
        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)

        # 特征顺序必须和训练时一致
        X = np.array([[
            features['rsi'],
            features['ma5_ma20_ratio'],
            features['ma20_ma60_ratio'],
            features['macd_histogram'],
            features['bb_position'],
            features['volume_ratio'],
            features['conditions_matched_ratio'],
            features['action']
        ]])

        proba = model.predict_proba(X)[0][1]  # 正类概率
        return {"confidence": float(proba), "model": "xgboost"}

    except Exception as e:
        return {"confidence": None, "model": "none", "error": str(e)}
