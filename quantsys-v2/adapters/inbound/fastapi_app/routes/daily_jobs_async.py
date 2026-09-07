"""进程内每日任务管理 API（2026-09-02）

- GET  /api/jobs/inprocess/status        今日各任务运行状态（巡检用）
- POST /api/jobs/inprocess/{job_id}/run  手动触发（force=true 忽略当日已有记录）
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Daily Jobs - 进程内每日任务"])


@router.get('/api/jobs/inprocess/status')
def daily_jobs_status():
    from adapters.inbound.fastapi_app.daily_jobs_bootstrap import list_today_runs, JOBS
    return {
        'success': True,
        'data': {
            'jobs': list_today_runs(),
            'schedule': [
                {'job_id': j.job_id, 'scheduled_at': j.run_at.strftime('%H:%M'),
                 'weekdays': list(j.weekdays), 'description': j.description}
                for j in JOBS
            ],
        },
    }


@router.post('/api/jobs/inprocess/{job_id}/run')
def daily_jobs_run(job_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    from adapters.inbound.fastapi_app.daily_jobs_bootstrap import trigger_job
    force = bool((payload or {}).get('force', False))
    result = trigger_job(job_id, force=force)
    if not result.get('success'):
        return JSONResponse(status_code=400, content=result)
    return result
