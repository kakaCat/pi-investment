"""删除调度任务必须同步摘除 APScheduler job（看板事件 3721874a 回归测试）。

根因：DELETE /api/scheduler/tasks/{id} 只做软删除（params._deleted_at + is_enabled=False），
不摘除 APScheduler job；jobstore（public.apscheduler_jobs）是持久化的，残留 job 会继续按
cron 触发，job_executor 读不到任务定义便每次报 "Task N not found in scheduler_tasks"
（实证 2026-09-10 01:50/02:00 共 3 次，直到进程重启才消失）。

新增：tests/api/test_scheduler_delete_detach.py（w-8f2c4cc5 / investor）
"""
import inspect
import json
from types import SimpleNamespace

import pytest

from adapters.inbound.fastapi_app.routes import scheduler_async as sa


class _FakeApscheduler:
    """代替 BackgroundScheduler：记录 get_job/remove_job 调用。"""

    def __init__(self, job_present=True, raise_on_remove=False):
        self.job_present = job_present
        self.raise_on_remove = raise_on_remove
        self.removed = []

    def get_job(self, job_id):
        return object() if self.job_present else None

    def remove_job(self, job_id):
        if self.raise_on_remove:
            raise RuntimeError("scheduler exploded")
        self.removed.append(job_id)


class _FakeSchedulerService:
    def __init__(self, apscheduler=None):
        if apscheduler is not None:
            self.scheduler = apscheduler


class _FakeDomainScheduler:
    """代替 routes 模块里的 _scheduler（domain 层 SchedulerService）。"""

    def __init__(self, task=None):
        self.task = task
        self.updated = []

    def get_task(self, tid):
        return self.task

    def update_task(self, tid, params=None, is_enabled=None):
        self.updated.append({"task_id": tid, "params": params, "is_enabled": is_enabled})
        return True


def _request(scheduler_service=None, with_attr=True):
    state = SimpleNamespace()
    if with_attr:
        state.scheduler_service = scheduler_service
    return SimpleNamespace(app=SimpleNamespace(state=state))


def _task_251():
    return {"id": 251, "name": "realtime-signal-monitor", "params": None}


def test_delete_detaches_registered_apscheduler_job(monkeypatch):
    domain = _FakeDomainScheduler(_task_251())
    aps = _FakeApscheduler(job_present=True)
    monkeypatch.setattr(sa, "_scheduler", domain)

    result = sa.delete_scheduler_task("251", _request(_FakeSchedulerService(aps)))

    assert result == {"success": True}
    assert aps.removed == ["task_251"], "删除后必须摘除 APScheduler job，否则残留 job 无限触发"


def test_delete_keeps_soft_delete_contract(monkeypatch):
    domain = _FakeDomainScheduler(_task_251())
    monkeypatch.setattr(sa, "_scheduler", domain)

    result = sa.delete_scheduler_task("251", _request(_FakeSchedulerService(_FakeApscheduler())))

    assert result == {"success": True}
    assert len(domain.updated) == 1
    rec = domain.updated[0]
    assert rec["task_id"] == 251
    assert rec["is_enabled"] is False
    assert rec["params"].get("_deleted_at")  # 软删除标记必须保留


def test_delete_tolerates_absent_job(monkeypatch):
    domain = _FakeDomainScheduler(_task_251())
    aps = _FakeApscheduler(job_present=False)
    monkeypatch.setattr(sa, "_scheduler", domain)

    result = sa.delete_scheduler_task("251", _request(_FakeSchedulerService(aps)))

    assert result == {"success": True}
    assert aps.removed == []


def test_delete_tolerates_missing_scheduler_service(monkeypatch):
    """Agent OS 托管模式 / APScheduler 未启动时，删除接口不能因摘除失败而失败。"""
    domain = _FakeDomainScheduler(_task_251())
    monkeypatch.setattr(sa, "_scheduler", domain)

    result = sa.delete_scheduler_task("251", _request(None))

    assert result == {"success": True}


def test_delete_tolerates_remove_job_failure(monkeypatch):
    domain = _FakeDomainScheduler(_task_251())
    aps = _FakeApscheduler(job_present=True, raise_on_remove=True)
    monkeypatch.setattr(sa, "_scheduler", domain)

    result = sa.delete_scheduler_task("251", _request(_FakeSchedulerService(aps)))

    assert result == {"success": True}, "摘除失败属 best-effort，不得让删除接口 500"


def test_delete_tolerates_request_absent(monkeypatch):
    """直接函数调用（无 request 注入）时不得抛异常。"""
    domain = _FakeDomainScheduler(_task_251())
    monkeypatch.setattr(sa, "_scheduler", domain)

    result = sa.delete_scheduler_task("251", None)

    assert result == {"success": True}


def test_delete_missing_task_returns_404_without_detach(monkeypatch):
    domain = _FakeDomainScheduler(None)
    aps = _FakeApscheduler(job_present=True)
    monkeypatch.setattr(sa, "_scheduler", domain)

    result = sa.delete_scheduler_task("251", _request(_FakeSchedulerService(aps)))

    assert getattr(result, "status_code", None) == 404
    assert aps.removed == []


def test_delete_route_signature_keeps_request_param():
    """护栏：request 参数被删掉会让 FastAPI 不再注入 app 上下文 → 静默失去摘除能力。"""
    params = inspect.signature(sa.delete_scheduler_task).parameters
    assert "request" in params, "delete_scheduler_task 必须保留 request 参数以取 app.state.scheduler_service"


def test_helper_reports_reason_without_scheduler_service():
    reason = sa._detach_apscheduler_job(_request(None), 251)
    assert isinstance(reason, str) and reason


def test_helper_reports_reason_when_service_has_no_scheduler():
    service = _FakeSchedulerService(None)  # 无 .scheduler 属性
    service.scheduler = None
    reason = sa._detach_apscheduler_job(_request(service), 251)
    assert isinstance(reason, str) and reason


def test_helper_removes_only_target_job(monkeypatch):
    aps = _FakeApscheduler(job_present=True)
    assert sa._detach_apscheduler_job(_request(_FakeSchedulerService(aps)), 318) is None
    assert aps.removed == ["task_318"]
