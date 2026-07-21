# Scheduled Tasks for Data Pipeline

## Overview

This implementation adds two scheduled tasks to automatically run the quantsys-v2 data pipeline:

1. **daily_data_pipeline** - Daily incremental update at 16:30 (Mon-Fri, after market close)
2. **weekly_full_rebuild** - Full rebuild every Sunday at 2:00 AM

## Files Created

### 1. `runtime/scheduler/scheduled_tasks.py`
Contains the task implementations:
- `get_csi300_components()` - Fetches CSI 300 (沪深300) index components
- `daily_data_pipeline()` - Daily incremental update task
- `weekly_full_rebuild()` - Weekly full rebuild task

### 2. `scripts/register_pipeline_tasks.py`
Script to register the tasks with the scheduler database.

### 3. `scripts/test_pipeline_tasks.py`
Manual test script to run tasks without the scheduler.

### 4. `scripts/verify_pipeline_tasks.py`
Verification script to check integration is correct.

## Files Modified

### `runtime/scheduler/scheduler.py`
Added two new command handlers:
- `data_pipeline_daily` → `_handle_data_pipeline_daily()`
- `data_pipeline_weekly` → `_handle_data_pipeline_weekly()`

## Task Specifications

### Daily Data Pipeline

- **Schedule**: `30 16 * * 1-5` (16:30 Mon-Fri)
- **Command**: `data_pipeline_daily`
- **Action**: Incremental update for current trading day
- **Symbols**: CSI 300 components (~300 stocks)
- **Rationale**: Runs after A-share market close (15:00) with 1.5 hour buffer

### Weekly Full Rebuild

- **Schedule**: `0 2 * * 0` (02:00 Sunday)
- **Command**: `data_pipeline_weekly`
- **Action**: Full rebuild for last 90 days
- **Symbols**: CSI 300 components (~300 stocks)
- **Rationale**: Runs during off-market hours to avoid interference

## Usage

### 1. Register Tasks

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python scripts/register_pipeline_tasks.py
```

This will:
- Create task definitions in `quant.scheduler_tasks` table
- Set up cron schedules
- Enable tasks for automatic execution

### 2. Start Scheduler

```bash
python -m runtime.scheduler.scheduler
```

Or use the scheduler service in production.

### 3. Manual Testing

Test tasks without registering them:

```bash
# Test daily task
python scripts/test_pipeline_tasks.py daily

# Test weekly task
python scripts/test_pipeline_tasks.py weekly

# Test both
python scripts/test_pipeline_tasks.py
```

### 4. Verify Integration

```bash
python scripts/verify_pipeline_tasks.py
```

## Task Behavior

### Error Handling

Both tasks include comprehensive error handling:
- Catch exceptions and return error status
- Log errors with full stack traces
- Return structured result dictionaries
- Never crash the scheduler

### Return Format

Both tasks return a dictionary with:
```python
{
    "action": "daily_data_pipeline" | "weekly_full_rebuild",
    "status": "success" | "failed" | "error" | "skipped",
    "date": "YYYY-MM-DD",  # daily only
    "start_date": "YYYY-MM-DD",  # weekly only
    "end_date": "YYYY-MM-DD",  # weekly only
    "symbols_count": 300,
    "metadata": {...},  # Pipeline metadata
    "errors": [...],  # If failed
    "timestamp": "ISO-8601 timestamp"
}
```

### Graceful Degradation

If CSI 300 components cannot be fetched:
- Task returns `status: "skipped"`
- Logs warning but doesn't crash
- Scheduler continues running

## Database Tables

Tasks use existing scheduler tables:
- `quant.scheduler_tasks` - Task definitions
- `quant.scheduler_runs` - Execution history

## Monitoring

Task execution is logged to:
- Scheduler service logs
- Task-specific logs in `runtime.scheduler.scheduled_tasks`
- Database run records with status and duration

## Testing Results

Verification script confirms:
- ✓ All imports successful
- ✓ Command handlers registered
- ✓ Task functions callable
- ✓ CSI 300 components fetched (300 symbols)

## Notes

- Tasks use the existing `DataPipelineService` orchestration
- Pipeline failures are captured and logged, not propagated
- Tasks are idempotent - safe to run multiple times
- Scheduler checks for due tasks every 30 seconds
- Tasks only run when enabled in database

## Future Enhancements

Possible improvements:
1. Add task parameters for custom symbol lists
2. Add notification on task failure
3. Add metrics collection for monitoring
4. Add task retry logic with exponential backoff
5. Add task timeout configuration
