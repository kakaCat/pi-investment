"""账户级计划调度任务（REQ-261026140857-c192）"""

import asyncio
from datetime import date

from qs_plan.application.plan_job import (
    TradingPlanGenerateJob,
    TradingPlanReadinessJob,
    build_trading_plan_jobs,
)


class FakeGenerateService:
    def __init__(self):
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return {"plan_id": 1, "revision_id": 2, "version": 1, "status": "draft"}


class FakeReadinessService:
    def __init__(self):
        self.calls = []

    def evaluate(self, **kwargs):
        self.calls.append(kwargs)
        return {"ready": True, "status": "ready", "reasons": []}


def test_generate_job_runs_all_accounts_and_returns_details():
    service = FakeGenerateService()
    job = TradingPlanGenerateJob(
        service=service,
        account_provider=lambda: ("acct-a", "acct-b"),
        now_date=lambda: date(2026, 10, 26),
    )

    result = asyncio.run(job.execute({"actor": "system"}))

    assert result.success is True
    assert result.action == "trading_plan_generate_daily"
    assert len(result.details["results"]) == 2
    assert [call["account"] for call in service.calls] == ["acct-a", "acct-b"]
    assert all(call["trade_date"] == date(2026, 10, 26) for call in service.calls)
    assert all(call["idempotency_key"].endswith(":2026-10-26:generate") for call in service.calls)


def test_readiness_job_reports_ready_count():
    service = FakeReadinessService()
    job = TradingPlanReadinessJob(
        service=service,
        account_provider=lambda: ("acct-a",),
        now_date=lambda: date(2026, 10, 26),
    )

    result = asyncio.run(job.execute({"stage": "runtime"}))

    assert result.success is True
    assert result.message == "ready=1/1"
    assert service.calls[0]["stage"] == "runtime"


def test_missing_service_is_explicit_failure():
    result = asyncio.run(TradingPlanGenerateJob(account_provider=lambda: []).execute({}))

    assert result.success is False
    assert "未注入 PlanGenerationService" in result.error


def test_build_jobs_contains_generate_and_readiness():
    jobs = build_trading_plan_jobs(
        generation_service=FakeGenerateService(),
        readiness_service=FakeReadinessService(),
        account_provider=lambda: [],
    )

    assert [job.name for job in jobs] == [
        "trading_plan_generate_daily",
        "trading_plan_readiness",
    ]
