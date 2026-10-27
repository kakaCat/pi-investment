"""Read/trigger adapter exposing migrated DailyJobs through scheduler_tasks.

The public compatibility API remains ``/api/jobs/inprocess/...`` for existing
dashboards and scripts, but its source of truth is now APScheduler's
``scheduler_tasks`` / ``scheduler_runs`` tables.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from adapters.inbound.fastapi_app.daily_jobs.apscheduler_bridge import DAILY_TASK_SPECS

DAILY_JOB_IDS = tuple(spec.job_id for spec in DAILY_TASK_SPECS)
_ORDER = {job_id: index for index, job_id in enumerate(DAILY_JOB_IDS)}


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _schedule_fields(cron_expression: str) -> Dict[str, Any]:
    """Convert the simple 5-field specs to the legacy scheduled_at/weekdays shape."""
    from infrastructure.scheduler.scheduler import parse_cron

    schedule = parse_cron(cron_expression)
    minute = min(schedule.minute)
    hour = min(schedule.hour)
    py_to_cron = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}
    cron_to_py = {cron: py for py, cron in py_to_cron.items()}
    cron_days = {0 if day == 7 else day for day in schedule.dow}
    weekdays = sorted(cron_to_py[day] for day in cron_days if day in cron_to_py)
    return {
        "scheduled_at": f"{hour:02d}:{minute:02d}",
        "weekdays": weekdays,
    }


def _is_soft_deleted(task: Dict[str, Any]) -> bool:
    params = task.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except (TypeError, json.JSONDecodeError):
            params = {}
    return bool(isinstance(params, dict) and params.get("_deleted_at"))


def _session():
    from qs_kernel.infrastructure.persistence.orm import get_session

    return get_session()


def list_daily_status(run_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return today's status for migrated jobs from scheduler tables."""
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
    from qs_kernel.infrastructure.persistence.orm import close_session

    day = run_date or datetime.now().strftime("%Y-%m-%d")
    session = _session()
    try:
        repo = SchedulerRepository(session)
        legacy_runs = JobRunRepository().map_by_date(day)
        tasks = [
            task for task in repo.list_tasks()
            if task.get("command") in _ORDER
            and not _is_soft_deleted(task)
        ]
        if len(tasks) != len(DAILY_JOB_IDS):
            raise RuntimeError(
                "DailyJobs 迁移不完整："
                f"scheduler_tasks 只有 {len(tasks)}/{len(DAILY_JOB_IDS)} 条，"
                "请先执行 20261027_dailyjobs_to_apscheduler.py --apply"
            )
        tasks.sort(key=lambda task: _ORDER.get(task.get("command"), 9999))
        rows: List[Dict[str, Any]] = []
        for task in tasks:
            job_id = task.get("command")
            runs = repo.list_runs(task_id=task.get("id"), limit=1, date_filter=day)
            latest = runs[0] if runs else None
            legacy = None if latest else legacy_runs.get(job_id)
            schedule = _schedule_fields(task.get("cron_expression") or "")
            rows.append({
                "job_id": job_id,
                "task_id": task.get("id"),
                "description": task.get("description"),
                **schedule,
                "status": (latest.get("status") if latest
                           else legacy.get("status") if legacy else "not_run"),
                "started_at": (_iso(latest.get("started_at")) if latest
                               else legacy.get("started_at") if legacy else None),
                "finished_at": (_iso(latest.get("completed_at")) if latest
                                else legacy.get("finished_at") if legacy else None),
                "error": (latest.get("error") if latest
                          else legacy.get("error") if legacy else None),
                "source": "apscheduler" if latest else "inprocess_legacy" if legacy else None,
                "backend": "apscheduler",
            })
        return rows
    finally:
        close_session()


def get_daily_schedule() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for spec in DAILY_TASK_SPECS:
        schedule = _schedule_fields(spec.cron_expression)
        rows.append({
            "job_id": spec.job_id,
            **schedule,
            "description": spec.description,
            "domain": spec.domain,
            "task_type": spec.task_type,
        })
    return rows


def trigger_daily_job(job_id: str, scheduler_service) -> Dict[str, Any]:
    """Trigger a migrated daily job through APScheduler (manual/backfill path)."""
    from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
    from qs_kernel.infrastructure.persistence.orm import close_session

    if scheduler_service is None:
        return {"success": False, "error": "APScheduler 未启动，无法触发"}
    session = _session()
    try:
        repo = SchedulerRepository(session)
        task = repo.get_task_by_name(job_id)
        if task is None:
            matches = [t for t in repo.list_tasks() if t.get("command") == job_id]
            task = matches[0] if matches else None
        if task is None or task.get("command") not in _ORDER:
            return {
                "success": False,
                "error": f"未知任务: {job_id}",
                "available": list(DAILY_JOB_IDS),
            }
        if not task.get("is_enabled"):
            return {"success": False, "error": f"任务已停用: {job_id}"}

        task_id = int(task["id"])
        status = scheduler_service.get_job_status(task_id)
        if not status.get("exists"):
            scheduler_service.reload_tasks()
            status = scheduler_service.get_job_status(task_id)
        if not status.get("exists"):
            return {"success": False, "error": f"任务未加载到 APScheduler: {job_id}"}

        scheduler_service.trigger_task_now(task_id)
        return {
            "success": True,
            "message": f"{job_id} 已触发（APScheduler 后台运行）",
        }
    finally:
        close_session()
