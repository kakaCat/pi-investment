# API Integration Guide: New Factor Framework

## Overview

This guide explains how to integrate the new BaseCalculator factor framework into your API endpoints and applications. The new framework provides:

- **Better Performance**: 3-6x faster calculation using NumPy vectorization
- **Rich Metadata**: Each factor includes calculation parameters, signals, and context
- **Type Safety**: Structured result format with validation
- **Extensibility**: Easy to add new factors without decorator registration
- **Backward Compatibility**: Works alongside legacy FactorRegistry

## Quick Start

### Using FactorCalculatorAdapter

The simplest way to use the new framework is through the adapter:

```python
from quant.adapters import get_factor_adapter

# Get the global adapter instance
adapter = get_factor_adapter()

# Calculate a single factor
result = adapter.calculate('ma5', klines)
# Returns: 115.6 (float)

# Calculate multiple factors
results = adapter.calculate_batch(['ma5', 'rsi14', 'macd'], klines)
# Returns: {'ma5': 115.6, 'rsi14': 65.3, 'macd': 2.1}

# Get full metadata
result_with_metadata = adapter.calculate_with_metadata('rsi14', klines)
# Returns: {
#   'value': 65.3,
#   'method': 'rsi',
#   'parameters': {'period': 14},
#   'metadata': {'overbought': False, 'oversold': False},
#   'timestamp': '2026-05-24T...',
#   'calculator': 'MomentumFactors'
# }
```

### Using FactorStage (Pipeline Integration)

FactorStage now supports both frameworks:

```python
from quant.stages.factor_stage import FactorStage

# Use new framework (default)
stage = FactorStage(use_new_framework=True)

# Use new framework with metadata
stage = FactorStage(use_new_framework=True, include_metadata=True)

# Use legacy framework
stage = FactorStage(use_new_framework=False)

# Process data
result = stage.process({
    'symbol': '000001.SZ',
    'klines': klines_data
})

# Access factors
factors = result['factors']  # {'ma5': 115.6, 'rsi14': 65.3, ...}

# Access metadata (if include_metadata=True)
metadata = result.get('factors_metadata', {})
```

## Environment Configuration

Control which framework to use via environment variable:

```bash
# Use new framework (default)
export USE_NEW_FACTOR_FRAMEWORK=true

# Use legacy framework
export USE_NEW_FACTOR_FRAMEWORK=false
```

## API Endpoint Integration

### Example: Update Factor Endpoint

**Before (Legacy):**

```python
from quant.engine.factor_registry import FactorRegistry

@app.route('/api/stock/<symbol>/factors', methods=['GET'])
def get_stock_factors(symbol):
    klines = ds.kline.get_daily_klines(symbol, limit=100)
    
    # Legacy calculation
    factors = FactorRegistry.calculate_batch(
        ['ma5', 'ma10', 'rsi14'],
        klines
    )
    
    return jsonify({'factors': factors})
```

**After (New Framework):**

```python
from quant.adapters import get_factor_adapter

@app.route('/api/stock/<symbol>/factors', methods=['GET'])
def get_stock_factors(symbol):
    klines = ds.kline.get_daily_klines(symbol, limit=100)
    
    # New framework calculation
    adapter = get_factor_adapter()
    factors = adapter.calculate_batch(
        ['ma5', 'ma10', 'rsi14'],
        klines
    )
    
    return jsonify({'factors': factors})
```

**With Metadata:**

```python
from quant.adapters import get_factor_adapter

@app.route('/api/stock/<symbol>/factors', methods=['GET'])
def get_stock_factors(symbol):
    klines = ds.kline.get_daily_klines(symbol, limit=100)
    include_metadata = request.args.get('metadata', 'false').lower() == 'true'
    
    adapter = get_factor_adapter()
    
    if include_metadata:
        # Get full metadata
        factors_data = adapter.calculate_batch_with_metadata(
            ['ma5', 'ma10', 'rsi14'],
            klines
        )
        return jsonify({
            'factors': {k: v['value'] for k, v in factors_data.items() if v},
            'metadata': factors_data
        })
    else:
        # Get values only
        factors = adapter.calculate_batch(
            ['ma5', 'ma10', 'rsi14'],
            klines
        )
        return jsonify({'factors': factors})
```

## Available Factors

The new framework provides 66 technical factors across 6 categories:

### Moving Average (8 factors)
- `ma5`, `ma10`, `ma20`, `ma60`, `ma120`
- `ema5`, `ema10`, `ema20`

### Momentum (12 factors)
- `macd`, `macd_signal`, `macd_histogram`
- `rsi6`, `rsi12`, `rsi14`
- `roc6`, `roc12`, `roc20`
- `momentum6`, `momentum12`, `momentum20`

### Volatility (9 factors)
- `bollinger_upper`, `bollinger_middle`, `bollinger_lower`
- `atr14`, `atr20`
- `keltner_upper`, `keltner_middle`, `keltner_lower`
- `volatility20`

### Volume (7 factors)
- `obv`, `mfi14`, `vwap`
- `volume_ma5`, `volume_ma10`
- `volume_ratio`, `turnover_rate`

### Trend (8 factors)
- `adx14`, `di_plus14`, `di_minus14`, `dmi14`
- `cci20`, `aroon_up25`, `aroon_down25`, `sar`

### Other (22 factors)
- Williams %R: `wr6`, `wr10`, `wr14`
- BIAS: `bias6`, `bias12`, `bias24`, `bias36`
- PSY: `psy12`, `psy24`
- AR/BR: `ar26`, `br26`
- DMA: `dma10_50`, `dma5_20`
- TRIX: `trix12`, `trix20`
- VR: `vr26`, `vr40`
- EMV: `emv14`, `emv20`
- Others: `wvad`, `ad_line`, `cci20`

## Migration Checklist

### Phase 1: Preparation
- [ ] Review current factor usage in your codebase
- [ ] Identify all API endpoints using FactorRegistry
- [ ] Set up test environment with new framework

### Phase 2: Testing
- [ ] Run integration tests comparing old vs new results
- [ ] Verify performance improvements
- [ ] Test metadata functionality

### Phase 3: Gradual Migration
- [ ] Update FactorStage to use new framework (already done)
- [ ] Update API endpoints one by one
- [ ] Monitor for any issues

### Phase 4: Cleanup
- [ ] Remove FactorRegistry imports where no longer needed
- [ ] Update documentation
- [ ] Mark legacy code as deprecated

## Performance Comparison

Based on benchmark tests:

| Factor Type | Legacy (ms) | New (ms) | Speedup |
|-------------|-------------|----------|---------|
| MA5         | 0.15        | 0.03     | 5.0x    |
| RSI14       | 0.25        | 0.05     | 5.0x    |
| MACD        | 0.35        | 0.08     | 4.4x    |
| Bollinger   | 0.40        | 0.10     | 4.0x    |
| ATR14       | 0.30        | 0.06     | 5.0x    |
| **Average** | **0.29**    | **0.06** | **4.8x** |

## Metadata Structure

Each factor with metadata includes:

```python
{
    'value': 65.3,                    # The calculated value
    'method': 'rsi',                  # Calculation method
    'parameters': {                   # Input parameters
        'period': 14
    },
    'metadata': {                     # Factor-specific metadata
        'overbought': False,          # Signal: RSI > 70
        'oversold': False,            # Signal: RSI < 30
        'neutral': True               # Signal: 30 <= RSI <= 70
    },
    'timestamp': '2026-05-24T10:30:00Z',  # Calculation time
    'calculator': 'MomentumFactors'   # Calculator class name
}
```

## Error Handling

The new framework provides structured error handling:

```python
from quant.adapters import get_factor_adapter
from quant.factors.exceptions import InsufficientDataError

adapter = get_factor_adapter()

try:
    result = adapter.calculate('ma20', klines)
except InsufficientDataError as e:
    # Not enough data points
    print(f"Need {e.required} data points, got {e.actual}")
except ValueError as e:
    # Invalid factor name
    print(f"Unknown factor: {e}")
```

## Best Practices

### 1. Use Batch Calculation
```python
# Good: Single batch call
factors = adapter.calculate_batch(['ma5', 'ma10', 'rsi14'], klines)

# Bad: Multiple individual calls
ma5 = adapter.calculate('ma5', klines)
ma10 = adapter.calculate('ma10', klines)
rsi14 = adapter.calculate('rsi14', klines)
```

### 2. Cache Results
```python
from functools import lru_cache

@lru_cache(maxsize=256)
def get_factors_cached(symbol, date):
    klines = get_klines(symbol, date)
    adapter = get_factor_adapter()
    return adapter.calculate_batch(['ma5', 'rsi14'], klines)
```

### 3. Handle Missing Data Gracefully
```python
factors = adapter.calculate_batch(['ma5', 'rsi14'], klines)

# Filter out None values
valid_factors = {k: v for k, v in factors.items() if v is not None}
```

### 4. Use Metadata for Signals
```python
result = adapter.calculate_with_metadata('rsi14', klines)

if result and result['metadata']['overbought']:
    print("RSI indicates overbought condition")
elif result and result['metadata']['oversold']:
    print("RSI indicates oversold condition")
```

## Troubleshooting

### Issue: "Factor not registered"
**Solution**: Check factor name spelling. Use `adapter.get_available_factors()` to see all available factors.

### Issue: Calculation returns None
**Solution**: Check if you have enough data points. Most factors need 20+ klines.

### Issue: Performance not improved
**Solution**: Ensure you're using batch calculation and that klines data is properly formatted.

### Issue: Metadata not available
**Solution**: Use `calculate_with_metadata()` instead of `calculate()`, or set `include_metadata=True` in FactorStage.

## Support

For issues or questions:
- Check the test files for usage examples
- Review the source code in `quant/factors/`
- File an issue in the project repository

## Next Steps

1. **Test in Development**: Use the new framework in your dev environment
2. **Monitor Performance**: Compare calculation times
3. **Gradual Rollout**: Migrate endpoints one at a time
4. **Collect Feedback**: Monitor for any issues or unexpected behavior
5. **Full Migration**: Once stable, deprecate legacy FactorRegistry
