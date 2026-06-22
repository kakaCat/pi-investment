# Pandas to Polars Migration Design Specification

**Date**: 2026-06-07  
**Author**: AI Agent  
**Status**: Draft for Review

---

## Executive Summary

### Objective
Migrate the quantsys-v2 Python backend from pandas to polars for improved performance, reduced memory footprint, and future scalability.

### Scope
- **In Scope**: Repository layer (26 files), Service layer (8 core services), API serialization layer
- **Out of Scope**: Test files (gradual migration), example scripts, ML pipeline (Phase 2)
- **Timeline**: 2 weeks (Week 1: Repository, Week 2: Service + API)

### Key Decisions
- **Migration Strategy**: Bottom-up layered approach (Repository → Service → API)
- **Compatibility**: Internal refactoring only; external API responses unchanged
- **TA-Lib Integration**: polars ↔ numpy array bridging
- **Testing**: Full regression testing after each module

---

## Background

### Current State
- **245 files** use pandas (41 in core services/repositories)
- **192 files** use DataFrame/Series API
- Core modules: Backtest engine, factor calculation, strategy services, data pipeline
- Dependencies: pandas 2.0+, TA-Lib, pandas-ta, numba

### Motivation
- **Technical upgrade** for future scalability (not immediate performance issues)
- **Proactive optimization** before data volume grows
- **Modern ecosystem** alignment (Rust-based, Apache Arrow)

### Constraints
- **Time window**: 1-2 weeks
- **Backward compatibility**: API responses must remain unchanged
- **Testing requirement**: Complete regression testing per module

---

## Architecture Design

### Migration Layers

```
┌─────────────────────────────────────┐
│   API Layer (Flask Routes)         │  ← JSON serialization
│   └─ .to_dicts() conversion         │     (pl.DataFrame → dict)
├─────────────────────────────────────┤
│   Service Layer                     │  ← Business logic
│   └─ polars DataFrame operations    │     (logic unchanged)
├─────────────────────────────────────┤
│   Repository Layer                  │  ← Data access
│   └─ Returns pl.DataFrame           │     (core transformation)
├─────────────────────────────────────┤
│   TA-Lib Bridge                     │  ← Technical indicators
│   └─ pl → numpy → TA-Lib → pl      │     (explicit conversion)
└─────────────────────────────────────┘
```

### Core Components

#### 1. Repository Layer Transformation

**Before (pandas)**:
```python
def get_daily_klines(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
    rows = self.query(sql, params)
    return rows  # List[Dict]
```

**After (polars)**:
```python
import polars as pl

def get_daily_klines(self, symbol: str, start_date: str, end_date: str) -> pl.DataFrame:
    rows = self.query(sql, params)  # List[Dict] from psycopg2
    if not rows:
        return pl.DataFrame(schema={
            'trade_date': pl.Date,
            'open': pl.Float64,
            'high': pl.Float64,
            'low': pl.Float64,
            'close': pl.Float64,
            'volume': pl.Int64,
        })
    return pl.DataFrame(rows)
```

**Key Changes**:
- Return type: `List[Dict]` → `pl.DataFrame`
- Empty result handling: Return empty DataFrame with schema
- Type safety: Explicit schema definition

#### 2. TA-Lib Bridge Layer

**New Component**: `quantlib/technical/talib_bridge.py`

```python
import polars as pl
import talib
import numpy as np

class TALibBridge:
    """polars ↔ TA-Lib bridging layer"""
    
    @staticmethod
    def add_indicators(df: pl.DataFrame) -> pl.DataFrame:
        """
        Add technical indicators to polars DataFrame
        
        Args:
            df: DataFrame with OHLCV columns
            
        Returns:
            DataFrame with added indicator columns
        """
        # Convert to numpy arrays
        close = df['close'].to_numpy()
        high = df['high'].to_numpy()
        low = df['low'].to_numpy()
        volume = df['volume'].to_numpy()
        
        # Call TA-Lib (C implementation)
        rsi = talib.RSI(close, timeperiod=14)
        macd, signal, hist = talib.MACD(close)
        atr = talib.ATR(high, low, close, timeperiod=14)
        upper, middle, lower = talib.BBANDS(close, timeperiod=20)
        
        # Write results back to polars
        return df.with_columns([
            pl.Series("rsi", rsi),
            pl.Series("macd", macd),
            pl.Series("macd_signal", signal),
            pl.Series("macd_hist", hist),
            pl.Series("atr", atr),
            pl.Series("bollinger_upper", upper),
            pl.Series("bollinger_middle", middle),
            pl.Series("bollinger_lower", lower),
        ])
```

#### 3. Service Layer Adaptation

**Before (pandas)**:
```python
df = pd.DataFrame(klines)
df['rsi'] = df['close'].rolling(14).mean()
df['signal'] = df['close'] > df['ma20']
filtered = df[df['volume'] > 1000000]
```

**After (polars)**:
```python
df = pl.DataFrame(klines)
df = df.with_columns([
    pl.col('close').rolling_mean(14).alias('rsi')
])
df = df.with_columns([
    (pl.col('close') > pl.col('ma20')).alias('signal')
])
filtered = df.filter(pl.col('volume') > 1000000)
```

**Key API Changes**:
- `.apply()` → `.map_elements()` or vectorized operations
- `.iterrows()` → `.iter_rows()` or column operations
- Boolean indexing `df[condition]` → `df.filter(condition)`
- Assignment `df['new_col'] = ...` → `df.with_columns([...])`

#### 4. API Layer Serialization

**Flask Route Changes**:

```python
# Before
@app.route('/api/backtest', methods=['POST'])
def backtest():
    result = backtest_service.run(...)  # pandas DataFrame
    return jsonify(result.to_dict('records'))

# After
@app.route('/api/backtest', methods=['POST'])
def backtest():
    result = backtest_service.run(...)  # polars DataFrame
    return jsonify(result.to_dicts())  # polars method
```

**Response Format Compatibility**:
- pandas: `.to_dict('records')` → `[{col1: val1, ...}, ...]`
- polars: `.to_dicts()` → `[{col1: val1, ...}, ...]`
- Result: Identical JSON structure (TypeScript Agent unaffected)

---

## Data Flow and Integration

### External Library Integration

#### scikit-learn / XGBoost
```python
X_pl = df.select(['feature1', 'feature2', ...])
X_np = X_pl.to_numpy()  # Convert to numpy for sklearn
model.fit(X_np, y)
```

#### matplotlib / seaborn (Plotting)
```python
df_pd = df.to_pandas()  # Convert only when needed
df_pd.plot()
```

#### alphalens / empyrical (Factor Analysis)
```python
# These libraries depend on pandas MultiIndex
factor_data_pd = factor_data_pl.to_pandas()
alphalens.tears.create_full_tear_sheet(factor_data_pd)
```

### Performance Optimization

#### 1. Lazy Evaluation
```python
# Eager (immediate execution)
df = pl.DataFrame(data)
df = df.filter(pl.col('volume') > 0)
df = df.with_columns([pl.col('close').pct_change().alias('return')])

# Lazy (deferred execution with automatic optimization)
df = pl.scan_parquet('data.parquet')  # Don't read immediately
df = df.filter(pl.col('volume') > 0)
df = df.with_columns([pl.col('close').pct_change().alias('return')])
result = df.collect()  # Execute optimized query plan
```

#### 2. Columnar Caching
```python
# Cache frequently-queried data in parquet format
df.write_parquet('cache/klines_600000.parquet')
df_cached = pl.read_parquet('cache/klines_600000.parquet')  # 10x faster than CSV
```

#### 3. Automatic Parallelization
```python
# polars auto-parallelizes group operations (no manual ThreadPoolExecutor)
df.group_by('symbol').agg([
    pl.col('close').mean().alias('avg_price'),
    pl.col('volume').sum().alias('total_volume')
])  # Automatic multi-threaded execution
```

---

## Error Handling and Edge Cases

### Empty Data Handling

**pandas vs polars Differences**:

```python
# pandas: Empty DataFrame retains column definitions
df_empty = pd.DataFrame(columns=['date', 'close', 'volume'])
df_empty.empty  # True
df_empty.columns  # Index(['date', 'close', 'volume'])

# polars: Empty DataFrame needs explicit schema
df_empty = pl.DataFrame()  # Completely empty
df_empty = pl.DataFrame(schema={'date': pl.Date, 'close': pl.Float64})  # With schema
```

**Repository Layer Uniform Handling**:
```python
def get_daily_klines(self, symbol: str, start_date: str, end_date: str) -> pl.DataFrame:
    rows = self.query(sql, params)
    if not rows:
        # Return empty DataFrame with schema
        return pl.DataFrame(schema={
            'trade_date': pl.Date,
            'open': pl.Float64,
            'high': pl.Float64,
            'low': pl.Float64,
            'close': pl.Float64,
            'volume': pl.Int64,
        })
    return pl.DataFrame(rows)
```

### Type Conversion Pitfalls

#### Date Type Handling
```python
# pandas: Auto-infer dates
df['date'] = pd.to_datetime(df['date'])

# polars: Explicit format required
df = df.with_columns([
    pl.col('date').str.strptime(pl.Date, format='%Y-%m-%d')
])

# Repository layer handles uniformly
rows = self.query(sql)  # Returns List[Dict], dates are datetime.date objects
df = pl.DataFrame(rows)  # polars auto-recognizes Python date objects
```

#### NULL Value Handling
```python
# pandas: NaN / None mixed usage
df['value'].isna()  # Check both NaN and None

# polars: Strict distinction between null and NaN
df.filter(pl.col('value').is_null())  # Check SQL NULL
df.filter(pl.col('value').is_nan())   # Check floating-point NaN

# Unified strategy: Fill defaults at Repository return
df = df.fill_null(0)  # Or based on business requirements
```

### Exception Handling

**New Exception Types**:
```python
# quantlib/exceptions.py
class DataFrameConversionError(Exception):
    """DataFrame conversion failure"""
    pass

class TALibBridgeError(Exception):
    """TA-Lib bridging failure"""
    pass
```

**Service Layer Catching**:
```python
try:
    df = self.kline_repo.get_daily_klines(symbol, start, end)
    if df.is_empty():
        raise ValueError(f"No data found for {symbol}")
    
    df = TALibBridge.add_indicators(df)
except pl.exceptions.ColumnNotFoundError as e:
    logger.error(f"Column missing: {e}")
    raise DataFrameConversionError(f"Required column not found: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

---

## Testing Strategy

### Test Layering

#### 1. Repository Layer Unit Tests

**Focus**: Verify polars DataFrame return format

```python
# tests/repositories/test_kline_repository_polars.py
import polars as pl
import pytest
from repositories.kline_repository import KlineRepository

class TestKlineRepositoryPolars:
    def test_get_daily_klines_returns_polars_dataframe(self):
        repo = KlineRepository()
        result = repo.get_daily_klines('600000', '2024-01-01', '2024-12-31')
        
        # Type validation
        assert isinstance(result, pl.DataFrame)
        
        # Schema validation
        expected_columns = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
        assert all(col in result.columns for col in expected_columns)
        
        # Data type validation
        assert result['close'].dtype == pl.Float64
        assert result['volume'].dtype == pl.Int64
    
    def test_empty_result_returns_empty_dataframe_with_schema(self):
        repo = KlineRepository()
        result = repo.get_daily_klines('999999', '2024-01-01', '2024-01-02')
        
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()
        assert 'close' in result.columns  # Schema still exists
```

#### 2. Service Layer Integration Tests

**Focus**: Verify business logic result consistency

```python
# tests/services/test_strategy_backtest_service_polars.py
import polars as pl
from services.strategy_backtest_service import StrategyBacktestService

class TestStrategyBacktestServicePolars:
    def test_backtest_results_match_baseline(self):
        """Compare polars version with baseline results"""
        service = StrategyBacktestService()
        
        # Execute backtest
        result = service.backtest_indicator_strategy(
            strategy={'code_content': '...', 'parsed_params': {}},
            klines=[...],
            initial_cash=1000000
        )
        
        # Key metric validation (compare with historical baseline)
        assert abs(result['total_return'] - 0.1523) < 0.0001  # 15.23%
        assert abs(result['sharpe_ratio'] - 1.82) < 0.01
        assert result['max_drawdown'] < -0.05  # -5%
        assert result['win_rate'] > 0.6  # 60%
```

#### 3. Regression Tests (Dual-track Validation)

**Focus**: pandas vs polars result consistency

```python
# tests/integration/test_pandas_polars_parity.py
import pandas as pd
import polars as pl
from services.factor_analysis_service import FactorAnalysisService

class TestPandasPolarsParity:
    """Verify pandas and polars version result consistency"""
    
    def test_factor_ic_calculation_parity(self):
        """Factor IC calculation result parity"""
        service = FactorAnalysisService()
        
        # Prepare test data
        test_data = self._load_test_data()
        
        # pandas version (baseline)
        df_pd = pd.DataFrame(test_data)
        ic_pd = self._calculate_ic_pandas(df_pd)
        
        # polars version (new implementation)
        df_pl = pl.DataFrame(test_data)
        ic_pl = service.calculate_factor_ic(df_pl)  # Using polars
        
        # Result comparison (allow floating-point error)
        assert abs(ic_pd - ic_pl) < 1e-6
```

### Test Data Preparation

**Create Standard Test Dataset**:

```python
# tests/fixtures/polars_test_data.py
import polars as pl
from datetime import date, timedelta

def create_test_klines(symbol: str = '600000', days: int = 252) -> pl.DataFrame:
    """Generate standard test K-line data"""
    start_date = date(2024, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(days)]
    
    return pl.DataFrame({
        'symbol': [symbol] * days,
        'trade_date': dates,
        'open': [100.0 + i * 0.1 for i in range(days)],
        'high': [102.0 + i * 0.1 for i in range(days)],
        'low': [98.0 + i * 0.1 for i in range(days)],
        'close': [100.5 + i * 0.1 for i in range(days)],
        'volume': [1000000 + i * 1000 for i in range(days)],
    })
```

### Test Coverage Requirements

| Module | Target Coverage | Key Test Points |
|--------|----------------|-----------------|
| Repository Layer | 90%+ | Empty data, boundary dates, type conversion |
| Service Layer | 85%+ | Business logic, exception handling |
| TA-Lib Bridge | 95%+ | NaN handling, array alignment |
| API Layer | 80%+ | JSON serialization, response format |

### CI/CD Integration

**pytest Configuration Update**:

```python
# pytest.ini - Add polars test markers
[pytest]
markers =
    polars: tests for polars migration
    pandas_parity: tests comparing pandas and polars results
    slow: slow tests (>5s)

# Execution strategy
pytest -m polars  # Run only polars-related tests
pytest -m pandas_parity  # Run dual-track comparison tests
```

---

## Implementation Plan

### Week 1: Repository Layer Migration (Day 1-7)

**Day 1-2: Infrastructure**
- Add polars dependency to `requirements.txt`
- Create `TALibBridge` class
- Create test data generation tools
- Write Repository layer base test framework

**Day 3-5: Core Repository Migration**
- `KlineRepository` — K-line queries (daily + minute)
- `StockRepository` — Stock fundamentals
- `FinancialRepository` — Financial data
- `FactorRepository` — Factor data
- Run unit tests immediately after completing each Repository

**Day 6-7: Secondary Repositories + Regression Tests**
- `DividendRepository`, `OrderRepository`, `StrategyRepository`, etc.
- Run complete Repository layer test suite
- Fix discovered issues

**Week 1 Deliverables**:
- ✅ All Repositories return `pl.DataFrame`
- ✅ Repository layer test coverage > 90%
- ✅ `TALibBridge` available and tested

---

### Week 2: Service Layer Migration (Day 8-14)

**Day 8-10: Core Service Migration**
- `StrategyBacktestService` — Backtest engine (highest priority)
- `FactorAnalysisService` — Factor analysis
- `OpportunityScoringService` — Opportunity scanning
- Run integration tests + dual-track comparison tests after each Service

**Day 11-12: Secondary Service Migration**
- `ComboStrategyBacktestService` — Combo backtest
- `MarketDataService` — Market data
- `StockDataService` — Stock data
- `BenchmarkService` — Benchmark comparison

**Day 13: API Layer Adaptation**
- Update Flask route serialization logic (`.to_dict()` → `.to_dicts()`)
- API end-to-end tests
- Performance benchmark tests (compare before/after migration)

**Day 14: Acceptance and Documentation**
- Complete regression test suite
- Performance report
- Update CLAUDE.md documentation

**Week 2 Deliverables**:
- ✅ All core Services use polars
- ✅ API response format remains compatible
- ✅ All regression tests pass
- ✅ Performance benchmark report

---

## Risk Control Measures

### 1. Rollback Mechanism

**Git Branch Strategy**:
```bash
# Main branch protection
main (production) → Keep stable
  ↓
feature/polars-migration (development branch)
  ↓
feature/polars-week1-repo (Week 1 branch)
feature/polars-week2-service (Week 2 branch)
```

**Daily Backup Points**:
- Create tag at end of each day: `polars-migration-day-N`
- Can quickly revert to previous day's state if issues found

### 2. Gradual Validation

**Week 1 End Validation Point**:
```python
# Temporary dual-mode Repository (Week 1-2 transition)
class KlineRepository:
    def __init__(self, use_polars: bool = True):
        self.use_polars = use_polars
    
    def get_daily_klines(self, ...) -> Union[pd.DataFrame, pl.DataFrame]:
        rows = self.query(sql)
        if self.use_polars:
            return pl.DataFrame(rows)
        else:
            return pd.DataFrame(rows)  # fallback
```

**Environment Variable Switch**:
```bash
# .env
USE_POLARS=true  # Default enabled in Week 2
```

### 3. Performance Monitoring

**Key Metrics**:
- Backtest execution time (expected 40% reduction)
- Factor calculation time (expected 60% reduction)
- Memory usage (expected 50% reduction)
- API response time (expected 30% reduction)

**Monitoring Script**:
```python
# scripts/benchmark_polars.py
import time
import psutil

def benchmark_backtest():
    """Compare pandas vs polars backtest performance"""
    # pandas version
    start = time.time()
    result_pd = backtest_with_pandas(...)
    time_pd = time.time() - start
    mem_pd = psutil.Process().memory_info().rss / 1024 / 1024
    
    # polars version
    start = time.time()
    result_pl = backtest_with_polars(...)
    time_pl = time.time() - start
    mem_pl = psutil.Process().memory_info().rss / 1024 / 1024
    
    print(f"Time: pandas={time_pd:.2f}s, polars={time_pl:.2f}s, speedup={time_pd/time_pl:.1f}x")
    print(f"Memory: pandas={mem_pd:.0f}MB, polars={mem_pl:.0f}MB, reduction={100*(1-mem_pl/mem_pd):.0f}%")
```

### 4. Issue Classification

| Level | Definition | Response Measures |
|-------|-----------|-------------------|
| P0 | Complete functionality failure | Immediately rollback to previous day's tag |
| P1 | Result inconsistency (error > 0.1%) | Pause migration, fix then continue |
| P2 | Performance degradation (> 10%) | Analyze root cause, optimize code |
| P3 | Test coverage below target | Add test cases |

---

## Dependencies and Prerequisites

### Environment Requirements
- Python 3.13 (satisfied)
- PostgreSQL database (exists)
- Complete test dataset (needs preparation)

### Staffing Requirements
- 1 full-time developer
- Reserve 20% buffer time for unexpected issues

### Technical Debt Cleanup
- None required; polars migration doesn't affect existing pandas code (until Week 1 completion)

---

## Success Criteria

### Functional Requirements
- ✅ All Repository methods return polars DataFrame
- ✅ All Service business logic maintains identical results
- ✅ All API endpoints return identical JSON format
- ✅ TA-Lib integration works correctly
- ✅ All regression tests pass (>95% pass rate)

### Non-Functional Requirements
- ✅ Test coverage: Repository >90%, Service >85%, API >80%
- ✅ Performance improvement: >30% overall speedup
- ✅ Memory reduction: >40% memory footprint reduction
- ✅ Code quality: No pylint warnings, type hints complete

### Documentation Requirements
- ✅ Design spec (this document)
- ✅ Implementation plan (generated by writing-plans skill)
- ✅ Performance benchmark report
- ✅ Updated CLAUDE.md with polars conventions

---

## Future Considerations

### Phase 2 (Post-Migration)
- Migrate ML pipeline to polars
- Migrate test files gradually
- Add polars lazy evaluation in data pipelines
- Evaluate polars streaming API for large datasets

### Monitoring and Maintenance
- Track polars library updates (breaking changes)
- Monitor performance metrics in production
- Collect team feedback on polars API usability
- Consider contributing fixes upstream to polars

---

## Appendix

### A. polars vs pandas API Mapping

| Operation | pandas | polars |
|-----------|--------|--------|
| Read CSV | `pd.read_csv()` | `pl.read_csv()` |
| Filter rows | `df[df['x'] > 0]` | `df.filter(pl.col('x') > 0)` |
| Add column | `df['new'] = ...` | `df.with_columns([pl.lit(...).alias('new')])` |
| Group by | `df.groupby('key').agg(...)` | `df.group_by('key').agg([...])` |
| Join | `df1.merge(df2)` | `df1.join(df2)` |
| Sort | `df.sort_values('col')` | `df.sort('col')` |
| Rolling window | `df['x'].rolling(5).mean()` | `pl.col('x').rolling_mean(5)` |
| To dict | `df.to_dict('records')` | `df.to_dicts()` |
| To numpy | `df.values` | `df.to_numpy()` |
| To pandas | N/A | `df.to_pandas()` |

### B. Dependencies to Add

```txt
# requirements.txt additions
polars>=0.20.0  # Core polars library
pyarrow>=14.0.0  # Apache Arrow backend (optional but recommended)
```

### C. Key Files to Modify

**Week 1 (Repository Layer)**:
- `repositories/kline_repository.py`
- `repositories/stock_repository.py`
- `repositories/financial_repository.py`
- `repositories/factor_repository.py`
- `repositories/dividend_repository.py`
- `repositories/order_repository.py`
- `repositories/strategy_repository.py`
- (+ 19 other repository files)

**Week 2 (Service Layer)**:
- `services/strategy_backtest_service.py`
- `services/factor_analysis_service.py`
- `services/opportunity_scoring_service.py`
- `services/combo_strategy_backtest_service.py`
- `services/market_data_service.py`
- `services/stock_data_service.py`
- `services/data_pipeline_service.py`
- `services/benchmark_service.py`

**New Files**:
- `quantlib/technical/talib_bridge.py`
- `utils/dataframe_adapter.py` (temporary, for transition)
- `tests/fixtures/polars_test_data.py`
- `scripts/benchmark_polars.py`

---

## Sign-off

**Design Approved By**: [Pending User Review]  
**Implementation Start Date**: [TBD after plan creation]  
**Expected Completion Date**: [TBD, ~2 weeks from start]

