"""Bind legacy DailyJobs handlers to the unified APScheduler JobRegistry.

This module is the inbound composition layer:
- schedule metadata for migration is derived from the existing ``JOBS`` catalog;
- handlers remain the original business functions (no business rewrite);
- legacy ops notifications are preserved through injected callbacks.

The legacy host thread is not started by the application anymore. APScheduler
owns time-based scheduling; this bridge only supplies the command handlers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from types import MappingProxyType
from typing import Any, Dict, List, Tuple

from qs_ops.application.jobs.function_job import FunctionJob

from adapters.inbound.fastapi_app.daily_jobs.alerting import _send_feishu, _summarize_result
from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS

# Allow six hours of lateness so a short service restart at the scheduled time
# still triggers the job, matching the old host's same-day catch-up behaviour.
DEFAULT_MISFIRE_GRACE_SECONDS = 6 * 60 * 60

DOMAINS = MappingProxyType({
    "watch_rule_health": "monitor",
    "v2_daily_cycle_reset": "monitor",
    "invalid_rule_escalation": "monitor",
    "event_calendar_check": "analysis",
    "freshness_guard": "data",
    "evening_pipeline": "data",
    "chip_distribution": "data",
    "evolution_fitness": "analysis",
    "financial_statements": "data",
    "pool_daily_refresh": "data",
    "pool_weekly_review": "data",
})

TIMEOUT_SECONDS = MappingProxyType({
    "evening_pipeline": 3 * 60 * 60,
    "financial_statements": 2 * 60 * 60,
    "pool_daily_refresh": 2 * 60 * 60,
    "pool_weekly_review": 2 * 60 * 60,
})


@dataclass(frozen=True)
class DailyTaskSpec:
    """Canonical scheduler_tasks row for a migrated legacy job."""

    job_id: str
    cron_expression: str
    description: str
    domain: str
    timeout_seconds: int
    task_type: str = "cron"
    params: Dict[str, Any] = field(default_factory=dict)
    misfire_grace_time_seconds: int = DEFAULT_MISFIRE_GRACE_SECONDS


def _cron_dow(weekdays: Tuple[int, ...]) -> str:
    """Convert Python weekdays (Mon=0..Sun=6) to standard cron day-of-week."""
    py_to_cron = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}
    cron_days = sorted({py_to_cron[d] for d in weekdays})
    if len(cron_days) == 7:
        return "*"

    ranges: List[str] = []
    start = previous = cron_days[0]
    for day in cron_days[1:]:
        if day == previous + 1:
            previous = day
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = day
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def _build_daily_specs() -> Tuple[DailyTaskSpec, ...]:
    specs: List[DailyTaskSpec] = []
    for job in JOBS:
        specs.append(
            DailyTaskSpec(
                job_id=job.job_id,
                cron_expression=(
                    f"{job.run_at.minute} {job.run_at.hour} * * {_cron_dow(job.weekdays)}"
                ),
                description=job.description,
                domain=DOMAINS[job.job_id],
                timeout_seconds=TIMEOUT_SECONDS.get(job.job_id, 3600),
            )
        )
    return tuple(specs)


DAILY_TASK_SPECS = _build_daily_specs()


def _notify_start(job_id: str, description: str) -> None:
    from datetime import datetime

    _send_feishu(
        f"▶️ 每日任务开始：{job_id}\n{description}\n"
        f"时间: {datetime.now().strftime('%H:%M')}"
    )


def _notify_success(job_id: str, description: str, result: Any, elapsed: float) -> None:
    summary = _summarize_result(result)
    _send_feishu(
        f"✅ 每日任务完成：{job_id}\n{description}\n"
        f"耗时: {elapsed / 60:.1f} 分钟" + (f"\n{summary}" if summary else "")
    )


def _notify_failure(job_id: str, description: str, error: str, _result: Any, _elapsed: float) -> None:
    _send_feishu(
        f"🚨 每日任务失败：{job_id}\n{description}\n错误: {error[:300]}"
    )


def build_daily_jobs() -> List[FunctionJob]:
    """Build one FunctionJob per legacy daily job (no scheduling side effect)."""
    by_id = {spec.job_id: spec for spec in DAILY_TASK_SPECS}
    jobs: List[FunctionJob] = []
    for job in JOBS:
        spec = by_id[job.job_id]
        jobs.append(
            FunctionJob(
                name=job.job_id,
                description=job.description,
                handler=job.handler,
                timeout_seconds=spec.timeout_seconds,
                on_start=partial(_notify_start, job.job_id, job.description),
                on_success=partial(_notify_success, job.job_id, job.description),
                on_failure=partial(_notify_failure, job.job_id, job.description),
            )
        )
    return jobs


__all__ = [
    "DAILY_TASK_SPECS",
    "DailyTaskSpec",
    "build_daily_jobs",
]
