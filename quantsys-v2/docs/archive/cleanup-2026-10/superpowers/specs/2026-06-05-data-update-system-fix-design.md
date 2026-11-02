# Data Update System Fix - Design Specification

**Date**: 2026-06-05  
**Author**: System Design  
**Status**: Design Phase

## Executive Summary

Fix the broken `daily-data-update` scheduler task that currently only checks database existence instead of fetching new data. Implement a reliable data update mechanism with multi-source failover, health monitoring, and manual backfill capability.

## Problem Statement

### Current Issues

1. **Core Logic Flaw**: `daily-data-update` task only calls `get_latest_daily_kline()` which checks database, doesn't fetch new data
2. **Network Failure**: AkShare cannot connect to EastMoney servers (HTTPSConnectionPool errors)
3. **Data Lag**: 174 stocks stuck at 2026-05-29, missing 7 trading days (2026-05-30 to 2026-06-05)
4. **Poor Observability**: Limited monitoring and alerting for update failures
5. **Manual Intervention**: No convenient API to trigger historical data backfill

### Working Components

- **DataBackfiller**: Correctly implements data fetching with retry logic
- **DataSourceManager**: Multi-source failover with circuit breaker and caching
- **daily-data-quality-check**: Uses DataBackfiller, logic is correct but depends on AkShare
- **Tencent Finance API**: Verified working (腾讯财经可用)

## Solution Architecture

### Approach: Minimal Changes (Recommended)

Reuse existing validated components, minimize risk:

1. Fix `daily-data-update` core logic to use DataBackfiller
2. Adjust data source priority in configuration
3. Add health check API for diagnostics
4. Add on-demand backfill API for manual intervention
5. Enhance logging for better observability

### Component Reuse

```
daily-data-update (scheduler)
  └─> _handle_data_update() [MODIFIED]
       └─> DataBackfiller.backfill_symbol()
            └─> DataSourceManager.get_klines()
                 └─> Try in order: tencent → sina → eastmoney → akshare → baostock
```

### Responsibility Division

| Task | Schedule | Purpose |
|------|----------|---------|
| `daily-data-update` | 15:30 weekdays | Incremental update: fetch today's closing data |
| `daily-data-quality-check` | 00:00 daily | Deep check: backfill historical gaps |

## Detailed Design

### 1. Core Logic Fix

**File**: `runtime/scheduler/scheduler.py`  
**Method**: `_handle_data_update()` (line 1008)

#### Current Implementation (Broken)

The `update_symbol()` inner function only checks if data exists in the database:

```python
def update_symbol(symbol: str) -> tuple[bool, bool]:
    try:
        latest = self.ds.kline.get_latest_daily_kline(symbol)
        return (bool(latest), False)  # Only checks DB
    except Exception as e:
        return (False, True)
```

#### New Implementation

Replace with logic that actually fetches data:

```python
def update_symbol(symbol: str) -> tuple[bool, bool, int]:
    try:
        from services.data_backfiller import DataBackfiller
        from datetime import datetime, timedelta
        
        # 1. Check latest data date
        latest = self.ds.kline.get_latest_daily_kline(symbol)
        
        # 2. Calculate date range
        today = datetime.now().strftime('%Y-%m-%d')
        if latest:
            latest_date = latest['trade_date'].strftime('%Y-%m-%d')
            start_date = (latest['trade_date'] + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # 3. Skip if up-to-date
        if latest and latest_date >= today:
            return (True, False, 0)
        
        # 4. Fetch using DataBackfiller
        backfiller = DataBackfiller()
        result = backfiller.backfill_symbol(
            symbol=symbol,
            missing_segments=[{'start': start_date, 'end': today, 'days': 0}],
            max_retries=2
        )
        
        return (result['success'], not result['success'], result['total_days_filled'])
        
    except Exception as e:
        logger.warning(f"Failed to update {symbol}: {e}")
        return (False, True, 0)
```

#### Return Value Enhancement

Update result aggregation to track records added:

```python
total_records = 0
for future in as_completed(futures):
    success, error, records = future.result()
    if success:
        updated += 1
        total_records += records
    if error:
        errors += 1

return {
    "action": "data_update",
    "symbols_checked": len(symbols),
    "symbols_updated": updated,
    "total_records_added": total_records,  # NEW
    "errors": errors,
    "market": market,
}
```

### 2. Data Source Priority Configuration

**File**: `data_sources/sources_config.yaml`

#### Changes Required

1. **Enable Tencent** (verified working):

```yaml
- name: tencent
  priority: 1  # Highest priority
  enabled: true  # Changed from false
  timeout: 5
  max_failures: 3
  circuit_timeout: 60
  description: "腾讯财经 - 首选数据源（已验证可用）"
```

2. **Adjust priorities**:

```yaml
- name: sina
  priority: 2
  
- name: eastmoney
  priority: 3
  
- name: akshare
  priority: 4  # Demoted due to network issues
  
- name: baostock
  priority: 5
```

3. **K-line specific override**:

```yaml
get_klines:
  sources: [tencent, sina, eastmoney, akshare, baostock]
  cache_ttl: 300
```

#### Rationale

- Tencent tested and working
- Sina and EastMoney as reliable backups
- AkShare kept as fallback (network issue may be temporary)
- Five-layer redundancy ensures high availability

### 3. Health Check API

**New File**: `api/routes/data_sources.py`

#### Endpoint

`GET /api/data-sources/health`

#### Purpose

Test connectivity of all configured data sources for diagnostics.

#### Implementation Sketch

```python
from flask import Blueprint, jsonify
from data_sources.manager import get_data_source_manager
from datetime import datetime
import time

data_sources_bp = Blueprint('data_sources', __name__)

@data_sources_bp.route('/api/data-sources/health', methods=['GET'])
def get_health():
    manager = get_data_source_manager()
    sources = manager.config['market_data']['sources']
    
    results = []
    for source_config in sources:
        if not source_config['enabled']:
            continue
            
        source_name = source_config['name']
        start = time.time()
        
        try:
            response = manager.get_stock_info('000001', source=source_name)
            elapsed_ms = int((time.time() - start) * 1000)
            
            if response.success:
                results.append({
                    'name': source_name,
                    'status': 'healthy',
                    'response_time_ms': elapsed_ms
                })
            else:
                results.append({
                    'name': source_name,
                    'status': 'unhealthy',
                    'error': response.error
                })
        except Exception as e:
            results.append({
                'name': source_name,
                'status': 'unhealthy',
                'error': str(e)
            })
    
    return jsonify({
        'success': True,
        'timestamp': datetime.now().isoformat(),
        'sources': results,
        'healthy_count': sum(1 for r in results if r['status'] == 'healthy'),
        'total_count': len(results)
    })
```

### 4. On-Demand Backfill API

**File**: `api/routes/stock.py` (add new route)

#### Endpoint

`POST /api/data/backfill`

#### Purpose

Allow manual triggering of historical data补充 for specific date ranges.

#### Implementation Sketch

```python
from services.data_quality_service import DataQualityService

@stock_bp.route('/api/data/backfill', methods=['POST'])
@handle_api_error
def backfill_data():
    data = request.get_json(silent=True) or {}
    
    symbols = data.get('symbols')  # None = hot stocks
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    mode = data.get('mode', 'auto')  # auto | force
    
    service = DataQualityService()
    result = service.backfill_missing_data(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        max_workers=8
    )
    
    return jsonify(result)
```

### 5. Monitoring and Logging Enhancements

#### 5.1 Scheduler Failure Logging

**File**: `runtime/scheduler/scheduler.py`, method `complete_run()`

Add detailed error logging for failed tasks:

```python
if not success:
    task = self.get_task(task_id)
    task_name = task.get('name', 'unknown') if task else 'unknown'
    
    logger.error(
        f"Scheduled task failed: {task_name}\n"
        f"  Task ID: {task_id}\n"
        f"  Run ID: {run_id}\n"
        f"  Error: {error}\n"
        f"  Result: {result}"
    )
    
    if 'data' in task_name and result:
        logger.error(
            f"Data update details:\n"
            f"  - Symbols checked: {result.get('symbols_checked', 0)}\n"
            f"  - Symbols updated: {result.get('symbols_updated', 0)}\n"
            f"  - Records added: {result.get('total_records_added', 0)}\n"
            f"  - Errors: {result.get('errors', 0)}"
        )
```

#### 5.2 DataBackfiller Failure Summary

**File**: `services/data_backfiller.py`, method `backfill_batch()`

Add failure summary after batch completes:

```python
if failed_count > 0:
    failed_symbols = [r['symbol'] for r in results if not r['success']]
    logger.warning(
        f"Backfill completed with failures:\n"
        f"  Total: {len(backfill_tasks)}\n"
        f"  Success: {success_count}\n"
        f"  Failed: {failed_count}\n"
        f"  Failed symbols: {', '.join(failed_symbols[:20])}"
    )
```

## Error Handling and Edge Cases

### Network Failures

- **All sources fail**: Task marked as partial success, failed stocks recorded for retry
- **Empty data**: Logged as warning (may indicate holiday), not counted as error
- **Circuit breaker opened**: Auto-recovery after 60s, logs show which sources unavailable

### Data Consistency

- **Duplicate writes**: UPSERT on `(trade_date, symbol)` prevents duplicates
- **Invalid data**: Add validation in `_convert_klines()` to filter bad records

### Edge Cases

- **Holidays**: Empty response expected, not an error
- **Intraday execution**: May get incomplete data if run before 15:30
- **New IPOs**: Fetch last 30 days when no history exists
- **Suspended stocks**: Already filtered out in code (line 1028)

### Performance

- **Concurrency**: 8 workers reasonable for ~5500 stocks
- **Database**: Batch UPSERT already optimized
- **Rate limiting**: Cache (300s TTL) + circuit breaker prevent excessive calls

## Implementation Plan

### Phase 1: Configuration
1. Modify `sources_config.yaml`
2. Restart service
3. Verify config loaded

### Phase 2: Core Logic
1. Modify `_handle_data_update()`
2. Add unit tests
3. Manual trigger test

### Phase 3: New APIs
1. Implement health check API
2. Implement backfill API
3. Register blueprints

### Phase 4: Monitoring
1. Enhance logging
2. Test with induced failures

### Phase 5: Documentation
1. Operations guide
2. Config comments
3. Code comments

## Testing Strategy

### Unit Tests

- Test `_handle_data_update()` calls DataBackfiller
- Test data validation filters invalid records

### Integration Tests

- Test health check API returns all sources
- Test backfill API triggers correctly

### E2E (Manual)

1. Delete 3 days of data for test stock
2. Trigger `daily-data-update`
3. Verify new records in database
4. Check logs show correct source used

## Rollback Strategy

If Phase 2 fails:
1. Git revert
2. Restart service
3. Rely on `daily-data-quality-check` temporarily

## Deployment Checklist

- [ ] Backup `sources_config.yaml`
- [ ] Apply config changes
- [ ] Restart service
- [ ] Verify health endpoint
- [ ] Deploy code changes
- [ ] Restart again
- [ ] Test health check API
- [ ] Manual trigger test
- [ ] Monitor next day's automated run

## Success Criteria

1. `daily-data-update` fetches data, not just checks
2. All stocks current to latest trading day
3. Failover works automatically
4. Health API shows source status
5. Manual backfill API functional
6. Failures clearly logged
7. Ops team can troubleshoot independently

## Future Enhancements (Out of Scope)

- Prometheus metrics
- Automated alerting (Feishu/email)
- Dynamic source priority based on performance
- Distributed task execution

## References

- DataBackfiller: `services/data_backfiller.py`
- DataSourceManager: `data_sources/manager.py`
- Scheduler: `runtime/scheduler/scheduler.py`
- Config: `data_sources/sources_config.yaml`
