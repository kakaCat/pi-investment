# ML Pipeline Phase 6: 完善回测指标

## 目标
在回测引擎中添加夏普比率、最大回撤、胜率等关键指标。

## 回测指标计算

### 更新 backtesting/engine.py

```python
def run(self, df: pd.DataFrame, signals: pd.Series):
    # ... 现有回测逻辑 ...

    # 计算详细指标
    final_value = self.capital + self.position * df['close'].iloc[-1]
    total_return = (final_value / self.initial_capital - 1) * 100

    # 胜率
    winning_trades = [t for t in self.trades if t['action'].startswith('sell') and self._is_winning_trade(t)]
    win_rate = len(winning_trades) / len([t for t in self.trades if t['action'].startswith('sell')]) if len([t for t in self.trades if t['action'].startswith('sell')]) > 0 else 0

    # 最大回撤
    max_drawdown = self._calculate_max_drawdown(df, signals)

    # 夏普比率
    sharpe_ratio = self._calculate_sharpe_ratio(df, signals)

    return {
        'initial_capital': self.initial_capital,
        'final_value': final_value,
        'return': total_return,
        'trades': len(self.trades),
        'win_rate': win_rate * 100,
        'max_drawdown': max_drawdown * 100,
        'sharpe_ratio': sharpe_ratio
    }

def _calculate_max_drawdown(self, df, signals):
    # 计算每日资产净值
    equity_curve = []
    capital = self.initial_capital
    position = 0

    for i in range(len(df)):
        # 简化：重新模拟获取净值曲线
        equity = capital + position * df['close'].iloc[i]
        equity_curve.append(equity)

    # 计算最大回撤
    peak = equity_curve[0]
    max_dd = 0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd

def _calculate_sharpe_ratio(self, df, signals):
    # 简化：假设无风险利率为0，计算日收益率的夏普比率
    # 实际应该用净值曲线计算
    if len(self.trades) < 2:
        return 0
    returns = []
    for i in range(1, len(self.trades)):
        if self.trades[i]['action'].startswith('sell'):
            buy_price = self.trades[i-1]['price']
            sell_price = self.trades[i]['price']
            ret = (sell_price - buy_price) / buy_price
            returns.append(ret)
    if len(returns) == 0:
        return 0
    import numpy as np
    return np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
```

## 实现步骤

1. 更新 backtesting/engine.py 添加指标计算方法
2. 更新 backtest 命令输出格式
3. 测试回测命令查看新指标
