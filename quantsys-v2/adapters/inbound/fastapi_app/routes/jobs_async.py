"""任务（Job）API - FastAPI 版（从 Flask jobs.py 迁移，响应契约保持一致）

jobs 存储在 health.py 的模块级内存字典中（_jobs/_jobs_lock），Flask 与 FastAPI
共享同一内存状态（与 Flask 行为一致）。
"""
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    error_response, sanitize_for_json, convert_keys_to_snake,
)

# 从 health.py 导入共享的 Job 基础设施（与 Flask jobs.py 一致）
from adapters.inbound.api.routes.health import (
    _jobs, _jobs_lock, _audit_job, _execute_job_by_type, _JOB_TYPES,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Jobs - 任务"])


@router.get('/api/jobs')
def list_jobs(page: int = Query(1), pageSize: int = Query(20)):
    with _jobs_lock:
        jobs = list(_jobs.values())
        jobs.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        total = len(jobs)
        start = (page - 1) * pageSize
        end = start + pageSize
        jobs = jobs[start:end]
    return sanitize_for_json({'success': True, 'jobs': jobs, 'count': total})


@router.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return error_response({'success': False, 'error': f'Job not found: {job_id}'}, 404)
    return {'success': True, 'data': sanitize_for_json(job)}


@router.post('/api/jobs/{job_type}/run')
def run_job_by_type(job_type: str, payload: Optional[Dict[str, Any]] = Body(None)):
    if job_type not in _JOB_TYPES:
        return error_response({
            'success': False,
            'error': f'Unsupported job type: {job_type}. Must be one of: {", ".join(sorted(_JOB_TYPES))}'
        }, 400)

    params = convert_keys_to_snake(payload or {})

    with _jobs_lock:
        for j in _jobs.values():
            if j.get('type') == job_type and j.get('status') in ('pending', 'running', 'queued'):
                return error_response({'success': False, 'error': f'Active job already exists for type: {job_type}'}, 409)

    job_id = str(uuid.uuid4())
    job = {
        'id': job_id, 'type': job_type, 'params': params,
        'status': 'queued', 'createdAt': datetime.now().isoformat(),
    }
    with _jobs_lock:
        _jobs[job_id] = job
    _audit_job('run', job)

    def _run_job():
        try:
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'running'
            result = _execute_job_by_type(job_type, params)
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'completed'
                    _jobs[job_id]['result'] = result
                    _jobs[job_id]['completedAt'] = datetime.now().isoformat()
        except Exception as e:
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'failed'
                    _jobs[job_id]['error'] = str(e)
                    _jobs[job_id]['completedAt'] = datetime.now().isoformat()

    threading.Thread(target=_run_job, daemon=True).start()
    _audit_job('run', job)
    return error_response({'success': True, 'data': sanitize_for_json(job)}, 202)


@router.post('/api/jobs/{job_id}/retry')
def retry_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return error_response({'success': False, 'error': f'Job not found: {job_id}'}, 404)
    if job['status'] not in ('failed', 'cancelled'):
        return error_response({
            'success': False,
            'error': f'Only failed or cancelled jobs can be retried. Current status: {job["status"]}'
        }, 400)

    job_type = job.get('type', 'data_update')
    params = job.get('params', None)
    if not params:
        params = {'source': job.get('source', 'watchlist'), 'days': job.get('days', 730), 'force': job.get('force', False)}

    new_job_id = str(uuid.uuid4())
    new_job = {
        'id': new_job_id, 'type': job_type, 'params': params,
        'status': 'queued', 'createdAt': datetime.now().isoformat(), 'retryOf': job_id,
    }
    with _jobs_lock:
        _jobs[new_job_id] = new_job
    _audit_job('retry', new_job)

    def _retry():
        try:
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'running'
            result = _execute_job_by_type(job_type, params)
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'completed'
                    _jobs[new_job_id]['result'] = result
                    _jobs[new_job_id]['completedAt'] = datetime.now().isoformat()
        except Exception as e:
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'failed'
                    _jobs[new_job_id]['error'] = str(e)
                    _jobs[new_job_id]['completedAt'] = datetime.now().isoformat()

    threading.Thread(target=_retry, daemon=True).start()
    return {'success': True, 'job_id': new_job_id, 'message': f'Job retried: {new_job_id}'}


@router.post('/api/jobs/{job_id}/cancel')
def cancel_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return error_response({'success': False, 'error': f'Job not found: {job_id}'}, 404)
    if job['status'] not in ('pending', 'running', 'queued'):
        return error_response({
            'success': False,
            'error': f'Only pending or running jobs can be cancelled. Current status: {job["status"]}'
        }, 400)
    with _jobs_lock:
        _jobs[job_id]['status'] = 'cancelled'
        _jobs[job_id]['cancelledAt'] = datetime.now().isoformat()
    _audit_job('cancel', job)
    return {'success': True, 'message': f'Job cancelled: {job_id}'}
