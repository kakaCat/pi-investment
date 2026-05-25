# Strategy Layer

This directory contains the strategy layer for quantitative trading.

## Structure

```
strategies/
├── base.py                     # BaseStrategy class
├── utils.py                    # Strategy utility functions
├── backtest.py                 # Backtesting engine
├── test_strategies.py          # Quick test script
└── classic/
    ├── __init__.py
    ├── ma_cross.py            # MA Crossover Strategy
    ├── rsi_reversal.py        # RSI Reversal Strategy
    └── bollinger_breakout.py  # Bollinger Breakout Strategy
```

## Implemented Strategies

### 1. MA Cross Strategy (MACrossStrategy)
- **Type**: Trend Following
- **Entry**: Golden Cross (MA5 crosses above MA20)
- **Exit**: Death Cross (MA5 crosses below MA20)
- **Stop Loss**: 5%
- **Take Profit**: 15%

### 2. RSI Reversal Strategy (RSIReversalStrategy)
- **Type**: Mean Reversion
- **Entry**: RSI crosses below 30 (oversold)
- **Exit**: RSI crosses above 70 (overbought)
- **Stop Loss**: 5%
- **Take Profit**: 10%

### 3. Bollinger Breakout Strategy (BollingerBreakoutStrategy)
- **Type**: Mean Reversion
- **Entry**: Price touches lower Bollinger Band
- **Exit**: Price touches upper Bollinger Band or reverts to middle band
- **Stop Loss**: 5%
- **Take Profit**: 10%

## Usage

### Quick Test
```bash
python python/strategies/test_strategies.py
```

### Backtest Single Strategy
```bash
python -m python.strategies.backtest \
  --strategy ma_cross \
  --symbol 000001.SZ \
  --start 2015-01-01 \
  --end 2025-12-31 \
  --capital 100000 \
  --output results.json
```

### Available Strategies
- `ma_cross`: MA Crossover Strategy
- `rsi_reversal`: RSI Reversal Strategy
- `bollinger_breakout`: Bollinger Breakout Strategy

## Creating Custom Strategies

Extend `BaseStrategy` and implement `calculate_signals()`:

```python
from strategies.base import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    def __init__(self, params):
        super().__init__(params)
        self.name = 'My_Strategy'
    
    def calculate_signals(self, data):
        signals = []
        # Your logic here
        return signals
```

## Performance Metrics

The backtesting engine calculates:
- Total Return
- Win Rate
- Profit Factor
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Maximum Drawdown
- Average Holding Period

## Next Steps

1. Run backtests on multiple stocks (2015-2025)
2. Parameter optimization
3. Walk-forward analysis
4. Out-of-sample testing
5. Integration with factor library (when available)
