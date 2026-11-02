# Data Pipeline Design Specification

**Date:** 2026-05-26  
**Author:** Claude (Brainstorming Skill)  
**Status:** Draft  
**Version:** 1.0

## Executive Summary

This document specifies the design of a comprehensive data processing pipeline for quantsys-v2, implementing the flow: **行情数据 → 清洗 → 校验 → 存储 → 因子计算**.

**Key Requirements:**
- **Scenario:** Batch research (offline processing, data integrity over latency)
- **Scale:** Medium (300 stocks × hundreds of factors, hourly computation)
- **Data Sources:** Multi-source fusion (akshare + tushare + eastmoney) with incremental updates and periodic full rebuilds
- **Quality Priority:** Time alignment > Anomaly detection > Conflict resolution > Imputation
- **Storage:** Three-layer (raw → cleaned → factors)

**Architecture:** Pipeline pattern with composable stages, leveraging existing `core/pipeline.py` framework.

---

## 1. Requirements Analysis

### 1.1 Functional Requirements

**FR-1: Multi-Source Data Acquisition**
- Fetch data from multiple providers (akshare, tushare, eastmoney)
- Support both incremental (daily) and full rebuild (weekly) modes
- Handle API timeouts and rate limits with retry logic

**FR-2: Data Cleaning**
- Remove duplicate records within each data source
- Deduplicate based on (symbol, trade_date, timestamp)
- Keep the most recently fetched record

**FR-3: Data Validation**
- **Priority 1:** Time alignment - unified trading calendar, timezone handling, suspension marking
- **Priority 2:** Anomaly detection - price jumps, volume spikes, financial data sanity checks
- **Priority 3:** Conflict resolution - arbitrate when multiple sources disagree
- **Priority 4:** Imputation - fill missing values with appropriate strategies

**FR-4: Three-Layer Storage**
- **Raw layer:** Preserve original data from each source
- **Cleaned layer:** Merged and validated data ready for analysis
- **Factor layer:** Computed factor values

**FR-5: Factor Computation**
- Trigger factor calculation on cleaned data
- Support batch and incremental computation
- Integrate with existing `FactorService`

### 1.2 Non-Functional Requirements

**NFR-1: Performance**
- Process 300 stocks in < 1 hour
- Support vectorized operations for factor computation
- Batch database writes (50 stocks per batch)

**NFR-2: Reliability**
- Graceful error handling (skip failed stocks, continue processing)
- Transaction rollback on critical failures
- Retry logic for transient errors (3 retries with exponential backoff)

**NFR-3: Observability**
- Log execution metrics for each stage
- Generate data quality reports
- Alert on anomalies (execution time > 1h, quality score < 60, error rate > 10%)

**NFR-4: Maintainability**
- Each stage independently testable
- Clear separation of concerns
- Configuration-driven behavior

---

## 2. Architecture Design

### 2.1 System Layers

```
┌─────────────────────────────────────────────────────────┐
│  Scheduler / API / CLI (Entry Points)                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  DataPipelineService (Orchestration Layer)              │
│  - Configuration management                             │
│  - Pipeline construction                                │
│  - Execution monitoring                                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Pipeline Framework (core/pipeline.py)                  │
│  - Stage orchestration                                  │
│  - Data passing between stages                          │
│  - Error handling                                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Data Processing Stages (quant/stages/data/)            │
│                                                          │
│  1. DataFetchStage      - Multi-source data fetch       │
│  2. DeduplicationStage  - Remove duplicates             │
│  3. TimeAlignmentStage  - Time alignment (Priority 1)   │
│  4. AnomalyDetectionStage - Anomaly detection (P2)      │
│  5. ConflictResolutionStage - Conflict arbitration (P3) │
│  6. ImputationStage     - Fill missing values (P4)      │
│  7. StorageStage        - Three-layer storage           │
│  8. FactorComputeStage  - Trigger factor computation    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Infrastructure Layer                                    │
│  - DataValidator (quantlib/data_validator.py)           │
│  - Repositories (repositories/)                         │
│  - DataSources (data_sources/)                          │
│  - Cache (runtime/cache/)                               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
Raw Data (Dict[source, DataFrame])
    ↓ DataFetchStage
    ↓ DeduplicationStage
    ↓ TimeAlignmentStage
Aligned Data (Dict[source, DataFrame])
    ↓ AnomalyDetectionStage
Validated Data (Dict[source, DataFrame]) + QualityReport
    ↓ ConflictResolutionStage
Merged Data (DataFrame)
    ↓ ImputationStage
Complete Data (DataFrame)
    ↓ StorageStage
    ├─ quant.raw_klines (raw layer)
    ├─ quant.daily_klines (cleaned layer)
    └─ quant.factors (factor layer)
```

### 2.3 Design Rationale

**Why Pipeline Pattern?**
- Aligns with existing `core/pipeline.py` framework
- Each stage is independently testable
- Easy to add/remove/reorder stages
- Supports partial re-execution (resume from failed stage)

**Why Three-Layer Storage?**
- **Raw layer:** Enables re-processing with improved cleaning logic
- **Cleaned layer:** Optimized for backtesting and analysis
- **Factor layer:** Avoids redundant computation

**Why Not Event-Driven?**
- Batch research scenario doesn't require real-time streaming
- Simpler debugging and reasoning about data flow
- Lower operational complexity

---

## 3. Component Design

### 3.1 Stage Interfaces

**Base Interface:**
```python
class PipelineStage(ABC):
    @abstractmethod
    def execute(self, context: PipelineContext) -> PipelineResult:
        pass

class PipelineContext:
    data: Any                    # Input data
    config: Dict[str, Any]       # Stage configuration
    metadata: Dict[str, Any]     # Execution metadata

class PipelineResult:
    success: bool
    data: Any                    # Output data
    errors: List[Dict]           # Error records
    metadata: Dict[str, Any]     # Execution metrics
```

### 3.2 Stage Specifications

#### Stage 1: DataFetchStage

**Purpose:** Fetch raw data from multiple data sources in parallel.

**Input:** 
- `symbols: List[str]` - Stock symbols (e.g., ['600000.SH', '000001.SZ'])
- `date_range: Tuple[str, str]` - Date range (start_date, end_date)
- `sources: List[str]` - Data source names (e.g., ['akshare', 'tushare'])

**Output:** `Dict[str, pd.DataFrame]` - Keyed by source name

**Implementation:**
```python
class DataFetchStage(PipelineStage):
    def __init__(self, sources: List[str], symbols: List[str], date_range: Tuple[str, str]):
        self.sources = sources
        self.symbols = symbols
        self.date_range = date_range
        self.data_source_registry = DataSourceRegistry()
    
    def execute(self, context: PipelineContext) -> PipelineResult:
        results = {}
        errors = []
        
        for source_name in self.sources:
            try:
                source = self.data_source_registry.get(source_name)
                df = source.fetch_klines(self.symbols, self.date_range)
                df['source'] = source_name
                df['fetch_time'] = datetime.now()
                results[source_name] = df
            except Exception as e:
                errors.append({
                    'source': source_name,
                    'error': str(e),
                    'timestamp': datetime.now()
                })
                logger.warning(f"Failed to fetch from {source_name}: {e}")
        
        return PipelineResult(
            success=len(results) > 0,
            data=results,
            errors=errors,
            metadata={'sources_fetched': len(results), 'total_records': sum(len(df) for df in results.values())}
        )
```

**Error Handling:**
- Timeout: Retry 3 times with exponential backoff (5s, 10s, 20s)
- API rate limit: Skip source and log warning
- Network error: Retry, then skip if all retries fail

**Why:** Parallel fetching reduces total execution time. Storing source name enables conflict resolution.

---

#### Stage 2: DeduplicationStage

**Purpose:** Remove duplicate records within each data source.

**Input:** `Dict[str, pd.DataFrame]` - Raw data from each source

**Output:** `Dict[str, pd.DataFrame]` - Deduplicated data

**Implementation:**
```python
class DeduplicationStage(PipelineStage):
    def execute(self, context: PipelineContext) -> PipelineResult:
        results = {}
        stats = {}
        
        for source, df in context.data.items():
            original_count = len(df)
            
            # Deduplicate by (symbol, trade_date, timestamp)
            # Keep the last record (most recent fetch_time)
            df_dedup = df.sort_values('fetch_time').drop_duplicates(
                subset=['symbol', 'trade_date'], 
                keep='last'
            )
            
            duplicates_removed = original_count - len(df_dedup)
            results[source] = df_dedup
            stats[source] = {
                'original': original_count,
                'after_dedup': len(df_dedup),
                'removed': duplicates_removed
            }
            
            if duplicates_removed > 0:
                logger.info(f"{source}: Removed {duplicates_removed} duplicates")
        
        return PipelineResult(
            success=True,
            data=results,
            errors=[],
            metadata={'deduplication_stats': stats}
        )
```

**Why:** Duplicates can occur due to API retries or overlapping date ranges. Keeping the most recent record ensures data freshness.

---

#### Stage 3: TimeAlignmentStage (Priority 1)

**Purpose:** Align timestamps to unified trading calendar and timezone.

**Input:** `Dict[str, pd.DataFrame]` - Deduplicated data

**Output:** `Dict[str, pd.DataFrame]` - Time-aligned data

**Implementation:**
```python
class TimeAlignmentStage(PipelineStage):
    def __init__(self, calendar: str = 'SSE', timezone: str = 'Asia/Shanghai'):
        self.calendar = calendar
        self.timezone = timezone
        self.trading_calendar = self._load_trading_calendar()
    
    def execute(self, context: PipelineContext) -> PipelineResult:
        results = {}
        stats = {}
        
        for source, df in context.data.items():
            original_count = len(df)
            
            # 1. Convert timezone
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.tz_localize(self.timezone)
            
            # 2. Filter non-trading days
            df = df[df['trade_date'].dt.date.isin(self.trading_calendar)]
            
            # 3. Mark suspensions (no volume but date is trading day)
            df['is_suspended'] = (df['volume'] == 0) | df['volume'].isna()
            
            # 4. Validate trading hours (09:30-15:00 for A-shares)
            if 'timestamp' in df.columns:
                df = df[
                    (df['timestamp'].dt.hour >= 9) & 
                    (df['timestamp'].dt.hour < 15) |
                    ((df['timestamp'].dt.hour == 9) & (df['timestamp'].dt.minute >= 30))
                ]
            
            filtered_count = original_count - len(df)
            results[source] = df
            stats[source] = {
                'original': original_count,
                'after_alignment': len(df),
                'filtered': filtered_count,
                'suspensions': df['is_suspended'].sum()
            }
        
        return PipelineResult(
            success=True,
            data=results,
            errors=[],
            metadata={'alignment_stats': stats}
        )
    
    def _load_trading_calendar(self) -> Set[date]:
        """Load SSE/SZSE trading calendar.
        
        Implementation options:
        1. Query from existing calendar table in database
        2. Use pandas_market_calendars library
        3. Load from static file (data/trading_calendar.csv)
        
        Returns set of trading dates for current year + previous year.
        """
        # Example: Load from database
        query = "SELECT trade_date FROM quant.trading_calendar WHERE exchange = 'SSE'"
        cursor = self.db.cursor()
        cursor.execute(query)
        dates = {row['trade_date'] for row in cursor.fetchall()}
        cursor.close()
        return dates
```

**Why:** Time alignment is Priority 1 because misaligned timestamps cause factor calculation errors and backtest inaccuracies.

**How to apply:** Always run this stage before anomaly detection. Suspension marking prevents false positives in volume anomaly detection.

---

#### Stage 4: AnomalyDetectionStage (Priority 2)

**Purpose:** Detect price jumps, volume spikes, and data quality issues.

**Input:** `Dict[str, pd.DataFrame]` - Time-aligned data

**Output:** `Dict[str, pd.DataFrame]` + `DataQualityReport`

**Implementation:**
```python
class AnomalyDetectionStage(PipelineStage):
    def __init__(self, validator: DataValidator):
        self.validator = validator
    
    def execute(self, context: PipelineContext) -> PipelineResult:
        results = {}
        quality_reports = {}
        
        for source, df in context.data.items():
            # Use existing DataValidator
            cleaned_df, report = self.validator.validate_financial_data(
                df, 
                data_type='prices',
                data_name=f"{source}_klines"
            )
            
            # Add quality score to each record
            cleaned_df['quality_score'] = report.quality_score
            
            results[source] = cleaned_df
            quality_reports[source] = report.to_dict()
            
            # Log critical issues
            for issue in report.issues:
                if issue['severity'] in ['high', 'critical']:
                    logger.warning(f"{source}: {issue['description']}")
        
        return PipelineResult(
            success=True,
            data=results,
            errors=[],
            metadata={'quality_reports': quality_reports}
        )
```

**Integration:** Leverages existing `quantlib/data_validator.py` for:
- Price jump detection (>50% change → potential split/error)
- Volume Z-score outliers (>3σ)
- Negative price detection
- Statistical anomalies (IQR method)

**Why:** Priority 2 because anomalies corrupt factor calculations. Must run after time alignment to avoid false positives from non-trading days.

---

#### Stage 5: ConflictResolutionStage (Priority 3)

**Purpose:** Merge data from multiple sources and resolve conflicts.

**Input:** `Dict[str, pd.DataFrame]` - Validated data from each source

**Output:** `pd.DataFrame` - Single merged dataset

**Implementation:**
```python
class ConflictResolutionStage(PipelineStage):
    def __init__(self, strategy: str = 'priority', priority: List[str] = ['akshare', 'tushare', 'eastmoney']):
        self.strategy = strategy
        self.priority = priority
    
    def execute(self, context: PipelineContext) -> PipelineResult:
        # Concatenate all sources
        all_data = []
        for source in self.priority:
            if source in context.data:
                df = context.data[source].copy()
                df['_source'] = source
                df['_priority'] = self.priority.index(source)
                all_data.append(df)
        
        combined = pd.concat(all_data, ignore_index=True)
        
        # Resolve conflicts based on strategy
        if self.strategy == 'priority':
            merged = self._resolve_by_priority(combined)
        elif self.strategy == 'voting':
            merged = self._resolve_by_voting(combined)
        elif self.strategy == 'weighted':
            merged = self._resolve_by_confidence(combined)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
        
        conflicts = self._detect_conflicts(combined)
        
        return PipelineResult(
            success=True,
            data=merged,
            errors=[],
            metadata={
                'total_records': len(merged),
                'conflicts_detected': len(conflicts),
                'resolution_strategy': self.strategy
            }
        )
    
    def _resolve_by_priority(self, df: pd.DataFrame) -> pd.DataFrame:
        # Sort by priority and keep first (highest priority)
        return df.sort_values('_priority').drop_duplicates(
            subset=['symbol', 'trade_date'],
            keep='first'
        ).drop(columns=['_source', '_priority'])
    
    def _detect_conflicts(self, df: pd.DataFrame) -> List[Dict]:
        # Group by (symbol, trade_date) and find groups with multiple sources
        conflicts = []
        grouped = df.groupby(['symbol', 'trade_date'])
        
        for (symbol, trade_date), group in grouped:
            if len(group) > 1:
                # Check if close prices differ by >1%
                close_prices = group['close'].values
                if (close_prices.max() - close_prices.min()) / close_prices.mean() > 0.01:
                    conflicts.append({
                        'symbol': symbol,
                        'trade_date': trade_date,
                        'sources': group['_source'].tolist(),
                        'close_prices': close_prices.tolist()
                    })
        
        return conflicts
```

**Why:** Priority 3 because conflicts are less common than time/anomaly issues. Priority strategy is simplest and works well when one source is consistently more reliable.

**How to apply:** Log conflicts for manual review. If conflict rate >5%, investigate data source quality.

---

#### Stage 6: ImputationStage (Priority 4)

**Purpose:** Fill missing values with appropriate strategies.

**Input:** `pd.DataFrame` - Merged data

**Output:** `pd.DataFrame` - Complete data

**Implementation:**
```python
class ImputationStage(PipelineStage):
    def execute(self, context: PipelineContext) -> PipelineResult:
        df = context.data.copy()
        imputation_stats = {}
        
        # Price data: forward fill (use last known price during suspension)
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            missing_before = df[col].isna().sum()
            df[col] = df.groupby('symbol')[col].fillna(method='ffill')
            missing_after = df[col].isna().sum()
            imputation_stats[col] = {
                'missing_before': int(missing_before),
                'missing_after': int(missing_after),
                'filled': int(missing_before - missing_after)
            }
        
        # Volume: fill with 0 (no trading during suspension)
        df['volume'] = df['volume'].fillna(0)
        df['amount'] = df['amount'].fillna(0)
        
        # Financial data: do NOT fill (preserve NULL for missing quarters)
        # This is handled separately in financial data pipeline
        
        return PipelineResult(
            success=True,
            data=df,
            errors=[],
            metadata={'imputation_stats': imputation_stats}
        )
```

**Why:** Priority 4 because missing data is less critical than alignment/anomaly issues. Forward fill is appropriate for prices during suspensions.

**How to apply:** Only fill price/volume data. Never fill financial data (PE, ROE, etc.) as NULL has semantic meaning (data not yet released).

---

#### Stage 7: StorageStage

**Purpose:** Write data to three-layer storage in PostgreSQL.

**Input:** `pd.DataFrame` - Complete cleaned data

**Output:** Database write confirmation

**Implementation:**
```python
class StorageStage(PipelineStage):
    def __init__(self, raw_repo: RawKlineRepository, kline_repo: KlineRepository):
        self.raw_repo = raw_repo
        self.kline_repo = kline_repo
    
    def execute(self, context: PipelineContext) -> PipelineResult:
        df = context.data
        
        # 1. Save raw data (from earlier stage context)
        raw_data = context.metadata.get('raw_data', {})
        for source, raw_df in raw_data.items():
            self.raw_repo.batch_upsert(raw_df, batch_size=50)
        
        # 2. Save cleaned data
        self.kline_repo.batch_upsert(df, batch_size=50)
        
        return PipelineResult(
            success=True,
            data=df,
            errors=[],
            metadata={
                'raw_records_saved': sum(len(d) for d in raw_data.values()),
                'cleaned_records_saved': len(df)
            }
        )
```

**Database Schema:**
```sql
-- Raw data table
CREATE TABLE quant.raw_klines (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    amount DECIMAL(20,2),
    fetch_time TIMESTAMP DEFAULT NOW(),
    UNIQUE(source, symbol, trade_date)
);

-- Cleaned data table
CREATE TABLE quant.daily_klines (
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    amount DECIMAL(20,2),
    adj_factor DECIMAL(10,6) DEFAULT 1.0,
    is_suspended BOOLEAN DEFAULT FALSE,
    quality_score DECIMAL(5,2),
    processed_time TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date)
);

-- Factor data table
CREATE TABLE quant.factors (
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    factor_value DECIMAL(20,6),
    computed_time TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date, factor_name)
);

-- Indexes
CREATE INDEX idx_daily_klines_date ON quant.daily_klines(trade_date);
CREATE INDEX idx_daily_klines_symbol ON quant.daily_klines(symbol);
CREATE INDEX idx_factors_date ON quant.factors(trade_date);
CREATE INDEX idx_factors_name ON quant.factors(factor_name);
```

**Why:** Three-layer storage enables re-processing (raw), fast queries (cleaned), and avoids redundant computation (factors).

---

#### Stage 8: FactorComputeStage

**Purpose:** Trigger factor computation on cleaned data.

**Input:** `pd.DataFrame` - Cleaned kline data

**Output:** Factor computation confirmation

**Implementation:**
```python
class FactorComputeStage(PipelineStage):
    def __init__(self, factor_service: FactorService, factor_repo: FactorRepository):
        self.factor_service = factor_service
        self.factor_repo = factor_repo
    
    def execute(self, context: PipelineContext) -> PipelineResult:
        df = context.data
        
        # Compute factors using existing FactorService
        symbols = df['symbol'].unique().tolist()
        date_range = (df['trade_date'].min(), df['trade_date'].max())
        
        factors_df = self.factor_service.compute_factors(
            symbols=symbols,
            date_range=date_range,
            factor_names=['momentum', 'value', 'quality', 'volatility']  # configurable
        )
        
        # Batch write to factors table
        self.factor_repo.batch_upsert(factors_df, batch_size=100)
        
        return PipelineResult(
            success=True,
            data=factors_df,
            errors=[],
            metadata={
                'factors_computed': len(factors_df),
                'symbols': len(symbols),
                'date_range': date_range
            }
        )
```

**Integration:** Reuses existing `services/factor_service.py` and `repositories/factor_repository.py`.

**Why:** Separating factor computation as a stage allows independent testing and optional skipping (e.g., when only updating raw data).

---

## 4. Orchestration Layer

### 4.1 DataPipelineService

**Purpose:** High-level service for constructing and executing pipelines.

```python
class DataPipelineService:
    def __init__(self):
        self.pipeline_builder = PipelineBuilder()
        self.monitor = DataPipelineMonitor(event_bus)
        self.config = self._load_config()
    
    def run_daily_update(self, symbols: List[str], date: str) -> PipelineResult:
        """Execute daily incremental update."""
        pipeline = self.pipeline_builder \
            .add_stage(DataFetchStage(
                sources=self.config['sources'],
                symbols=symbols,
                date_range=(date, date)
            )) \
            .add_stage(DeduplicationStage()) \
            .add_stage(TimeAlignmentStage(
                calendar=self.config['calendar'],
                timezone=self.config['timezone']
            )) \
            .add_stage(AnomalyDetectionStage(DataValidator())) \
            .add_stage(ConflictResolutionStage(
                strategy=self.config['conflict_strategy'],
                priority=self.config['source_priority']
            )) \
            .add_stage(ImputationStage()) \
            .add_stage(StorageStage(raw_repo, kline_repo)) \
            .add_stage(FactorComputeStage(factor_service, factor_repo)) \
            .with_monitor(self.monitor) \
            .with_error_handler(PipelineErrorHandler()) \
            .build()
        
        result = pipeline.execute()
        
        # Generate execution report
        report = self.monitor.generate_report()
        logger.info(f"Pipeline completed: {report}")
        
        return result
    
    def run_full_rebuild(self, symbols: List[str], start_date: str, end_date: str) -> PipelineResult:
        """Execute full rebuild (weekly)."""
        # Same pipeline, different date range
        # Can configure to skip DataFetchStage if raw data already exists
        pass
    
    def _load_config(self) -> Dict:
        # Load from config/data_pipeline.yaml
        pass
```

### 4.2 Configuration

**File:** `config/data_pipeline.yaml`

```yaml
pipeline:
  name: "daily_data_update"
  
  # Data sources
  sources:
    - akshare
    - tushare
    - eastmoney
  
  source_priority:
    - akshare
    - tushare
    - eastmoney
  
  # Stock pool
  symbols:
    type: "index_components"
    index: "000300.SH"  # 沪深300
  
  # Calendar and timezone
  calendar: "SSE"
  timezone: "Asia/Shanghai"
  
  # Conflict resolution
  conflict_strategy: "priority"  # or "voting", "weighted"
  
  # Execution
  execution:
    mode: "incremental"
    batch_size: 50
    parallel: true
    max_workers: 4
  
  # Quality thresholds
  quality:
    min_score: 60
    max_error_rate: 0.1
    alert_on_low_quality: true
```

---

## 5. Error Handling

### 5.1 Error Handling Strategy

```python
class PipelineErrorHandler:
    def handle_stage_error(self, stage: PipelineStage, error: Exception, context: PipelineContext):
        if isinstance(error, DataSourceTimeout):
            # Retry 3 times with exponential backoff
            return RetryStrategy(max_retries=3, backoff_seconds=[5, 10, 20])
        
        elif isinstance(error, DataQualityError):
            # Skip problematic symbol, continue with others
            return SkipStrategy(scope='symbol', log_level='warning')
        
        elif isinstance(error, DatabaseError):
            # Critical: rollback and fail immediately
            return FailFastStrategy(rollback=True)
        
        else:
            # Unknown error: log and continue
            return ContinueStrategy(log_level='error')
```

### 5.2 Stage-Level Error Handling

Each stage implements graceful degradation:

```python
class TimeAlignmentStage(PipelineStage):
    def execute(self, context: PipelineContext) -> PipelineResult:
        results = {}
        errors = []
        
        for source, df in context.data.items():
            try:
                aligned_df = self._align_timestamps(df)
                results[source] = aligned_df
            except Exception as e:
                # Log error but don't fail entire pipeline
                errors.append({
                    'source': source,
                    'error': str(e),
                    'timestamp': datetime.now()
                })
                logger.warning(f"Failed to align {source}: {e}")
        
        # Success if at least one source succeeded
        return PipelineResult(
            success=len(results) > 0,
            data=results,
            errors=errors,
            metadata={'aligned_sources': len(results)}
        )
```

### 5.3 Transaction Management

```python
class StorageStage(PipelineStage):
    def execute(self, context: PipelineContext) -> PipelineResult:
        with self.kline_repo.transaction() as txn:
            try:
                # Write raw data
                self.raw_repo.batch_upsert(raw_data, batch_size=50)
                
                # Write cleaned data
                self.kline_repo.batch_upsert(cleaned_data, batch_size=50)
                
                txn.commit()
            except Exception as e:
                txn.rollback()
                raise DatabaseError(f"Storage failed: {e}")
```

---

## 6. Monitoring and Alerting

### 6.1 Execution Monitoring

```python
class DataPipelineMonitor:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.metrics = {}
    
    def on_stage_start(self, stage_name: str):
        self.metrics[stage_name] = {
            'start_time': datetime.now(),
            'status': 'running'
        }
    
    def on_stage_complete(self, stage_name: str, result: PipelineResult):
        duration = (datetime.now() - self.metrics[stage_name]['start_time']).total_seconds()
        
        self.metrics[stage_name].update({
            'end_time': datetime.now(),
            'duration': duration,
            'status': 'success' if result.success else 'failed',
            'records_processed': result.metadata.get('records_count', 0)
        })
        
        # Publish event for alerting
        self.event_bus.publish('pipeline.stage.completed', {
            'stage': stage_name,
            'metrics': self.metrics[stage_name]
        })
    
    def generate_report(self) -> Dict:
        total_duration = sum(m['duration'] for m in self.metrics.values())
        success_count = sum(1 for m in self.metrics.values() if m['status'] == 'success')
        
        return {
            'total_duration': total_duration,
            'success_rate': success_count / len(self.metrics),
            'stages': self.metrics
        }
```

### 6.2 Alert Rules

```python
class DataPipelineAlertHandler:
    def handle_stage_completed(self, event: Event):
        metrics = event.data['metrics']
        stage = event.data['stage']
        
        # Alert 1: Execution time > 1 hour
        if metrics['duration'] > 3600:
            self.send_alert(
                level='warning',
                message=f"Stage {stage} took {metrics['duration']:.0f}s (>1h)"
            )
        
        # Alert 2: Quality score < 60
        if metrics.get('quality_score', 100) < 60:
            self.send_alert(
                level='error',
                message=f"Low quality score: {metrics['quality_score']}"
            )
        
        # Alert 3: Error rate > 10%
        if metrics.get('error_rate', 0) > 0.1:
            self.send_alert(
                level='error',
                message=f"High error rate: {metrics['error_rate']:.1%}"
            )
```

---

## 7. Scheduling

### 7.1 Daily Update Task

```python
from runtime.scheduler import scheduler

@scheduler.scheduled_job('cron', hour=16, minute=30)
def daily_data_pipeline():
    """Execute daily incremental update at 16:30 (after market close)."""
    service = DataPipelineService()
    
    # Get 沪深300 components
    symbols = get_index_components('000300.SH')
    
    # Process today's data
    today = datetime.now().strftime('%Y-%m-%d')
    result = service.run_daily_update(symbols, today)
    
    logger.info(f"Daily pipeline completed: {result.metadata}")
    
    return result
```

### 7.2 Weekly Full Rebuild

```python
@scheduler.scheduled_job('cron', day_of_week='sun', hour=2)
def weekly_full_rebuild():
    """Execute full rebuild every Sunday at 2:00 AM."""
    service = DataPipelineService()
    symbols = get_index_components('000300.SH')
    
    # Rebuild last 90 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    result = service.run_full_rebuild(
        symbols,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    logger.info(f"Weekly rebuild completed: {result.metadata}")
    
    return result
```

---

## 8. Testing Strategy

### 8.1 Unit Tests (Stage Level)

```python
# tests/test_time_alignment_stage.py
class TestTimeAlignmentStage:
    def test_timezone_conversion(self):
        stage = TimeAlignmentStage(calendar='SSE', timezone='Asia/Shanghai')
        
        input_data = pd.DataFrame({
            'symbol': ['600000.SH'],
            'timestamp': [pd.Timestamp('2024-01-01 01:30:00', tz='UTC')],
            'close': [1800.0]
        })
        
        result = stage.execute(PipelineContext(data={'test': input_data}))
        
        assert result.success
        assert result.data['test']['timestamp'][0].tz.zone == 'Asia/Shanghai'
        assert result.data['test']['timestamp'][0].hour == 9
    
    def test_non_trading_day_filter(self):
        stage = TimeAlignmentStage(calendar='SSE')
        
        input_data = pd.DataFrame({
            'symbol': ['600000.SH'] * 3,
            'trade_date': ['2024-01-05', '2024-01-06', '2024-01-07'],  # Fri, Sat, Sun
            'close': [1800.0, 1810.0, 1820.0]
        })
        
        result = stage.execute(PipelineContext(data={'test': input_data}))
        
        assert len(result.data['test']) == 1  # Only Friday
        assert result.data['test']['trade_date'][0] == '2024-01-05'
    
    def test_suspension_marking(self):
        stage = TimeAlignmentStage(calendar='SSE')
        
        input_data = pd.DataFrame({
            'symbol': ['600000.SH'] * 2,
            'trade_date': ['2024-01-05', '2024-01-08'],
            'volume': [1000000, 0],  # Normal, suspended
            'close': [1800.0, 1800.0]
        })
        
        result = stage.execute(PipelineContext(data={'test': input_data}))
        
        assert result.data['test']['is_suspended'][0] == False
        assert result.data['test']['is_suspended'][1] == True
```

### 8.2 Integration Tests (Pipeline Level)

```python
# tests/test_data_pipeline_integration.py
class TestDataPipelineIntegration:
    @pytest.fixture
    def test_database(self):
        # Uses quant_test database (automatic via conftest.py)
        yield
    
    def test_full_pipeline_execution(self, test_database):
        service = DataPipelineService()
        
        symbols = ['600000.SH', '000001.SZ']
        date = '2024-01-05'
        
        result = service.run_daily_update(symbols, date)
        
        # Verify pipeline success
        assert result.success
        
        # Verify data in database
        repo = KlineRepository()
        klines = repo.get_daily_klines('600000.SH', date, date)
        
        assert len(klines) > 0
        assert klines[0]['quality_score'] >= 60
        assert klines[0]['is_suspended'] is not None
    
    def test_multi_source_conflict_resolution(self, test_database):
        with patch('data_sources.akshare_source.fetch') as mock_akshare, \
             patch('data_sources.tushare_source.fetch') as mock_tushare:
            
            # Mock different prices from two sources
            mock_akshare.return_value = pd.DataFrame({
                'symbol': ['600000.SH'],
                'trade_date': ['2024-01-05'],
                'close': [1800.0]
            })
            
            mock_tushare.return_value = pd.DataFrame({
                'symbol': ['600000.SH'],
                'trade_date': ['2024-01-05'],
                'close': [1805.0]
            })
            
            service = DataPipelineService()
            result = service.run_daily_update(['600000.SH'], '2024-01-05')
            
            # Verify priority strategy (akshare wins)
            repo = KlineRepository()
            klines = repo.get_daily_klines('600000.SH', '2024-01-05', '2024-01-05')
            assert klines[0]['close'] == 1800.0
```

### 8.3 Data Quality Tests

```python
# tests/test_data_quality.py
class TestDataQuality:
    def test_no_duplicate_records(self):
        repo = KlineRepository()
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        klines = repo.get_daily_klines('600000.SH', start_date, end_date)
        
        dates = [k['trade_date'] for k in klines]
        assert len(dates) == len(set(dates))  # No duplicates
    
    def test_price_continuity(self):
        repo = KlineRepository()
        klines = repo.get_latest('600000.SH', limit=100)
        
        df = pd.DataFrame(klines)
        returns = df['close'].pct_change().dropna()
        
        # Daily returns within reasonable range (-20% to +20%)
        assert (returns.abs() < 0.2).all()
    
    def test_quality_score_threshold(self):
        repo = KlineRepository()
        klines = repo.get_latest('600000.SH', limit=30)
        
        quality_scores = [k['quality_score'] for k in klines if k['quality_score']]
        assert all(score >= 80 for score in quality_scores)
```

---

## 9. Implementation Plan

### Phase 1: Foundation (1-2 days)

**Tasks:**
1. Create directory structure: `quant/stages/data/`
2. Define `PipelineContext` and `PipelineResult` data structures
3. Create database schema (raw_klines, daily_klines, factors tables)
4. Implement `DataPipelineService` skeleton
5. Set up configuration file (`config/data_pipeline.yaml`)

**Deliverables:**
- Directory structure in place
- Database tables created
- Basic service class with config loading

---

### Phase 2: Core Stages (3-4 days)

**Tasks:**
1. Implement `DataFetchStage` (reuse existing `data_sources/`)
2. Implement `TimeAlignmentStage` (Priority 1)
   - Trading calendar integration
   - Timezone conversion
   - Suspension marking
3. Implement `AnomalyDetectionStage` (Priority 2)
   - Integrate `DataValidator`
   - Quality score calculation
4. Implement `ConflictResolutionStage` (Priority 3)
   - Priority strategy
   - Conflict detection and logging
5. Implement `StorageStage`
   - Three-layer writes
   - Batch upsert with transactions

**Deliverables:**
- 5 core stages implemented and unit tested
- Integration with existing infrastructure (DataValidator, repositories)

---

### Phase 3: Secondary Stages and Integration (2-3 days)

**Tasks:**
1. Implement `DeduplicationStage`
2. Implement `ImputationStage` (Priority 4)
3. Implement `FactorComputeStage` (integrate with `FactorService`)
4. Add error handling (`PipelineErrorHandler`)
5. Add monitoring (`DataPipelineMonitor`)
6. Implement alert rules

**Deliverables:**
- All 8 stages complete
- Error handling and monitoring in place
- Alert system configured

---

### Phase 4: Testing and Optimization (2-3 days)

**Tasks:**
1. Write unit tests for each stage (target: >80% coverage)
2. Write integration tests for full pipeline
3. Write data quality validation tests
4. Performance optimization:
   - Batch processing (50 stocks per batch)
   - Parallel data fetching
   - Database query optimization
5. Set up scheduled tasks (daily update, weekly rebuild)

**Deliverables:**
- Comprehensive test suite
- Performance benchmarks (300 stocks in <1 hour)
- Scheduled tasks configured

---

**Total Estimated Time: 8-12 days**

---

## 10. Success Criteria

### 10.1 Functional Criteria

- ✅ Successfully fetch data from 3+ sources (akshare, tushare, eastmoney)
- ✅ Process 300 stocks (沪深300) without errors
- ✅ Detect and resolve conflicts between data sources
- ✅ Generate data quality reports with scores ≥80
- ✅ Store data in three layers (raw, cleaned, factors)
- ✅ Compute factors on cleaned data

### 10.2 Performance Criteria

- ✅ Complete daily update in <1 hour for 300 stocks
- ✅ Database writes use batch operations (50 stocks/batch)
- ✅ Factor computation uses vectorized operations

### 10.3 Quality Criteria

- ✅ No duplicate records in cleaned data
- ✅ All timestamps aligned to SSE trading calendar
- ✅ Price continuity (daily returns within -20% to +20%)
- ✅ Quality score ≥80 for 95% of records

### 10.4 Reliability Criteria

- ✅ Graceful handling of data source failures (skip and continue)
- ✅ Transaction rollback on database errors
- ✅ Alert on execution time >1h, quality score <60, error rate >10%

---

## 11. Future Enhancements

### 11.1 Short-term (Next 3 months)

1. **Minute-level data support** - Extend pipeline to handle intraday data
2. **More conflict resolution strategies** - Implement voting and weighted strategies
3. **Data lineage tracking** - Record which source contributed each field
4. **Performance dashboard** - Visualize pipeline execution metrics

### 11.2 Long-term (6+ months)

1. **Real-time streaming** - Migrate to event-driven architecture for tick data
2. **Machine learning for conflict resolution** - Learn which source is most reliable per field
3. **Distributed processing** - Scale to full A-share market (5000+ stocks)
4. **Time-series database** - Migrate to TimescaleDB or ClickHouse for better performance

---

## 12. Appendix

### 12.1 File Structure

```
quantsys-v2/
├── quant/
│   └── stages/
│       └── data/
│           ├── __init__.py
│           ├── data_fetch_stage.py
│           ├── deduplication_stage.py
│           ├── time_alignment_stage.py
│           ├── anomaly_detection_stage.py
│           ├── conflict_resolution_stage.py
│           ├── imputation_stage.py
│           ├── storage_stage.py
│           └── factor_compute_stage.py
├── services/
│   └── data_pipeline_service.py
├── config/
│   └── data_pipeline.yaml
├── tests/
│   ├── test_data_fetch_stage.py
│   ├── test_time_alignment_stage.py
│   ├── test_anomaly_detection_stage.py
│   ├── test_conflict_resolution_stage.py
│   ├── test_data_pipeline_integration.py
│   └── test_data_quality.py
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-26-data-pipeline-design.md
```

### 12.2 Dependencies

**Existing Components:**
- `core/pipeline.py` - Pipeline framework
- `quantlib/data_validator.py` - Data validation
- `repositories/kline_repository.py` - K-line data access
- `repositories/factor_repository.py` - Factor data access
- `data_sources/` - Data source adapters
- `services/factor_service.py` - Factor computation
- `runtime/scheduler/` - Task scheduling
- `runtime/events/` - Event bus

**New Dependencies:**
- None (all functionality uses existing infrastructure)

### 12.3 Configuration Reference

See `config/data_pipeline.yaml` in Section 4.2 for full configuration options.

---

**End of Specification**

