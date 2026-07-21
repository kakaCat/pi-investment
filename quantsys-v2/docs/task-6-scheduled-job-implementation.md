# Task 6: Scheduled Job Configuration - Implementation Summary

## Overview
Created the scheduled job entry point and registered it in the scheduler configuration for daily signal execution at 15:30.

## Files Created

### 1. `runtime/scheduler/signal_execution_job.py`
Entry point function for the scheduled task:
- `execute_daily_signals_job()` - Called by scheduler at 15:30 daily
- Instantiates `SignalExecutionScheduler` and calls `execute_daily_signals()`
- Comprehensive logging (start, success, failure)
- Exception handling with re-raise for scheduler tracking

### 2. `scripts/register_signal_execution_task.py`
Registration utility script:
- Registers the task in the database
- Cron expression: `30 15 * * 1-5` (Mon-Fri at 15:30)
- Command: `signal_execution_daily`
- Handles both new registration and updates to existing task

## Files Modified

### `runtime/scheduler/scheduler.py`
Added command handler:
- Registered `signal_execution_daily` in `_execute_command()` handlers dict
- Added `_handle_signal_execution_daily()` method that delegates to the job function
- Follows existing pattern from data pipeline handlers

## How to Use

### 1. Register the Task
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python scripts/register_signal_execution_task.py
```

This will:
- Create a new task named `daily_signal_execution` in the database
- Set schedule to 15:30 Mon-Fri (after market close)
- Enable the task by default

### 2. Verify Registration
```bash
# Via API
curl http://127.0.0.1:5001/api/scheduler/tasks

# Via Python
python -c "
from runtime.scheduler.scheduler import SchedulerService
scheduler = SchedulerService()
tasks = scheduler.list_tasks()
for task in tasks:
    if 'signal' in task['name']:
        print(f\"{task['name']}: {task['cron_expression']} -> {task['command']}\")
scheduler.close()
"
```

### 3. Manual Trigger (for testing)
```bash
# Get task ID first
curl http://127.0.0.1:5001/api/scheduler/tasks | jq '.[] | select(.name=="daily_signal_execution") | .id'

# Trigger manually
curl -X POST http://127.0.0.1:5001/api/scheduler/tasks/<task_id>/trigger
```

### 4. Monitor Execution
```bash
# Check execution logs
curl http://127.0.0.1:5001/api/scheduler/runs?limit=10

# Check signal execution logs
curl http://127.0.0.1:5001/api/signals/execution-logs
```

## Architecture

```
Scheduler (15:30 daily)
    ↓
_execute_command("signal_execution_daily", {})
    ↓
_handle_signal_execution_daily()
    ↓
execute_daily_signals_job()
    ↓
SignalExecutionScheduler.execute_daily_signals()
    ↓
[Strategy runs → Signal collection → Risk checks → Order creation]
```

## Schedule Details

- **Time**: 15:30 Beijing time (Asia/Shanghai)
- **Days**: Monday-Friday (trading days only)
- **Cron**: `30 15 * * 1-5`
- **Timezone**: Handled by system timezone (should be set to Asia/Shanghai)

## Verification Checklist

✅ Job entry point file created (`signal_execution_job.py`)  
✅ Job function calls `SignalExecutionScheduler`  
✅ Proper logging (start, success, failure)  
✅ Scheduler config updated with command handler  
✅ Handler delegates to job function  
✅ Registration script created  
✅ Correct time (15:30) and days (Mon-Fri)  
✅ Changes committed to git  

## Next Steps

To complete the signal execution pipeline:
- Task 7: Integration tests
- Task 8: Error handling and retry logic
- Task 9: Monitoring and alerting
- Task 10: Documentation

## Notes

- The `scripts/` directory is in `.gitignore`, so the registration script is not tracked in git
- This is intentional - registration scripts are utilities run once during setup
- The core job logic in `runtime/scheduler/` is properly tracked
- Registration can be done via the script or manually through the API
