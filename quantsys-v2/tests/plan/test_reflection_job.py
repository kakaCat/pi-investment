"""反思定时任务测试（t11）：交易日守卫/到期扫描/唤醒/overdue"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from qs_plan.application.reflection_job import (
    PlanReflectionJob,
    PlanReflectionWeeklyJob,
)

NOW = datetime(2026, 10, 21, 15, 35, tzinfo=timezone.utc)
SATURDAY = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)


def _plan(pid=1, due_at=None, last_reflected_at=None, account="agent_brain"):
    return SimpleNamespace(
        id=pid,
        review_interval_days=1,
        review_due_at=due_at,
        last_reflected_at=last_reflected_at,
        status="active",
        account=account,
    )


class FakeRepo:
    def __init__(self, plans):
        self.plans = plans
        self.overdue = {}
        self.due = {}

    def list_due_plans(self, now):
        return self.plans

    def bump_overdue(self, pid):
        self.overdue[pid] = self.overdue.get(pid, 0) + 1
        return self.overdue[pid]

    def set_review_due(self, pid, at):
        self.due[pid] = at


class FakePack:
    def __init__(self, fail_ids=()):
        self.fail_ids = set(fail_ids)

    def build(self, pid):
        if pid in self.fail_ids:
            raise RuntimeError("pack failed")
        return {"plan_id": pid}


class TestReflectionJob:
    def test_non_trading_day_skips(self):
        repo = FakeRepo([_plan()])
        job = PlanReflectionJob(
            plan_repo=repo,
            pack_service=FakePack(),
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: False,
        )
        out = job.run()
        assert out["status"] == "skipped" and out["packed"] == 0

    def test_packs_and_wakes_due_plans(self):
        repo = FakeRepo([_plan(1), _plan(2)])
        woken = []
        job = PlanReflectionJob(
            plan_repo=repo,
            pack_service=FakePack(),
            waker=lambda p, pack: woken.append(p.id),
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )
        out = job.run()
        assert out["packed"] == 2 and out["woken"] == 2
        assert sorted(woken) == [1, 2]
        assert all(pid in repo.due for pid in (1, 2))

    def test_pack_failure_counts_overdue(self):
        repo = FakeRepo([_plan(3)])
        job = PlanReflectionJob(
            plan_repo=repo,
            pack_service=FakePack(fail_ids={3}),
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )
        out = job.run()
        assert out["overdue"] == 1 and repo.overdue[3] == 1
        assert 3 not in repo.due

    def test_wake_failure_counts_overdue(self):
        repo = FakeRepo([_plan(4)])

        def boom(p, pack):
            raise RuntimeError("wake down")

        job = PlanReflectionJob(
            plan_repo=repo,
            pack_service=FakePack(),
            waker=boom,
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )
        out = job.run()
        assert out["overdue"] == 1 and repo.overdue[4] == 1

    def test_no_plans_due(self):
        job = PlanReflectionJob(
            plan_repo=FakeRepo([]),
            pack_service=FakePack(),
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )
        out = job.run()
        assert out["status"] == "ok" and out["due_plans"] == 0

    def test_missed_previous_reflection_counts_overdue(self):
        due = NOW - timedelta(days=1)
        repo = FakeRepo([_plan(5, due_at=due, last_reflected_at=None)])
        woken = []
        job = PlanReflectionJob(
            plan_repo=repo,
            pack_service=FakePack(),
            waker=lambda p, pack: woken.append(p.id),
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )
        out = job.run()
        assert out["overdue"] == 1 and repo.overdue[5] == 1
        assert out["packed"] == 1 and woken == [5]
        assert 5 in repo.due

    def test_reflection_after_previous_due_does_not_count_overdue(self):
        due = NOW - timedelta(days=1)
        repo = FakeRepo([_plan(6, due_at=due, last_reflected_at=due + timedelta(hours=1))])
        job = PlanReflectionJob(
            plan_repo=repo,
            pack_service=FakePack(),
            waker=lambda p, pack: True,
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )
        out = job.run()
        assert out["overdue"] == 0 and 6 in repo.due

    def test_wake_failure_does_not_advance_due(self):
        repo = FakeRepo([_plan(7)])

        def boom(p, pack):
            raise RuntimeError("wake down")

        job = PlanReflectionJob(
            plan_repo=repo,
            pack_service=FakePack(),
            waker=boom,
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )
        out = job.run()
        assert out["overdue"] == 1 and repo.overdue[7] == 1
        assert 7 not in repo.due

    def test_weekly_aggregates_same_account_and_ignores_trading_guard(self):
        repo = FakeRepo([_plan(8, account="agent_brain"), _plan(9, account="agent_brain")])
        calls = []
        job = PlanReflectionWeeklyJob(
            plan_repo=repo,
            pack_service=FakePack(),
            waker=lambda plan, pack: calls.append((plan, pack)),
            now_fn=lambda: SATURDAY,
            trading_day_fn=lambda now: False,  # 周任务不套交易日守卫
        )
        out = job.run()
        assert out["status"] == "ok" and out["packed"] == 2 and out["woken"] == 1
        assert len(calls) == 1
        plan, pack = calls[0]
        assert plan.id is None and plan.account == "agent_brain"
        assert pack["kind"] == "weekly" and pack["plan_count"] == 2
        assert sorted(item["plan_id"] for item in pack["plans"]) == [8, 9]
        assert 8 in repo.due and 9 in repo.due

    def test_weekly_without_waker_still_advances_due(self):
        repo = FakeRepo([_plan(10, account="agent_brain")])
        job = PlanReflectionWeeklyJob(
            plan_repo=repo, pack_service=FakePack(), waker=None, now_fn=lambda: SATURDAY
        )
        out = job.run()
        assert out["status"] == "ok" and out["packed"] == 1 and out["woken"] == 0
        assert 10 in repo.due

    def test_execute_wraps_run_result_as_job_result(self):
        job = PlanReflectionJob(
            plan_repo=FakeRepo([_plan(11)]),
            pack_service=FakePack(),
            waker=lambda p, pack: True,
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )

        result = asyncio.run(job.execute({}))

        assert result.success is True
        assert result.action == "plan_reflect_daily"
        assert result.details["details"]["packed"] == 1
        assert result.details["details"]["woken"] == 1

    def test_execute_converts_exception_to_failed_job_result(self, monkeypatch):
        job = PlanReflectionJob(
            plan_repo=FakeRepo([]),
            pack_service=FakePack(),
            now_fn=lambda: NOW,
            trading_day_fn=lambda now: True,
        )

        def boom(_params):
            raise RuntimeError("reflection failed")

        monkeypatch.setattr(job, "run", boom)
        result = asyncio.run(job.execute({}))

        assert result.success is False
        assert result.action == "plan_reflect_daily"
        assert "reflection failed" in result.error


class TestAgentWaker:
    """FR-1（REQ-261022022657-857f）：既有唤醒通道薄包装 + 组合根注入。"""

    def test_disabled_returns_none(self):
        from qs_plan.application.reflection_job import build_agent_waker

        assert build_agent_waker(enabled=False) is None

    def test_notify_called_with_plan_and_pack_summary(self):
        from qs_plan.application.reflection_job import build_agent_waker

        calls = []

        def notify(event, data, target=None):
            calls.append((event, data, target))
            return True

        waker = build_agent_waker(notify_fn=notify, enabled=True)
        plan = SimpleNamespace(id=7, account="agent_brain")
        assert (
            waker(plan, {"modifications": [1, 2], "wins": [1], "losses": [], "missed": []}) is True
        )
        event, data, target = calls[0]
        assert event == "plan_reflection"
        assert data["plan_id"] == 7 and data["account"] == "agent_brain"
        assert data["pack_summary"]["modifications"] == 2
        assert data["answers_required"] == ["q1", "q2", "q3", "q4", "q5"]
        assert target == "agent-dh"

    def test_notify_weekly_aggregate_pack(self):
        from qs_plan.application.reflection_job import build_agent_waker

        calls = []

        def notify(event, data, target=None):
            calls.append((event, data, target))
            return True

        waker = build_agent_waker(notify_fn=notify, enabled=True)
        plan = SimpleNamespace(id=None, account="agent_ts")
        pack = {
            "kind": "weekly",
            "period": "2026-W43",
            "plan_count": 2,
            "plans": [
                {"plan_id": 1, "pack": {"inputs_ready": ["modifications"]}},
                {"plan_id": 2, "pack": {"inputs_ready": []}},
            ],
        }
        assert waker(plan, pack) is True
        _, data, target = calls[0]
        assert data["plan_id"] is None and data["kind"] == "weekly"
        assert data["period"] == "2026-W43"
        assert data["pack_summary"]["plan_count"] == 2
        assert data["pack_summary"]["inputs_ready"] == 1
        assert target == "agent-ts"

    def test_build_plan_jobs_injects_waker(self):
        from qs_plan.application.reflection_job import build_plan_jobs

        waker = lambda plan, pack: True  # noqa: E731
        jobs = build_plan_jobs(waker=waker)
        assert len(jobs) == 2
        assert jobs[0]._wake is waker and jobs[1]._wake is waker
