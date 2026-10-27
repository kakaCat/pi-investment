"""Compatibility API for migrated DailyJobs.

Source of truth is now quant.scheduler_tasks / quant.scheduler_runs. The route
names stay unchanged so existing dashboards and scripts keep working.

- GET  /api/jobs/inprocess/status
- POST /api/jobs/inprocess/{job_id}/run
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Daily Jobs - 已迁移至 APScheduler"])


@router.get('/api/jobs/inprocess/status')
def daily_jobs_status():
    from adapters.inbound.fastapi_app.daily_jobs.status import (
        get_daily_schedule,
        list_daily_status,
    )

    return {
        'success': True,
        'data': {
            'backend': 'apscheduler',
            'jobs': list_daily_status(),
            'schedule': get_daily_schedule(),
        },
    }


@router.post('/api/jobs/inprocess/{job_id}/run')
def daily_jobs_run(
    job_id: str,
    request: Request,
    payload: Optional[Dict[str, Any]] = Body(None),
):
    from adapters.inbound.fastapi_app.daily_jobs.status import trigger_daily_job

    scheduler_service = getattr(request.app.state, 'scheduler_service', None)
    result = trigger_daily_job(job_id, scheduler_service)
    if not result.get('success'):
        return JSONResponse(status_code=400, content=result)
    result['force_ignored'] = bool((payload or {}).get('force', False))
    return result
