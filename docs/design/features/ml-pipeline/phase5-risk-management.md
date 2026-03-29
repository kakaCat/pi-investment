# ML Pipeline Phase 5: 风险管理

## 目标
在回测引擎中添加止损、止盈、仓位管理功能。

## 风险管理模块

### backtesting/risk_manager.py

```python
"""风险管理器"""

class RiskManager:
    def __init__(self, stop_loss: float = 0.05, take_profit: float = 0.10, max_position: float = 0.3):
        self.stop_loss = stop_loss  # 止损比例 5%
        self.take_profit = take_profit  # 止盈比例 10%
        self.max_position = max_position  # 最大仓位 30%

    def should_stop_loss(self, buy_price: float, current_price: float) -> bool:
        return (current_price - buy_price) / buy_price < -self.stop_loss

    def should_take_profit(self, buy_price: float, current_price: float) -> bool:
        return (current_price - buy_price) / buy_price > self.take_profit

    def calculate_position_size(self, capital: float, price: float) -> float:
        max_shares = (capital * self.max_position) / price
        return max_shares
```

### 更新 backtesting/engine.py

```python
class BacktestEngine:
    def __init__(self, initial_capital: float = 100000, risk_manager: RiskManager = None):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0
        self.buy_price = 0
        self.trades = []
        self.risk_manager = risk_manager or RiskManager()

    def run(self, df: pd.DataFrame, signals: pd.Series):
        for i in range(len(df)):
            current_price = df['close'].iloc[i]

            # 检查止损止盈
            if self.position > 0:
                if self.risk_manager.should_stop_loss(self.buy_price, current_price):
                    # 止损卖出
                    self.capital = self.position * current_price
                    self.trades.append({
                        'date': df['date'].iloc[i],
                        'action': 'sell_stop_loss',
                        'price': current_price,
                        'shares': self.position
                    })
                    self.position = 0
                    continue

                if self.risk_manager.should_take_profit(self.buy_price, current_price):
                    # 止盈卖出
                    self.capital = self.position * current_price
                    self.trades.append({
                        'date': df['date'].iloc[i],
                        'action': 'sell_take_profit',
                        'price': current_price,
                        'shares': self.position
                    })
                    self.position = 0
                    continue

            # 买入信号
            if signals.iloc[i] == 1 and self.position == 0:
                shares = self.risk_manager.calculate_position_size(self.capital, current_price)
                cost = shares * current_price
                if cost <= self.capital:
                    self.position = shares
                    self.buy_price = current_price
                    self.capital -= cost
                    self.trades.append({
                        'date': df['date'].iloc[i],
                        'action': 'buy',
                        'price': current_price,
                        'shares': shares
                    })
```

## 实现步骤

1. 创建 backtesting/risk_manager.py
2. 更新 backtesting/engine.py 集成风险管理
3. 测试回测命令验证止损止盈
