# ML Pipeline Phase 2: 特征工程与模型训练

## 目标

实现完整的特征工程和 XGBoost 模型训练流程。

## 数据流

```
Pipeline 数据库 (stocks.db)
  ↓ 读取
特征工程 (features/technical.py)
  ↓ 计算
训练数据集 (X, y)
  ↓ 训练
XGBoost 模型
  ↓ 保存
models/signal_model.pkl
```

## Phase 2.1: 技术特征工程

### features/technical.py

```python
"""技术特征计算"""
import pandas as pd
import numpy as np
from typing import List, Dict


class TechnicalFeatures:
    """技术指标特征工程"""

    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """计算移动平均线"""
        for period in periods:
            df[f'ma{period}'] = df['close'].rolling(period).mean()
        return df

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df

    @staticmethod
    def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
        """计算MACD"""
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        return df

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        df = TechnicalFeatures.calculate_ma(df)
        df = TechnicalFeatures.calculate_rsi(df)
        df = TechnicalFeatures.calculate_macd(df)

        # 价格变化率
        df['price_change'] = df['close'].pct_change()
        df['volume_change'] = df['volume'].pct_change()

        # 标签：未来5日涨跌（>3%为1，否则0）
        df['label'] = (df['close'].shift(-5) / df['close'] - 1 > 0.03).astype(int)

        return df.dropna()
```

## Phase 2.2: 模型训练

### training/trainer.py

```python
"""模型训练器"""
import pickle
from pathlib import Path
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split


class SignalTrainer:
    """信号预测模型训练器"""

    def __init__(self, model_dir: str = "ml-pipeline/models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.model = None

    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """训练模型"""
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self.model = xgb.XGBClassifier(
            max_depth=5,
            learning_rate=0.1,
            n_estimators=100,
            random_state=42
        )

        self.model.fit(X_train, y_train)

        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)

        return {
            "train_score": train_score,
            "test_score": test_score,
            "n_samples": len(X)
        }

    def save(self, name: str = "signal_model.pkl"):
        """保存模型"""
        path = self.model_dir / name
        with open(path, 'wb') as f:
            pickle.dump(self.model, f)
        return str(path)

    def load(self, name: str = "signal_model.pkl"):
        """加载模型"""
        path = self.model_dir / name
        with open(path, 'rb') as f:
            self.model = pickle.load(f)
```

## Phase 2.3: CLI 集成

### ml_pipeline.py 更新

```python
def main(argv=None):
    # ... 现有代码 ...

    if args.command == 'train':
        from db import Database
        from features.technical import TechnicalFeatures
        from training.trainer import SignalTrainer

        # 1. 读取数据
        db = Database('.pi-invest/stock-db/stocks.db')
        symbols = db.get_all_symbols()[:10]  # 先用10只股票测试

        all_features = []
        for symbol in symbols:
            df = db.get_klines(symbol, limit=500)
            if len(df) < 100:
                continue
            features = TechnicalFeatures.calculate_all(df)
            all_features.append(features)

        # 2. 合并数据
        data = pd.concat(all_features, ignore_index=True)
        X = data.drop(['label', 'date', 'symbol'], axis=1)
        y = data['label']

        # 3. 训练
        trainer = SignalTrainer()
        metrics = trainer.train(X, y)
        model_path = trainer.save()

        print(f"[Train] 训练完成")
        print(f"  训练集准确率: {metrics['train_score']:.2%}")
        print(f"  测试集准确率: {metrics['test_score']:.2%}")
        print(f"  模型保存: {model_path}")
```

## 实现步骤

1. 实现 `features/technical.py` - TechnicalFeatures 类
2. 实现 `training/trainer.py` - SignalTrainer 类
3. 更新 `ml_pipeline.py` - train 命令集成
4. 测试：`python ml-pipeline/ml_pipeline.py train`
5. 验证生成 `models/signal_model.pkl`
