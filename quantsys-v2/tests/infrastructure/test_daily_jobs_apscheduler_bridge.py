"""Regression tests for the DailyJobs -> APScheduler bridge."""
import asyncio

import pytest

from qs_ops.application.jobs.function_job import FunctionJob
from qs_ops.application.jobs.job_registry import JobRegistry

from adapters.inbound.fastapi_app.daily_jobs.apscheduler_bridge import (
    DAILY_TASK_SPECS,
    build_daily_jobs,
)
from adapters.inbound.fastapi_app.daily_jobs import status as status_module
from adapters.inbound.fastapi_app.daily_jobs.status import _schedule_fields
from adapters.inbound.fastapi_app.daily_jobs.runtime import (
    start_daily_jobs,
    start_watch_interval_engine,
)


EXPECTED_CRON = {
    "watch_rule_health": "30 16 * * 1-5",
    "v2_daily_cycle_reset": "35 16 * * 1-5",
    "invalid_rule_escalation": "0 17 * * 1-5",
    "event_calendar_check": "45 16 * * *",
    "freshness_guard": "20 17 * * 1-5",
    "evening_pipeline": "30 20 * * 1-5",
    "chip_distribution": "10 21 * * 1-5",
    "evolution_fitness": "35 20 * * 1-5",
    "financial_statements": "0 20 * * 6",
    "pool_daily_refresh": "5 19 * * 1-5",
    "pool_weekly_review": "0 18 * * 0",
}


def test_bridge_covers_all_legacy_daily_jobs_with_exact_cron():
    specs = {spec.job_id: spec for spec in DAILY_TASK_SPECS}

    assert len(specs) == 11
    assert set(specs) == set(EXPECTED_CRON)
    for job_id, cron in EXPECTED_CRON.items():
        assert specs[job_id].cron_expression == cron
        assert specs[job_id].domain
        assert specs[job_id].misfire_grace_time_seconds == 6 * 60 * 60

    jobs = build_daily_jobs()
    assert [job.name for job in jobs] == [
        spec.job_id for spec in DAILY_TASK_SPECS
    ]


def test_bridge_registers_unique_commands_without_registry_collision():
    registry = JobRegistry()
    for job in build_daily_jobs():
        registry.register(job)

    assert set(registry.list_jobs()) == set(EXPECTED_CRON)


def test_function_job_success_keeps_handler_details_and_callbacks():
    calls = []
    job = FunctionJob(
        name="unit_success",
        description="unit",
        handler=lambda: {"status": "success", "updated": 7},
        on_start=lambda: calls.append("start"),
        on_success=lambda result, elapsed: calls.append(("success", result["updated"])),
        on_failure=lambda error, result, elapsed: calls.append(("failure", error)),
    )

    result = asyncio.run(job.execute({}))

    assert result.success is True
    assert result.details == {"status": "success", "updated": 7}
    assert calls == ["start", ("success", 7)]


def test_function_job_nested_failure_is_not_silent_success():
    calls = []
    job = FunctionJob(
        name="unit_nested_failure",
        description="unit",
        handler=lambda: {
            "status": "success",
            "kline_sync": {"status": "error", "error": "kline failed"},
        },
        on_success=lambda result, elapsed: calls.append("success"),
        on_failure=lambda error, result, elapsed: calls.append(error),
    )

    result = asyncio.run(job.execute({}))

    assert result.success is False
    assert "kline_sync" in result.error
    assert "kline failed" in result.error
    assert calls and "kline_sync" in calls[0]
    assert "success" not in calls


def test_function_job_exception_is_failed_and_notifies_once():
    calls = []
    job = FunctionJob(
        name="unit_exception",
        description="unit",
        handler=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        on_success=lambda result, elapsed: calls.append("success"),
        on_failure=lambda error, result, elapsed: calls.append(error),
    )

    result = asyncio.run(job.execute({}))

    assert result.success is False
    assert "RuntimeError: boom" == result.error
    assert calls == ["RuntimeError: boom"]


def test_notification_callback_error_does_not_fail_the_job():
    def broken_start():
        raise RuntimeError("notification unavailable")

    job = FunctionJob(
        name="unit_notification_failure",
        description="unit",
        handler=lambda: {"status": "success"},
        on_start=broken_start,
    )

    result = asyncio.run(job.execute({}))

    assert result.success is True
    assert result.details == {"status": "success"}


def test_status_schedule_fields_preserve_legacy_shape():
    assert _schedule_fields("30 16 * * 1-5") == {
        "scheduled_at": "16:30",
        "weekdays": [0, 1, 2, 3, 4],
    }
    assert _schedule_fields("0 20 * * 6") == {
        "scheduled_at": "20:00",
        "weekdays": [5],
    }
    assert _schedule_fields("0 18 * * 0") == {
        "scheduled_at": "18:00",
        "weekdays": [6],
    }


def test_legacy_daily_host_cannot_be_started_again():
    with pytest.raises(RuntimeError, match="retired"):
        start_daily_jobs()
    assert start_daily_jobs(skip=True) is None
    assert start_watch_interval_engine(skip=True) is None


class _FakeTaskRepo:
    task = {
        "id": 901,
        "name": "evening_pipeline",
        "command": "evening_pipeline",
        "is_enabled": True,
    }

    def __init__(self, _session):
        pass

    def get_task_by_name(self, name):
        return dict(self.task) if self.task["name"] == name else None

    def list_tasks(self):
        return [dict(self.task)]


class _FakeScheduler:
    def __init__(self):
        self.triggered = []

    def get_job_status(self, task_id):
        return {"exists": task_id == 901}

    def reload_tasks(self):
        return None

    def trigger_task_now(self, task_id):
        self.triggered.append(task_id)


def test_trigger_maps_compatibility_api_to_apscheduler(monkeypatch):
    from adapters.outbound.repositories import scheduler_repository
    from qs_kernel.infrastructure.persistence import orm

    monkeypatch.setattr(status_module, "_session", lambda: object())
    monkeypatch.setattr(orm, "close_session", lambda: None)
    monkeypatch.setattr(scheduler_repository, "SchedulerRepository", _FakeTaskRepo)

    scheduler = _FakeScheduler()
    result = status_module.trigger_daily_job("evening_pipeline", scheduler)

    assert result["success"] is True
    assert scheduler.triggered == [901]


def test_trigger_rejects_disabled_or_unknown_job(monkeypatch):
    from adapters.outbound.repositories import scheduler_repository
    from qs_kernel.infrastructure.persistence import orm

    class _DisabledRepo(_FakeTaskRepo):
        task = {
            "id": 901,
            "name": "evening_pipeline",
            "command": "evening_pipeline",
            "is_enabled": False,
        }

    monkeypatch.setattr(status_module, "_session", lambda: object())
    monkeypatch.setattr(orm, "close_session", lambda: None)
    monkeypatch.setattr(scheduler_repository, "SchedulerRepository", _DisabledRepo)
    scheduler = _FakeScheduler()

    disabled = status_module.trigger_daily_job("evening_pipeline", scheduler)
    unknown = status_module.trigger_daily_job("not_a_daily_job", scheduler)

    assert disabled["success"] is False
    assert "停用" in disabled["error"]
    assert unknown["success"] is False
    assert "未知任务" in unknown["error"]
    assert scheduler.triggered == []
