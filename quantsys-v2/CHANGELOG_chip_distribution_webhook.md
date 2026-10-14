# Chip Distribution Task Webhook Configuration

## Summary
Modified the `chip_distribution` daily job to send completion notifications to a specific Feishu webhook instead of the default notification channel.

## Changes Made

### 1. Updated `JobDef` dataclass to support custom webhooks
**File**: `adapters/inbound/fastapi_app/daily_jobs/defs.py`
- Added `webhook_url: Optional[str] = None` field to `JobDef` class
- This allows each job to specify its own notification webhook

### 2. Enhanced `_send_feishu` to support custom webhooks
**File**: `adapters/inbound/fastapi_app/daily_jobs/alerting.py`
- Added `webhook_url: Optional[str] = None` parameter to `_send_feishu` function
- When `webhook_url` is provided, sends directly to that webhook (bypassing NotificationFacade)
- Maintains backward compatibility - uses default channel when `webhook_url` is None

### 3. Updated runtime to pass webhook_url from jobs
**File**: `adapters/inbound/fastapi_app/daily_jobs/runtime.py`
- Modified all 4 `_send_feishu` calls in `_run_job` to pass `job.webhook_url`
- Updated `_send_running_notice` to accept and use `webhook_url` parameter
- Updated `_arm_running_notice` to pass `job.webhook_url` to the timer callback

### 4. Configured chip_distribution job with specific webhook
**File**: `adapters/inbound/fastapi_app/daily_jobs/registry.py`
- Added `webhook_url='https://open.feishu.cn/open-apis/bot/v2/hook/7aa7ebdd-be9e-47f9-be45-ba9c772499c9'` to chip_distribution JobDef

## Webhook Details
- **Webhook ID**: 7aa7ebdd-be9e-47f9-be45-ba9c772499c9
- **Full URL**: https://open.feishu.cn/open-apis/bot/v2/hook/7aa7ebdd-be9e-47f9-be45-ba9c772499c9
- **Target Job**: chip_distribution
- **Job Schedule**: 21:10 weekdays (0-4), trading days only

## Notification Types Affected
All chip_distribution notifications will now go to the custom webhook:
1. ✅ Job completion messages (success)
2. 🚨 Job failure messages
3. ⏳ Long-running job warnings
4. ▶️ Job start messages (if enabled)

## Backward Compatibility
- All existing jobs without `webhook_url` specified continue to use the default notification channel
- No changes required for other jobs
- The change is fully isolated to the chip_distribution job

## Testing
Syntax validation passed for all modified files:
- `adapters/inbound/fastapi_app/daily_jobs/defs.py`
- `adapters/inbound/fastapi_app/daily_jobs/alerting.py`
- `adapters/inbound/fastapi_app/daily_jobs/runtime.py`
- `adapters/inbound/fastapi_app/daily_jobs/registry.py`

## Deployment
No environment variable changes needed. The webhook URL is hardcoded in the job definition.
The service will need to be restarted to pick up the changes:
```bash
launchctl kickstart -k gui/501/com.pi-investment.v2-api
```

## Future Improvements
To make other jobs use custom webhooks, simply add the `webhook_url` parameter when defining the job in `registry.py`:
```python
JobDef('job_name', dtime(hour, minute), (weekdays),
       handler_function, 'Description',
       webhook_url='https://open.feishu.cn/open-apis/bot/v2/hook/YOUR-WEBHOOK-ID')
```
