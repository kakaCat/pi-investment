"""Unified Scheduler Admin API — YAML-config-driven task management.

Provides CRUD + trigger + status endpoints for the declarative scheduler.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response,
    error_response,
    handle_api_error,
)
from infrastructure.scheduler.unified_scheduler import (
    UnifiedScheduler,
    get_scheduler,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["UnifiedScheduler - 统一调度器"])

_scheduler: Optional[UnifiedScheduler] = None


def _get_scheduler() -> UnifiedScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = get_scheduler()
    return _scheduler


# ============ Jobs CRUD ============


@router.get("/api/unified-scheduler/jobs")
@handle_api_error
def list_jobs():
    """List all registered jobs with status."""
    scheduler = _get_scheduler()
    jobs = scheduler.list_jobs()
    return api_response({"success": True, "jobs": jobs, "count": len(jobs)})


@router.get("/api/unified-scheduler/jobs/{job_id}")
@handle_api_error
def get_job(job_id: str):
    """Get a single job by ID."""
    scheduler = _get_scheduler()
    job = scheduler.jobs.get(job_id)
    if job is None:
        return error_response({"success": False, "error": f"Job not found: {job_id}"}, 404)
    status = scheduler.get_job_status(job_id)
    return api_response({
        "success": True,
        "job": {
            "id": job.id,
            "name": job.name,
            "enabled": job.enabled,
            "status": status,
            "schedule": job.schedule,
            "executor": job.executor,
            "timeout": job.timeout,
            "retry": {"max_attempts": job.retry.max_attempts, "backoff": job.retry.backoff} if job.retry else None,
            "dependencies": job.dependencies or [],
            "alerts": {"on_failure": job.alerts.on_failure, "channels": job.alerts.channels} if job.alerts else None,
        },
    })


@router.post("/api/unified-scheduler/jobs/{job_id}/trigger")
@handle_api_error
def trigger_job(job_id: str):
    """Manually trigger a job."""
    scheduler = _get_scheduler()
    result = scheduler.run_job(job_id)
    return api_response({
        "success": result.status == "success",
        "result": {
            "job_id": result.job_id,
            "status": result.status,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "finished_at": result.finished_at.isoformat() if result.finished_at else None,
            "result": result.result,
            "error": result.error,
        },
    })


# ============ History ============


@router.get("/api/unified-scheduler/history")
@handle_api_error
def list_history(
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    limit: int = Query(20, ge=1, le=100),
):
    """List recent run history."""
    scheduler = _get_scheduler()
    history = scheduler.get_history(job_id=job_id, limit=limit)
    return api_response({"success": True, "history": history, "count": len(history)})


# ============ Config ============


@router.post("/api/unified-scheduler/reload")
@handle_api_error
def reload_config():
    """Reload YAML configuration."""
    scheduler = _get_scheduler()
    scheduler.reload_config()
    return api_response({
        "success": True,
        "message": f"Reloaded {len(scheduler.jobs)} jobs from config",
    })


# ============ Health ============


@router.get("/api/unified-scheduler/health")
@handle_api_error
def health_check():
    """Scheduler health check."""
    scheduler = _get_scheduler()
    running = scheduler.is_running
    jobs_count = len(scheduler.jobs)
    enabled_count = sum(1 for j in scheduler.jobs.values() if j.enabled)
    return api_response({
        "success": True,
        "running": running,
        "jobs_total": jobs_count,
        "jobs_enabled": enabled_count,
    })
