# Indicator Tools Usage Guide

This guide demonstrates how to use the indicator tools system for creating, testing, and comparing custom trading strategies.

## Table of Contents

1. [CLI Commands](#cli-commands)
2. [API Endpoints](#api-endpoints)
3. [Common Workflows](#common-workflows)
4. [Advanced Features](#advanced-features)

## CLI Commands

### List Indicators

```bash
# List all your custom indicators
python cli/main.py indicators list --type my

# List system-provided indicators
python cli/main.py indicators list --type system

# Output as JSON
python cli/main.py indicators list --type my --format json
```

### Create Indicator

```bash
# Create from inline code
python cli/main.py indicators create \
  --name "RSI Oversold Strategy" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70" \
  --description "Buy when RSI < 30, sell when RSI > 70"

# Create from file
python cli/main.py indicators create \
  --name "Complex Strategy" \
  --code /path/to/strategy.py \
  --description "Multi-factor strategy"

# Output as JSON to capture ID
python cli/main.py indicators create \
  --name "My Strategy" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70" \
  --format json
```

### Update Indicator

```bash
# Update code
python cli/main.py indicators update \
  --id 1 \
  --code "df['buy'] = (df['rsi'] < 30) & (df['macd'] > 0); df['sell'] = df['rsi'] > 70"

# Update from file
python cli/main.py indicators update \
  --id 1 \
  --code /path/to/new_strategy.py
```

### Run Indicator

```bash
# Run on recent data (default 100 bars)
python cli/main.py indicators run \
  --id 1 \
  --symbol 600000.SH

# Run on specific number of bars
python cli/main.py indicators run \
  --id 1 \
  --symbol 600000.SH \
  --limit 200

# Output as JSON
python cli/main.py indicators run \
  --id 1 \
  --symbol 600000.SH \
  --format json
```

### Backtest Indicator

```bash
# Backtest over date range
python cli/main.py indicators backtest \
  --id 1 \
  --symbol 600000.SH \
  --start 2024-01-01 \
  --end 2024-12-31

# Output as JSON
python cli/main.py indicators backtest \
  --id 1 \
  --symbol 600000.SH \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --format json
```

## API Endpoints

### Sandbox Column Exploration

Discover available columns in the strategy sandbox:

```bash
curl "http://127.0.0.1:5001/api/indicators/sandbox-columns?symbol=600000.SH"
```

Response:
```json
{
  "success": true,
  "data": {
    "columns": {
      "price": ["open", "high", "low", "close", "volume"],
      "technical": ["rsi", "macd", "macd_signal", "macd_hist", "bb_upper", "bb_middle", "bb_lower"],
      "fundamental": ["pe_ratio", "pb_ratio", "roe_q", "debt_ratio_q", "gross_margin_q"],
      "derived": ["returns", "log_returns"]
    },
    "sampleRow": {
      "date": "2024-12-31",
      "close": 1520.50,
      "rsi": 65.3,
      "pe_ratio": 28.5
    }
  }
}
```

### Strategy Comparison

Compare two strategies side-by-side:

```bash
curl -X POST http://127.0.0.1:5001/api/indicators/compare \
  -H "Content-Type: application/json" \
  -d '{
    "indicatorIdA": 1,
    "indicatorIdB": 2,
    "symbol": "600000.SH",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }'
```

Response:
```json
{
  "success": true,
  "data": {
    "comparison": {
      "commonSignals": 15,
      "uniqueToA": 8,
      "uniqueToB": 12,
      "filteredByAOnly": 3,
      "filteredByBOnly": 7
    },
    "backtestA": {
      "summary": {
        "totalReturn": 0.25,
        "sharpeRatio": 1.8,
        "maxDrawdown": -0.12
      }
    },
    "backtestB": {
      "summary": {
        "totalReturn": 0.32,
        "sharpeRatio": 2.1,
        "maxDrawdown": -0.09
      }
    }
  }
}
```

### Backtest with Summary

```bash
curl -X POST http://127.0.0.1:5001/api/indicators/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "indicatorId": 1,
    "symbol": "600000.SH",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }'
```

Response includes `summary` field:
```json
{
  "success": true,
  "data": {
    "summary": {
      "totalReturn": 0.25,
      "annualizedReturn": 0.28,
      "sharpeRatio": 1.8,
      "maxDrawdown": -0.12,
      "winRate": 0.65,
      "totalTrades": 24
    },
    "trades": [...],
    "equity": [...]
  }
}
```

## Common Workflows

### Workflow 1: Create and Test a Simple Strategy

```bash
# 1. Create strategy
INDICATOR_ID=$(python cli/main.py indicators create \
  --name "RSI Mean Reversion" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70" \
  --format json | jq -r '.id')

# 2. Test on recent data
python cli/main.py indicators run \
  --id $INDICATOR_ID \
  --symbol 600000.SH \
  --limit 100

# 3. Full backtest
python cli/main.py indicators backtest \
  --id $INDICATOR_ID \
  --symbol 600000.SH \
  --start 2024-01-01 \
  --end 2024-12-31
```

### Workflow 2: Explore Available Columns

```bash
# 1. Check available columns
curl "http://127.0.0.1:5001/api/indicators/sandbox-columns?symbol=600000.SH" | jq '.data.columns'

# 2. Create strategy using discovered columns
python cli/main.py indicators create \
  --name "Multi-Factor Strategy" \
  --code "df['buy'] = (df['rsi'] < 30) & (df['roe_q'] > 15) & (df['debt_ratio_q'] < 60); df['sell'] = df['rsi'] > 70"
```

### Workflow 3: Compare Two Strategies

```bash
# 1. Create baseline strategy
ID_A=$(python cli/main.py indicators create \
  --name "Simple RSI" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70" \
  --format json | jq -r '.id')

# 2. Create enhanced strategy
ID_B=$(python cli/main.py indicators create \
  --name "RSI + Fundamentals" \
  --code "df['buy'] = (df['rsi'] < 30) & (df['roe_q'] > 15); df['sell'] = df['rsi'] > 70" \
  --format json | jq -r '.id')

# 3. Compare
curl -X POST http://127.0.0.1:5001/api/indicators/compare \
  -H "Content-Type: application/json" \
  -d "{
    \"indicatorIdA\": $ID_A,
    \"indicatorIdB\": $ID_B,
    \"symbol\": \"600000.SH\",
    \"startDate\": \"2024-01-01\",
    \"endDate\": \"2024-12-31\"
  }" | jq '.data.comparison'
```

### Workflow 4: Iterate on Strategy

```bash
# 1. Create initial version
INDICATOR_ID=$(python cli/main.py indicators create \
  --name "My Strategy v1" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70" \
  --format json | jq -r '.id')

# 2. Test
python cli/main.py indicators backtest \
  --id $INDICATOR_ID \
  --symbol 600000.SH \
  --start 2024-01-01 \
  --end 2024-12-31

# 3. Update based on results
python cli/main.py indicators update \
  --id $INDICATOR_ID \
  --code "df['buy'] = (df['rsi'] < 30) & (df['macd'] > 0); df['sell'] = df['rsi'] > 70"

# 4. Re-test
python cli/main.py indicators backtest \
  --id $INDICATOR_ID \
  --symbol 600000.SH \
  --start 2024-01-01 \
  --end 2024-12-31
```

## Advanced Features

### Using Fundamental Data

```python
# Strategy code with fundamental filters
df['quality'] = (df['roe_q'] > 15) & (df['debt_ratio_q'] < 60) & (df['gross_margin_q'] > 30)
df['buy'] = df['quality'] & (df['rsi'] < 30)
df['sell'] = df['rsi'] > 70
```

### Multi-Condition Strategies

```python
# Complex entry conditions
df['oversold'] = df['rsi'] < 30
df['macd_bullish'] = df['macd'] > df['macd_signal']
df['volume_surge'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5

df['buy'] = df['oversold'] & df['macd_bullish'] & df['volume_surge']
df['sell'] = df['rsi'] > 70
```

### Bollinger Band Strategies

```python
# Mean reversion using Bollinger Bands
df['buy'] = df['close'] < df['bb_lower']
df['sell'] = df['close'] > df['bb_upper']
```

### Trend Following

```python
# MACD crossover strategy
df['buy'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
df['sell'] = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))
```

## Best Practices

1. **Start Simple**: Begin with single-factor strategies and add complexity gradually
2. **Use Column Exploration**: Always check available columns before writing strategy code
3. **Test on Recent Data First**: Use `indicators run` with small limit before full backtest
4. **Compare Variations**: Use the comparison API to evaluate incremental improvements
5. **Handle NaN Values**: Early rows may have NaN for indicators requiring history
6. **Version Your Strategies**: Create new indicators rather than overwriting when testing major changes

## Troubleshooting

### Strategy Returns No Signals

```bash
# Check if columns exist
curl "http://127.0.0.1:5001/api/indicators/sandbox-columns?symbol=600000.SH"

# Verify strategy logic with simple test
python cli/main.py indicators run --id 1 --symbol 600000.SH --limit 50
```

### Backtest Fails

- Ensure date range has sufficient data
- Check that symbol is valid (e.g., `600000.SH` not `600000`)
- Verify strategy code doesn't have syntax errors

### Missing Fundamental Data

- Not all stocks have complete fundamental data
- Use `.fillna()` or conditional checks in strategy code
- Test with large-cap stocks first (e.g., 600000.SH, 000001.SZ)

## Examples

See `quantsys-v2/examples/` for complete strategy examples:
- `strategy_with_financials.py` - Using fundamental data
- `strategy_technical_only.py` - Pure technical indicators
- `strategy_multi_factor.py` - Combined approach
