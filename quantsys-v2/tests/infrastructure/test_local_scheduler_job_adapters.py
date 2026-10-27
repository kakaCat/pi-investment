"""OS webhook 业务迁回 V2 本地 APScheduler 的适配器回归测试。"""
import asyncio

import pytest

from qs_ops.application.jobs.monitor_jobs import V2HealthCheckJob
from qs_ops.application.jobs.registry_setup import register_all_jobs
from qs_ops.application.jobs.trading_jobs import IntradayRiskCheckJob, StrategyExecuteAllJob


def test_legacy_agent_os_registration_fails_closed():
    from tools.register_jobs_to_agent_os import register_all_jobs

    with pytest.raises(RuntimeError, match="ADR-004"):
        asyncio.run(register_all_jobs())


def test_three_migrated_commands_are_registered_for_local_scheduling():
    from qs_ops.application.jobs.job_registry import job_registry

    register_all_jobs()
    for command in ("strategy_execute_all", "intraday_risk_check", "v2_health_check"):
        assert job_registry.get(command) is not None, command


def test_strategy_execute_all_reuses_business_function(monkeypatch):
    import qs_ops.infrastructure.jobs.strategy_trading_job as business

    captured = {}

    def fake_execute(**params):
        captured.update(params)
        return {"success": True, "date": "2026-10-27", "V13": {"status": "success"}}

    monkeypatch.setattr(business, "strategy_execute_all", fake_execute)
    result = asyncio.run(StrategyExecuteAllJob().execute({"date": "2026-10-27"}))

    assert captured == {"date": "2026-10-27"}
    assert result.success is True
    assert result.details["details"]["V13"]["status"] == "success"


def test_strategy_execute_all_success_false_is_not_silent_success(monkeypatch):
    import qs_ops.infrastructure.jobs.strategy_trading_job as business

    monkeypatch.setattr(
        business,
        "strategy_execute_all",
        lambda **params: {"success": False, "error": "boom"},
    )
    result = asyncio.run(StrategyExecuteAllJob().execute({}))

    assert result.success is False
    assert result.error == "boom"


def test_intraday_risk_failure_propagates(monkeypatch):
    import qs_ops.infrastructure.jobs.strategy_trading_job as business

    monkeypatch.setattr(
        business,
        "intraday_risk_check",
        lambda **params: {"status": "failed", "error": "risk failed"},
    )
    result = asyncio.run(IntradayRiskCheckJob().execute({}))

    assert result.success is False
    assert result.error == "risk failed"


def test_v2_health_check_preserves_degraded_details(monkeypatch):
    import adapters.outbound.repositories.scheduler_repository as repo_module
    import qs_kernel.infrastructure.persistence.orm as orm_module
    import qs_ops.application.jobs.health_monitor as health_module

    session = object()
    captured = {}
    monkeypatch.setattr(orm_module, "get_session", lambda: session)
    monkeypatch.setattr(repo_module, "SchedulerRepository", lambda actual_session: (actual_session,))
    def fake_check(repo):
        captured["repo"] = repo
        return {
            "healthy": False,
            "summary": {"missed": 1},
            "issues": [{"type": "missed_execution"}],
        }

    monkeypatch.setattr(health_module, "check_job_health", fake_check)
    result = asyncio.run(V2HealthCheckJob().execute({}))

    assert captured["repo"] == (session,)
    assert result.success is True
    assert result.details["healthy"] is False
    assert result.details["summary"] == {"missed": 1}
    assert result.details["issues"][0]["type"] == "missed_execution"
