# Strategy Batch Validation

## Overview

Strategy batch validation provides automated quality assessment for trading strategies. It validates strategies against historical data, calculates comprehensive scores across multiple dimensions, and identifies underperforming strategies for removal.

## Features

- **Batch Processing**: Validate multiple strategies in parallel
- **Multi-Dimensional Scoring**: Performance, risk, stability, and robustness metrics
- **Automated Filtering**: Mark invalid strategies based on configurable thresholds
- **Persistent Results**: Store validation reports in database for historical tracking
- **Stock Pool Integration**: Test strategies against hot stock pool (沪深300 + 创业板50 + 科创50)

## Scoring Algorithm

### Comprehensive Score Formula

```
comprehensive_score = performance × 0.40 + risk × 0.30 + stability × 0.20 + robustness × 0.10
```

### Dimension Breakdown

#### 1. Performance Score (40%)

Measures profitability and efficiency:

- **Annual Return** (50%): Normalized to [0, 100] range (0-30% target)
- **Sharpe Ratio** (30%): Risk-adjusted return (0-3 target)
- **Win Rate** (20%): Percentage of profitable trades (40-70% target)

#### 2. Risk Score (30%)

Measures downside protection:

- **Max Drawdown** (60%): Maximum peak-to-trough decline (0 to -30% range, reverse scoring)
- **Volatility** (40%): Annualized standard deviation (0-40% range, reverse scoring)

#### 3. Stability Score (20%)

Measures consistency:

- **Calmar Ratio** (50%): Return / Max Drawdown (0-2 target)
- **Monthly Win Rate** (50%): Percentage of profitable months (40-70% target)

#### 4. Robustness Score (10%)

Measures reliability:

- **Trade Count** (50%): Number of trades (20-200 target)
- **Avg Trade Duration** (50%): Average holding period in days (3-30 target)

### Normalization

All metrics are normalized to [0, 100] scale using:

```python
# Forward metrics (higher is better)
score = ((value - min_val) / (max_val - min_val)) * 100

# Reverse metrics (lower is better, e.g., drawdown)
score = ((max_val - value) / (max_val - min_val)) * 100
```

## Usage

### TypeScript Agent

```typescript
import { strategyBatchValidate } from './tools/strategy-batch-validate';

const result = await strategyBatchValidate({
  strategyIds: [1, 2, 3],           // Optional: specific strategies
  minScore: 60,                      // Optional: minimum passing score
  markInvalid: true,                 // Optional: auto-mark failed strategies
  stockPool: 'hot',                  // Optional: 'hot' or 'all'
  startDate: '2024-01-01',           // Optional: backtest start date
  endDate: '2024-12-31'              // Optional: backtest end date
});

console.log(result.summary);
// {
//   total: 3,
//   passed: 2,
//   failed: 1,
//   avgScore: 72.5,
//   duration: 1.23
// }
```

### HTTP API

**Endpoint**: `POST /api/strategies/validate`

**Request**:
```json
{
  "strategy_ids": [1, 2, 3],
  "min_score": 60,
  "mark_invalid": true,
  "stock_pool": "hot",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "strategy_id": 1,
      "strategy_name": "RSI Momentum",
      "passed": true,
      "comprehensive_score": 75.2,
      "performance_score": 80.5,
      "risk_score": 72.3,
      "stability_score": 68.9,
      "robustness_score": 78.1,
      "metrics": {
        "annual_return": 0.18,
        "sharpe_ratio": 1.5,
        "max_drawdown": -0.12,
        "volatility": 0.15,
        "win_rate": 0.58,
        "calmar_ratio": 1.5,
        "monthly_win_rate": 0.67,
        "trade_count": 45,
        "avg_trade_duration": 8.5
      },
      "marked_invalid": false
    }
  ],
  "summary": {
    "total": 3,
    "passed": 2,
    "failed": 1,
    "avg_score": 72.5,
    "duration": 1.23
  }
}
```

### Python Service

```python
from services.strategy_validation_service import StrategyValidationService

service = StrategyValidationService()

results = service.validate_strategies(
    strategy_ids=[1, 2, 3],
    min_score=60,
    mark_invalid=True,
    stock_pool='hot',
    start_date='2024-01-01',
    end_date='2024-12-31'
)

for result in results:
    print(f"{result['strategy_name']}: {result['comprehensive_score']:.1f}")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy_ids` | List[int] | None | Specific strategies to validate (None = all active) |
| `min_score` | float | 60.0 | Minimum passing score (0-100) |
| `mark_invalid` | bool | False | Auto-mark failed strategies as invalid |
| `stock_pool` | str | 'hot' | Stock pool to test ('hot' or 'all') |
| `start_date` | str | None | Backtest start date (YYYY-MM-DD) |
| `end_date` | str | None | Backtest end date (YYYY-MM-DD) |

## Output Format

### Validation Result

```typescript
interface ValidationResult {
  strategy_id: number;
  strategy_name: string;
  passed: boolean;
  comprehensive_score: number;
  performance_score: number;
  risk_score: number;
  stability_score: number;
  robustness_score: number;
  metrics: {
    annual_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    volatility: number;
    win_rate: number;
    calmar_ratio: number;
    monthly_win_rate: number;
    trade_count: number;
    avg_trade_duration: number;
  };
  marked_invalid: boolean;
}
```

### Summary

```typescript
interface ValidationSummary {
  total: number;
  passed: number;
  failed: number;
  avg_score: number;
  duration: number;  // seconds
}
```

## Performance Metrics

- **Validation Speed**: ~0.5-1.0 seconds per strategy
- **Batch Processing**: Parallel execution with ThreadPoolExecutor
- **Database Queries**: Optimized batch queries (no N+1)
- **Memory Usage**: ~50-100 MB for 100 strategies

## Database Schema

### validation_status Table

Tracks validation state for each strategy:

```sql
CREATE TABLE validation_status (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    last_validated_at TIMESTAMP,
    comprehensive_score FLOAT,
    performance_score FLOAT,
    risk_score FLOAT,
    stability_score FLOAT,
    robustness_score FLOAT,
    is_valid BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(strategy_id)
);
```

### validation_reports Table

Stores detailed validation results:

```sql
CREATE TABLE validation_reports (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    validated_at TIMESTAMP NOT NULL,
    comprehensive_score FLOAT NOT NULL,
    performance_score FLOAT NOT NULL,
    risk_score FLOAT NOT NULL,
    stability_score FLOAT NOT NULL,
    robustness_score FLOAT NOT NULL,
    metrics JSONB NOT NULL,
    passed BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Error Handling

### Common Errors

**1. Strategy Not Found**
```json
{
  "success": false,
  "error": "Strategy 999 not found"
}
```

**2. Insufficient Data**
```json
{
  "success": false,
  "error": "Insufficient historical data for strategy 1"
}
```

**3. Backtest Failure**
```json
{
  "success": false,
  "error": "Backtest failed for strategy 1: Division by zero"
}
```

### Partial Success

If some strategies fail validation, the API returns partial results:

```json
{
  "success": true,
  "results": [...],
  "errors": [
    {
      "strategy_id": 2,
      "error": "Insufficient data"
    }
  ],
  "summary": {
    "total": 3,
    "passed": 1,
    "failed": 1,
    "errors": 1
  }
}
```

## Best Practices

### 1. Regular Validation

Run validation weekly or monthly to catch degrading strategies:

```bash
# Cron job example
0 0 * * 0 curl -X POST http://localhost:5001/api/strategies/validate \
  -H "Content-Type: application/json" \
  -d '{"min_score": 60, "mark_invalid": true}'
```

### 2. Threshold Tuning

Adjust `min_score` based on market conditions:

- **Bull Market**: 65-70 (higher bar)
- **Bear Market**: 55-60 (lower bar)
- **Sideways Market**: 60-65 (moderate)

### 3. Stock Pool Selection

- **Development**: Use 'hot' pool (~400 stocks) for faster iteration
- **Production**: Use 'all' pool for comprehensive validation

### 4. Date Range

- **Minimum**: 6 months of data for meaningful statistics
- **Recommended**: 1-2 years for robust validation
- **Maximum**: 3-5 years to avoid overfitting to old regimes

### 5. Batch Size

- **Small Batch**: 10-20 strategies for quick checks
- **Full Validation**: All strategies monthly
- **Incremental**: New strategies immediately after creation

## Limitations

1. **Historical Bias**: Past performance doesn't guarantee future results
2. **Market Regime**: Strategies may perform differently in different market conditions
3. **Overfitting Risk**: High scores may indicate overfitting to historical data
4. **Transaction Costs**: Validation doesn't account for slippage and commissions
5. **Liquidity**: Assumes all trades can be executed at desired prices

## Related Documentation

- [Strategy Code Execution Engine](superpowers/specs/strategy-code-execution-engine.md)
- [ML Pipeline](../CLAUDE.md#ml-pipeline)
- [Repository Layer](../CLAUDE.md#repository-layer)

## Changelog

- **2026-05-28**: Initial implementation with comprehensive scoring algorithm
