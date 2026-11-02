# Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a comprehensive data processing pipeline for quantsys-v2 that fetches, cleans, validates, stores, and computes factors on stock market data from multiple sources.

**Architecture:** Pipeline pattern with 8 composable stages, three-layer storage (raw/cleaned/factors), configuration-driven orchestration.

**Tech Stack:** Python 3.13, PostgreSQL, pandas, quantlib/DataValidator, core/pipeline.py

**Spec:** `docs/superpowers/specs/2026-05-26-data-pipeline-design.md`

---

## Implementation Strategy

This plan implements 8 pipeline stages + orchestration in 4 phases (16 tasks total):

1. **Foundation** (Tasks 1-3): Database schema, config, base classes
2. **Core Stages** (Tasks 4-11): 8 data processing stages with TDD
3. **Orchestration** (Tasks 12-14): Service layer, error handling, monitoring
4. **Integration** (Tasks 15-16): Scheduling, end-to-end tests

Each task follows TDD: Write failing test → Implement → Pass test → Commit

---

## Phase 1: Foundation

### Task 1: Database Schema

**Files:** Create `migrations/create_data_pipeline_tables.sql`

- [ ] **Step 1: Write SQL migration**

```sql
-- migrations/create_data_pipeline_tables.sql

-- Raw data table (preserves all source data)
CREATE TABLE IF NOT EXISTS quant.raw_klines (
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

-- Cleaned data table (merged and validated)
CREATE TABLE IF NOT EXISTS quant.daily_klines (
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

-- Factor data table (computed factors)
CREATE TABLE IF NOT EXISTS quant.factors (
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    factor_value DECIMAL(20,6),
    computed_time TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date, factor_name)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_raw_klines_symbol ON quant.raw_klines(symbol);
CREATE INDEX IF NOT EXISTS idx_raw_klines_date ON quant.raw_klines(trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_klines_date ON quant.daily_klines(trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol ON quant.daily_klines(symbol);
CREATE INDEX IF NOT EXISTS idx_factors_date ON quant.factors(trade_date);
CREATE INDEX IF NOT EXISTS idx_factors_name ON quant.factors(factor_name);

-- Trading calendar table (if not exists)
CREATE TABLE IF NOT EXISTS quant.trading_calendar (
    trade_date DATE PRIMARY KEY,
    exchange VARCHAR(10) NOT NULL,
    is_trading_day BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_trading_calendar_exchange ON quant.trading_calendar(exchange);
```

- [ ] **Step 2: Run migration**

Run: `psql -h 127.0.0.1 -p 5432 -U your_user -d quant_investment -f migrations/create_data_pipeline_tables.sql`

Expected: "CREATE TABLE" messages for each table

- [ ] **Step 3: Verify tables**

Run: `psql -h 127.0.0.1 -p 5432 -U your_user -d quant_investment -c "\dt quant.*"`

Expected: See raw_klines, daily_klines, factors, trading_calendar

- [ ] **Step 4: Commit**

```bash
git add migrations/create_data_pipeline_tables.sql
git commit -m "feat(db): add data pipeline tables schema

- raw_klines: preserve original data from each source
- daily_klines: cleaned and merged data
- factors: computed factor values
- trading_calendar: SSE/SZSE trading days"
```

---

### Task 2: Configuration File

**Files:** Create `config/data_pipeline.yaml`

- [ ] **Step 1: Write configuration**

```yaml
# config/data_pipeline.yaml

pipeline:
  name: "daily_data_update"
  
  # Data sources (in priority order)
  sources:
    - akshare
    - tushare
  
  source_priority:
    - akshare
    - tushare
  
  # Stock pool configuration
  symbols:
    type: "index_components"
    index: "000300.SH"  # 沪深300
  
  # Calendar and timezone
  calendar: "SSE"
  timezone: "Asia/Shanghai"
  
  # Conflict resolution strategy
  conflict_strategy: "priority"  # options: priority, voting, weighted
  
  # Execution settings
  execution:
    mode: "incremental"  # options: incremental, full_rebuild
    batch_size: 50
    parallel: true
    max_workers: 4
  
  # Quality thresholds
  quality:
    min_score: 60
    max_error_rate: 0.1
    price_jump_threshold: 0.5  # 50% price change
    volume_zscore_threshold: 3.0
  
  # Imputation strategies
  imputation:
    price_method: "ffill"  # forward fill
    volume_method: "zero"  # fill with 0
  
  # Retry settings
  retry:
    max_retries: 3
    backoff_seconds: [5, 10, 20]
  
  # Alert settings
  alerts:
    enabled: true
    max_duration_seconds: 3600  # 1 hour
    min_quality_score: 60
    max_error_rate: 0.1
```

- [ ] **Step 2: Commit**

```bash
git add config/data_pipeline.yaml
git commit -m "feat(config): add data pipeline configuration

- Multi-source settings with priority
- Quality thresholds and retry logic
- Alert rules for monitoring"
```

---

### Task 3: Base Classes

**Files:** Create `quant/stages/data/__init__.py`

- [ ] **Step 1: Write base classes**

```python
# quant/stages/data/__init__.py
"""
Data processing stages for the pipeline.

Stages:
1. DataFetchStage - Multi-source data acquisition
2. DeduplicationStage - Remove duplicates
3. TimeAlignmentStage - Calendar and timezone alignment
4. AnomalyDetectionStage - Data quality checks
5. ConflictResolutionStage - Multi-source conflict resolution
6. ImputationStage - Fill missing values
7. StorageStage - Three-layer database writes
8. FactorComputeStage - Trigger factor computation
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PipelineContext:
    """Context passed between pipeline stages."""
    data: Any
    config: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class PipelineResult:
    """Result returned by each pipeline stage."""
    success: bool
    data: Any
    errors: List[Dict]
    metadata: Dict[str, Any]


__all__ = [
    'PipelineContext',
    'PipelineResult',
]
```

- [ ] **Step 2: Commit**

```bash
git add quant/stages/data/__init__.py
git commit -m "feat(pipeline): add data stage base classes

- PipelineContext for data passing
- PipelineResult for stage outputs"
```

---

## Phase 2: Core Stages (TDD Pattern)

**Note:** Tasks 4-11 follow the same TDD pattern. For brevity, I'll show the full pattern for Task 4, then summarize Tasks 5-11.

### Task 4: DataFetchStage (Full TDD Example)

**Files:** 
- Create: `quant/stages/data/data_fetch_stage.py`
- Create: `tests/test_data_fetch_stage.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_data_fetch_stage.py
import pytest
import pandas as pd
from datetime import datetime
from quant.stages.data.data_fetch_stage import DataFetchStage
from quant.stages.data import PipelineContext, PipelineResult


class TestDataFetchStage:
    def test_fetch_from_single_source(self, mocker):
        """Test fetching data from a single source."""
        mock_source = mocker.Mock()
        mock_source.fetch_klines.return_value = pd.DataFrame({
            'symbol': ['600000.SH'],
            'trade_date': ['2024-01-05'],
            'close': [1800.0],
            'volume': [1000000]
        })
        
        mock_registry = mocker.Mock()
        mock_registry.get.return_value = mock_source
        
        stage = DataFetchStage(
            sources=['akshare'],
            symbols=['600000.SH'],
            date_range=('2024-01-05', '2024-01-05')
        )
        stage.data_source_registry = mock_registry
        
        context = PipelineContext(data={}, config={}, metadata={})
        result = stage.execute(context)
        
        assert result.success
        assert 'akshare' in result.data
        assert len(result.data['akshare']) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_fetch_stage.py::TestDataFetchStage::test_fetch_from_single_source -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'quant.stages.data.data_fetch_stage'"

- [ ] **Step 3: Write minimal implementation**

```python
# quant/stages/data/data_fetch_stage.py
"""DataFetchStage - Multi-source data acquisition."""

import logging
from typing import List, Tuple
from datetime import datetime
import pandas as pd

from quant.stages.data import PipelineContext, PipelineResult
from data_sources import DataSourceRegistry

logger = logging.getLogger(__name__)


class DataFetchStage:
    """Fetch data from multiple sources in parallel."""
    
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
                logger.info(f"Fetched {len(df)} records from {source_name}")
            except Exception as e:
                errors.append({'source': source_name, 'error': str(e), 'timestamp': datetime.now()})
                logger.warning(f"Failed to fetch from {source_name}: {e}")
        
        return PipelineResult(
            success=len(results) > 0,
            data=results,
            errors=errors,
            metadata={'sources_fetched': len(results), 'total_records': sum(len(df) for df in results.values())}
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_fetch_stage.py::TestDataFetchStage::test_fetch_from_single_source -v`

Expected: PASS

- [ ] **Step 5: Add more tests**

Add to `tests/test_data_fetch_stage.py`:

```python
    def test_fetch_from_multiple_sources(self, mocker):
        """Test fetching from multiple sources."""
        # Mock two sources returning different data
        # Verify both sources in result.data
        pass  # Implementation similar to test_fetch_from_single_source
    
    def test_handle_source_failure_gracefully(self, mocker):
        """Test that one source failure doesn't stop pipeline."""
        # Mock one source raising exception, other succeeding
        # Verify result.success=True, len(result.data)==1, len(result.errors)==1
        pass
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/test_data_fetch_stage.py -v`

Expected: PASS (all 3 tests)

- [ ] **Step 7: Commit**

```bash
git add quant/stages/data/data_fetch_stage.py tests/test_data_fetch_stage.py
git commit -m "feat(pipeline): implement DataFetchStage

- Fetch data from multiple sources in parallel
- Graceful error handling (skip failed sources)
- Add source and fetch_time metadata"
```

---

### Tasks 5-11: Remaining Stages (Summary)

**Each task follows the same TDD pattern as Task 4. Key implementations:**

**Task 5: DeduplicationStage**
- Test: Remove duplicates, keep latest fetch_time
- Implementation: `df.sort_values('fetch_time').drop_duplicates(['symbol','trade_date'], keep='last')`
- Commit: "feat(pipeline): implement DeduplicationStage"

**Task 6: TimeAlignmentStage (Priority 1)**
- Test: Filter non-trading days, mark suspensions
- Implementation: Load trading calendar from DB, filter dates, mark volume==0 as suspended
- Commit: "feat(pipeline): implement TimeAlignmentStage (Priority 1)"

**Task 7: AnomalyDetectionStage (Priority 2)**
- Test: Detect price jumps, assign quality scores
- Implementation: Integrate quantlib.DataValidator, add quality_score column
- Commit: "feat(pipeline): implement AnomalyDetectionStage (Priority 2)"

**Task 8: ConflictResolutionStage (Priority 3)**
- Test: Merge sources by priority, detect conflicts
- Implementation: Concat sources, sort by priority, drop_duplicates(['symbol','trade_date'], keep='first')
- Commit: "feat(pipeline): implement ConflictResolutionStage (Priority 3)"

**Task 9: ImputationStage (Priority 4)**
- Test: Forward-fill prices, zero-fill volume
- Implementation: `df.groupby('symbol')['close'].fillna(method='ffill')`, `df['volume'].fillna(0)`
- Commit: "feat(pipeline): implement ImputationStage (Priority 4)"

**Task 10: StorageStage**
- Test: Write to raw_klines and daily_klines
- Implementation: batch_upsert to repositories (add batch_upsert method if missing)
- Commit: "feat(pipeline): implement StorageStage"

**Task 11: FactorComputeStage**
- Test: Trigger factor computation
- Implementation: Call existing FactorService.compute_factors(), write to factor_repository
- Commit: "feat(pipeline): implement FactorComputeStage"

---

## Phase 3: Orchestration

### Task 12: DataPipelineService

**Files:**
- Create: `services/data_pipeline_service.py`
- Create: `tests/test_data_pipeline_service.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_data_pipeline_service.py
def test_run_daily_update_builds_pipeline(mocker):
    """Test that run_daily_update builds and executes pipeline."""
    service = DataPipelineService()
    
    # Mock pipeline builder
    mock_pipeline = mocker.Mock()
    mock_pipeline.execute.return_value = PipelineResult(success=True, data={}, errors=[], metadata={})
    
    result = service.run_daily_update(['600000.SH'], '2024-01-05')
    
    assert result.success
```

- [ ] **Step 2: Run test (expect FAIL)**

- [ ] **Step 3: Implement DataPipelineService**

```python
# services/data_pipeline_service.py
import yaml
from quant.stages.data.data_fetch_stage import DataFetchStage
from quant.stages.data.deduplication_stage import DeduplicationStage
from quant.stages.data.time_alignment_stage import TimeAlignmentStage
from quant.stages.data.anomaly_detection_stage import AnomalyDetectionStage
from quant.stages.data.conflict_resolution_stage import ConflictResolutionStage
from quant.stages.data.imputation_stage import ImputationStage
from quant.stages.data.storage_stage import StorageStage
from quant.stages.data.factor_compute_stage import FactorComputeStage
from quantlib.data_validator import DataValidator
from core.pipeline import PipelineBuilder


class DataPipelineService:
    def __init__(self):
        self.config = self._load_config()
    
    def run_daily_update(self, symbols, date):
        pipeline = PipelineBuilder() \
            .add_stage(DataFetchStage(self.config['sources'], symbols, (date, date))) \
            .add_stage(DeduplicationStage()) \
            .add_stage(TimeAlignmentStage(self.config['calendar'], self.config['timezone'])) \
            .add_stage(AnomalyDetectionStage(DataValidator())) \
            .add_stage(ConflictResolutionStage(self.config['source_priority'])) \
            .add_stage(ImputationStage()) \
            .add_stage(StorageStage()) \
            .add_stage(FactorComputeStage()) \
            .build()
        
        return pipeline.execute()
    
    def _load_config(self):
        with open('config/data_pipeline.yaml') as f:
            return yaml.safe_load(f)['pipeline']
```

- [ ] **Step 4: Run test (expect PASS)**

- [ ] **Step 5: Commit**

```bash
git add services/data_pipeline_service.py tests/test_data_pipeline_service.py
git commit -m "feat(pipeline): implement DataPipelineService orchestration

- Load config from YAML
- Build pipeline with all 8 stages
- Execute and return result"
```

---

### Task 13: Error Handling & Monitoring

**Files:**
- Create: `infrastructure/pipeline/error_handler.py`
- Create: `infrastructure/pipeline/monitor.py`

- [ ] **Step 1: Implement PipelineErrorHandler**

```python
# infrastructure/pipeline/error_handler.py
class PipelineErrorHandler:
    def handle_stage_error(self, stage, error, context):
        if isinstance(error, DataSourceTimeout):
            return RetryStrategy(max_retries=3, backoff_seconds=[5, 10, 20])
        elif isinstance(error, DataQualityError):
            return SkipStrategy(scope='symbol', log_level='warning')
        elif isinstance(error, DatabaseError):
            return FailFastStrategy(rollback=True)
        else:
            return ContinueStrategy(log_level='error')
```

- [ ] **Step 2: Implement DataPipelineMonitor**

```python
# infrastructure/pipeline/monitor.py
class DataPipelineMonitor:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.metrics = {}
    
    def on_stage_start(self, stage_name):
        self.metrics[stage_name] = {'start_time': datetime.now(), 'status': 'running'}
    
    def on_stage_complete(self, stage_name, result):
        duration = (datetime.now() - self.metrics[stage_name]['start_time']).total_seconds()
        self.metrics[stage_name].update({'duration': duration, 'status': 'success' if result.success else 'failed'})
        self.event_bus.publish('pipeline.stage.completed', {'stage': stage_name, 'metrics': self.metrics[stage_name]})
```

- [ ] **Step 3: Add tests**

- [ ] **Step 4: Commit**

```bash
git add infrastructure/pipeline/error_handler.py infrastructure/pipeline/monitor.py
git commit -m "feat(pipeline): add error handling and monitoring

- PipelineErrorHandler with retry/skip/failfast strategies
- DataPipelineMonitor for stage timing and metrics"
```

---

### Task 14: Scheduled Tasks

**Files:** Modify `runtime/scheduler/__init__.py`

- [ ] **Step 1: Add daily task**

```python
# runtime/scheduler/__init__.py
from runtime.scheduler import scheduler
from services.data_pipeline_service import DataPipelineService
from datetime import datetime

@scheduler.scheduled_job('cron', hour=16, minute=30, day_of_week='mon-fri')
def daily_data_pipeline():
    """Execute daily incremental update at 16:30 (after market close)."""
    service = DataPipelineService()
    symbols = get_index_components('000300.SH')  # Get 沪深300 components
    today = datetime.now().strftime('%Y-%m-%d')
    result = service.run_daily_update(symbols, today)
    logger.info(f"Daily pipeline completed: {result.metadata}")
    return result

@scheduler.scheduled_job('cron', day_of_week='sun', hour=2)
def weekly_full_rebuild():
    """Execute full rebuild every Sunday at 2:00 AM."""
    service = DataPipelineService()
    symbols = get_index_components('000300.SH')
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    result = service.run_full_rebuild(symbols, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    logger.info(f"Weekly rebuild completed: {result.metadata}")
    return result
```

- [ ] **Step 2: Test manually**

Run: `python -c "from runtime.scheduler import daily_data_pipeline; daily_data_pipeline()"`

Expected: Pipeline executes successfully

- [ ] **Step 3: Commit**

```bash
git add runtime/scheduler/__init__.py
git commit -m "feat(pipeline): add scheduled tasks for daily/weekly runs

- daily_data_pipeline: 16:30 weekdays
- weekly_full_rebuild: Sunday 2am"
```

---

## Phase 4: Integration & Validation

### Task 15: Integration Tests

**Files:** Create `tests/test_data_pipeline_integration.py`

- [ ] **Step 1: Write full pipeline test**

```python
# tests/test_data_pipeline_integration.py
def test_full_pipeline_execution(test_database, mocker):
    """Test complete pipeline execution end-to-end."""
    # Mock data sources
    mock_akshare = mocker.Mock()
    mock_akshare.fetch_klines.return_value = pd.DataFrame({
        'symbol': ['600000.SH', '000001.SZ'],
        'trade_date': ['2024-01-05', '2024-01-05'],
        'close': [1800.0, 15.0],
        'volume': [1000000, 2000000]
    })
    
    service = DataPipelineService()
    result = service.run_daily_update(['600000.SH', '000001.SZ'], '2024-01-05')
    
    assert result.success
    
    # Verify data in database
    repo = KlineRepository()
    klines = repo.get_daily_klines('600000.SH', '2024-01-05', '2024-01-05')
    assert len(klines) > 0
    assert klines[0]['quality_score'] >= 60
```

- [ ] **Step 2: Write data quality tests**

```python
def test_no_duplicate_records(test_database):
    """Verify no duplicate records in cleaned data."""
    repo = KlineRepository()
    klines = repo.get_daily_klines('600000.SH', '2024-01-01', '2024-01-31')
    dates = [k['trade_date'] for k in klines]
    assert len(dates) == len(set(dates))

def test_price_continuity(test_database):
    """Verify price continuity (no extreme jumps)."""
    repo = KlineRepository()
    klines = repo.get_latest('600000.SH', limit=100)
    df = pd.DataFrame(klines)
    returns = df['close'].pct_change().dropna()
    assert (returns.abs() < 0.2).all()  # Daily returns within ±20%
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_data_pipeline_integration.py -v`

Expected: PASS (all tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_data_pipeline_integration.py
git commit -m "test(pipeline): add integration and data quality tests

- Full pipeline execution test
- Data quality validation (no duplicates, price continuity)"
```

---

### Task 16: Documentation & Final Validation

- [ ] **Step 1: Update README**

Add to README.md:

```markdown
## Data Pipeline

The data pipeline processes stock market data through 8 stages:

1. DataFetch - Fetch from multiple sources (akshare, tushare)
2. Deduplication - Remove duplicates
3. TimeAlignment - Filter non-trading days, mark suspensions
4. AnomalyDetection - Detect price jumps, assign quality scores
5. ConflictResolution - Merge sources by priority
6. Imputation - Fill missing values
7. Storage - Write to three-layer database
8. FactorCompute - Trigger factor computation

### Usage

```python
from services.data_pipeline_service import DataPipelineService

service = DataPipelineService()
result = service.run_daily_update(['600000.SH'], '2024-01-05')
```

### Scheduled Tasks

- Daily update: 16:30 weekdays (after market close)
- Weekly rebuild: Sunday 2:00 AM (last 90 days)
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ --cov=quant/stages/data --cov=services/data_pipeline_service --cov-report=html`

Expected: Coverage >80%

- [ ] **Step 3: Manual validation**

Run: `python -c "from services.data_pipeline_service import DataPipelineService; service = DataPipelineService(); result = service.run_daily_update(['600000.SH', '000001.SZ', '600036.SH', '601318.SH', '000858.SZ'], '2024-01-05'); print(result.metadata)"`

Expected: Pipeline completes successfully, check metadata for stats

- [ ] **Step 4: Verify database**

Run: `psql -h 127.0.0.1 -d quant_investment -c "SELECT COUNT(*) FROM quant.daily_klines WHERE trade_date='2024-01-05'"`

Expected: See records for test stocks

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs(pipeline): add usage documentation and validation

- README with pipeline overview and usage
- Full test suite passing with >80% coverage
- Manual validation successful"
```

---

## Success Criteria Checklist

- [ ] All 16 tasks completed
- [ ] Test coverage >80% for pipeline stages
- [ ] Daily update processes 300 stocks in <1 hour
- [ ] Data quality score ≥80 for 95% of records
- [ ] No duplicate records in daily_klines
- [ ] Scheduled tasks running successfully
- [ ] Database schema created and populated
- [ ] Configuration file in place
- [ ] All tests passing

---

## Execution Notes

**Estimated Time:** 8-12 days (2-3 days per phase)

**Dependencies:**
- Existing: core/pipeline.py, quantlib/data_validator.py, repositories/, data_sources/
- New: All stage implementations, DataPipelineService, scheduled tasks

**Testing Strategy:**
- Unit tests for each stage (TDD)
- Integration tests for full pipeline
- Data quality validation tests
- Manual testing with 沪深300 subset

**Performance Target:**
- 300 stocks processed in <1 hour
- Batch size: 50 stocks per database write
- Parallel data fetching from multiple sources

