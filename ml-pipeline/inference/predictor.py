"""信号预测器"""

import pickle
from pathlib import Path

import pandas as pd


class SignalPredictor:
    def __init__(self, model_path: str = "ml-pipeline/models/signal_model.pkl"):
        self.model_path = Path(model_path)
        self.model = None

    def load(self):
        with open(self.model_path, 'rb') as f:
            self.model = pickle.load(f)

    def predict(self, X: pd.DataFrame):
        if self.model is None:
            self.load()
        proba = self.model.predict_proba(X)
        return proba[:, 1]
