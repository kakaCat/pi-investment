"""模型训练器"""
import pickle
from pathlib import Path
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split


class SignalTrainer:
    def __init__(self, model_dir: str = "ml-pipeline/models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.model = None

    def train(self, X: pd.DataFrame, y: pd.Series):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # 计算类别权重
        scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()

        self.model = xgb.XGBClassifier(
            max_depth=5,
            learning_rate=0.1,
            n_estimators=100,
            scale_pos_weight=scale_pos_weight,
            random_state=42
        )
        self.model.fit(X_train, y_train)
        return {
            "train_score": self.model.score(X_train, y_train),
            "test_score": self.model.score(X_test, y_test),
            "n_samples": len(X)
        }

    def save(self, name: str = "signal_model.pkl"):
        path = self.model_dir / name
        with open(path, 'wb') as f:
            pickle.dump(self.model, f)
        return str(path)

    def load(self, name: str = "signal_model.pkl"):
        path = self.model_dir / name
        with open(path, 'rb') as f:
            self.model = pickle.load(f)
