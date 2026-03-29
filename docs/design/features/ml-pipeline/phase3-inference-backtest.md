# ML Pipeline Phase 3: 推理与回测

## Phase 3.1: 推理功能

### inference/predictor.py

```python
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
        return proba[:, 1]  # 返回上涨概率
```

### ml_pipeline.py predict 命令

```python
def _predict_signal(symbol: str) -> int:
    db = Database()
    try:
        df = db.get_klines(symbol, 500)
        if df.empty:
            print(f"[Predict] 错误: 没有 {symbol} 的数据")
            return 1

        featured = TechnicalFeatures.calculate_all(df)
        if featured.empty:
            print(f"[Predict] 错误: 特征计算失败")
            return 1

        X = featured.drop(columns=["label", "symbol", "date"], errors="ignore")
        X = X.select_dtypes(include="number")

        predictor = SignalPredictor()
        proba = predictor.predict(X.tail(1))

        print(f"[Predict] {symbol}")
        print(f"上涨概率: {proba[0]:.2%}")
        print(f"信号: {'买入' if proba[0] > 0.6 else '观望'}")
        return 0
    finally:
        db.close()
```

## Phase 3.2: 回测引擎

### backtesting/engine.py

```python
"""回测引擎"""
import pandas as pd


class BacktestEngine:
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0
        self.trades = []

    def run(self, df: pd.DataFrame, signals: pd.Series):
        """
        df: 包含 date/close 的K线数据
        signals: 买入信号（1=买入，0=不操作）
        """
        for i in range(len(df)):
            if signals.iloc[i] == 1 and self.position == 0:
                # 买入
                self.position = self.capital / df['close'].iloc[i]
                self.trades.append({
                    'date': df['date'].iloc[i],
                    'action': 'buy',
                    'price': df['close'].iloc[i],
                    'shares': self.position
                })
                self.capital = 0
            elif self.position > 0 and i == len(df) - 1:
                # 最后一天卖出
                self.capital = self.position * df['close'].iloc[i]
                self.trades.append({
                    'date': df['date'].iloc[i],
                    'action': 'sell',
                    'price': df['close'].iloc[i],
                    'shares': self.position
                })
                self.position = 0

        final_value = self.capital + self.position * df['close'].iloc[-1]
        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'return': (final_value / self.initial_capital - 1) * 100,
            'trades': len(self.trades)
        }
```

### ml_pipeline.py backtest 命令

```python
def _backtest_signal() -> int:
    db = Database()
    try:
        symbols = db.get_all_symbols()[:5]
        predictor = SignalPredictor()

        results = []
        for symbol in symbols:
            df = db.get_klines(symbol, 500)
            if df.empty:
                continue

            featured = TechnicalFeatures.calculate_all(df)
            X = featured.drop(columns=["label", "symbol", "date"], errors="ignore")
            proba = predictor.predict(X)
            signals = (proba > 0.6).astype(int)

            engine = BacktestEngine()
            result = engine.run(featured[['date', 'close']], pd.Series(signals))
            results.append({'symbol': symbol, **result})

        print("[Backtest] 回测结果")
        for r in results:
            print(f"{r['symbol']}: 收益率 {r['return']:.2f}%, 交易次数 {r['trades']}")
        return 0
    finally:
        db.close()
```

## 实现步骤

1. 实现 inference/predictor.py
2. 实现 backtesting/engine.py
3. 更新 ml_pipeline.py 添加 predict 和 backtest 命令
4. 测试: python ml-pipeline/ml_pipeline.py predict --symbol 600519
5. 测试: python ml-pipeline/ml_pipeline.py backtest
