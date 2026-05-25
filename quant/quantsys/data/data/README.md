# Data Layer Documentation

## Overview

The data layer provides a robust foundation for the quantitative trading system, handling data fetching, validation, adjustment, storage, and caching.

## Architecture

```
pipeline/data/
├── sources/              # Data source adapters
│   ├── base_adapter.py   # Abstract base class
│   └── akshare_adapter.py # AkShare implementation
├── cleaner/              # Data quality and adjustment
│   ├── adjuster.py       # Price adjustment (复权)
│   └── validator.py      # Data quality validation
└── storage/              # Data persistence
    ├── db_manager.py     # Database operations
    └── cache_manager.py  # In-memory caching
```

## Core Components

### 1. Data Adapters

**BaseDataAdapter** - Abstract interface for data sources
- `fetch_daily_klines()` - Fetch K-line data
- `fetch_stock_list()` - Get list of stocks
- `fetch_realtime_quote()` - Get real-time quotes

**AkShareAdapter** - AkShare implementation
- Supports A-share and Hong Kong markets
- Automatic fallback (East Money → Tencent)
- Batch fetching capabilities

```python
from pipeline.data.sources.akshare_adapter import AkShareAdapter

adapter = AkShareAdapter()
df = adapter.fetch_daily_klines("000001", "20240101", "20240131", adjust="qfq")
```

### 2. Price Adjuster

**PriceAdjuster** - Handle price adjustment for corporate actions

Features:
- Forward adjustment (前复权, qfq)
- Backward adjustment (后复权, hfq)
- Corporate action detection (splits, dividends)
- Adjustment verification

```python
from pipeline.data.cleaner.adjuster import PriceAdjuster

adjuster = PriceAdjuster()
adjusted_df = adjuster.adjust_prices(df, adjust_type="qfq")
```

### 3. Data Validator

**DataValidator** - Validate data quality

Checks:
- Missing values
- Outliers (z-score method)
- Suspended trading days
- Duplicate dates
- Date continuity
- OHLC price consistency

```python
from pipeline.data.cleaner.validator import DataValidator

validator = DataValidator()
result = validator.validate(df)
print(f"Valid: {result['is_valid']}")
print(f"Errors: {result['errors']}")
```

### 4. Database Manager

**DBManager** - SQLite database operations

Features:
- Save/load K-line data
- Batch operations
- Symbol filtering
- Date range queries
- Statistics

```python
from pipeline.data.storage.db_manager import DBManager

db = DBManager()
db.save_klines("000001", df)
loaded = db.load_klines("000001", start_date="2024-01-01")
```

### 5. Cache Manager

**CacheManager** - In-memory caching with TTL

Features:
- LRU eviction
- TTL (time-to-live)
- Symbol-specific caching
- Cache statistics
- Automatic cleanup

```python
from pipeline.data.storage.cache_manager import CacheManager

cache = CacheManager(max_size=1000, default_ttl=300)
cache.set_klines("000001", df, "20240101", "20240131")
cached = cache.get_klines("000001", "20240101", "20240131")
```

## Key Features

### 1. Price Adjustment (复权)

Price adjustment accounts for corporate actions like dividends and stock splits:

- **Forward adjustment (前复权, qfq)**: Adjusts historical prices based on current price
  - Use case: Technical analysis, backtesting
  - Keeps current price unchanged

- **Backward adjustment (后复权, hfq)**: Adjusts current price based on historical prices
  - Use case: Historical comparison
  - Keeps historical prices unchanged

### 2. Data Quality Validation

The validator performs comprehensive checks:

1. **Missing values**: Detects and reports missing data
2. **Outliers**: Uses z-score method (configurable threshold)
3. **Suspended days**: Identifies zero-volume trading days
4. **Duplicates**: Finds duplicate dates
5. **Continuity**: Detects date gaps
6. **Consistency**: Validates OHLC relationships (high >= low, etc)

### 3. Multi-Source Support

The adapter pattern allows easy integration of new data sources:

```python
class TushareAdapter(BaseDataAdapter):
    def fetch_daily_klines(self, symbol, start_date, end_date, adjust="qfq"):
        # Implementation
        pass
```

## Usage Examples

### Complete Workflow

```python
from pipeline.data.sources.akshare_adapter import AkShareAdapter
from pipeline.data.cleaner.adjuster import PriceAdjuster
from pipeline.data.cleaner.validator import DataValidator
from pipeline.data.storage.db_manager import DBManager
from pipeline.data.storage.cache_manager import CacheManager

# 1. Fetch data
adapter = AkShareAdapter()
df = adapter.fetch_daily_klines("000001", "20240101", "20240131", adjust="qfq")

# 2. Validate quality
validator = DataValidator()
result = validator.validate(df)
if not result['is_valid']:
    print(f"Data quality issues: {result['errors']}")

# 3. Adjust prices (if needed)
adjuster = PriceAdjuster()
adjusted = adjuster.adjust_prices(df, adjust_type="qfq")

# 4. Save to database
db = DBManager()
db.save_klines("000001", adjusted)

# 5. Cache for quick access
cache = CacheManager()
cache.set_klines("000001", adjusted, "20240101", "20240131")
```

### Batch Processing

```python
# Fetch multiple symbols
symbols = ["000001", "000002", "600000"]
results = adapter.fetch_klines_batch(symbols, "20240101", "20240131")

# Save to database
for symbol, df in results.items():
    if not df.empty:
        db.save_klines(symbol, df)
```

## Testing

Run unit tests:

```bash
python -m unittest pipeline.tests.test_data_layer -v
```

Test coverage:
- BaseAdapter: 4 tests
- PriceAdjuster: 4 tests
- DataValidator: 8 tests
- CacheManager: 10 tests

Total: 26 tests, all passing ✓

## Performance Considerations

1. **Caching**: Use CacheManager for frequently accessed data
2. **Batch operations**: Use batch methods for multiple symbols
3. **Database indexing**: Indexes on (symbol, date) for fast queries
4. **Memory management**: Cache has configurable max_size and TTL

## Error Handling

All modules raise descriptive exceptions:

- `ValueError`: Invalid parameters
- `RuntimeError`: Operation failures (network, database, etc)

Example:

```python
try:
    df = adapter.fetch_daily_klines("INVALID", "20240101", "20240131")
except RuntimeError as exc:
    print(f"Failed to fetch data: {exc}")
```

## Next Steps

1. Add TushareAdapter for backup data source
2. Implement IQR-based outlier detection (more robust than z-score)
3. Add data quality metrics dashboard
4. Implement automatic data refresh scheduler
5. Add support for minute-level K-line data

## References

- AkShare documentation: https://akshare.akfamily.xyz/
- Price adjustment explanation: https://www.investopedia.com/terms/a/adjusted-closing-price.asp
