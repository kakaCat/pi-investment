"""Fix② 回归测试：job_executor 外层 success 不再吞掉内层 status='failed'

审计发现（profit-engine-autonomy-full-flow-audit-20260903）：
Job 内部失败被 JobRegistry 转成 {status:'failed', error:...} dict 返回（从不抛异常），
原实现无条件 complete_run(success=True) → scheduler_tasks.last_status 假成功。
修复后：内层 result.status=='failed' → 外层也记 failed。
"""
import pytest


class _FakeTask:
    @staticmethod
    def get(name, default=None):
        return {"name": "fake-task", "command": "fake_cmd", "params": {}}.get(name, default)


class _FakeRun:
    def __init__(self):
        self.id = 1
        self.task_id = 1
        self.status = "running"
        self.completed_at = None
        self.result = None
        self.error = None
        self.started_at = None
        self.duration_ms = None


class _FakeRepo:
    """记录 complete_run 调用的假仓库"""

    def __init__(self):
        self.completed = []

    def get_task(self, task_id):
        return {"id": task_id, "name": "fake-task", "command": "fake_cmd", "is_enabled": True}

    def list_runs(self, task_id=None, statuses=None, limit=10):
        return []

    def create_run(self, task_id):
        return 1

    def complete_run(self, run_id, success=True, result=None, error=None):
        self.completed.append({
            "run_id": run_id, "success": success, "result": result, "error": error,
        })
        return True


def _patch_execute(monkeypatch, return_value):
    import infrastructure.scheduler.job_executor as je

    repo = _FakeRepo()
    monkeypatch.setattr(je, "_execute_command", lambda command, params: return_value)
    # 屏蔽真实 DB 工厂（测试不落库）
    # execute_scheduled_job 在函数内 import SchedulerRepository / get_session，
    # 这里 patch 它们的定义源模块（函数内 import 解析的是模块全局名）
    import adapters.outbound.repositories.scheduler_repository as sched_repo_mod
    monkeypatch.setattr(sched_repo_mod, "SchedulerRepository", lambda session: repo)
    import infrastructure.persistence.orm as orm_mod
    monkeypatch.setattr(orm_mod, "get_session", lambda: object())
    return repo


def test_inner_failed_propagates_to_outer(monkeypatch):
    """内层 status='failed' 必须记外层 failed（防假成功）"""
    import infrastructure.scheduler.job_executor as je

    repo = _patch_execute(monkeypatch, {
        "action": "fake_cmd", "status": "failed", "error": "boom", "details": {},
    })
    je.execute_scheduled_job(1)
    assert repo.completed, "complete_run 应被调用"
    call = repo.completed[0]
    assert call["success"] is False
    assert call["error"] == "boom"
    assert call["result"]["status"] == "failed"


def test_inner_success_stays_success(monkeypatch):
    """内层 status='success' 记外层 success"""
    import infrastructure.scheduler.job_executor as je

    repo = _patch_execute(monkeypatch, {
        "action": "fake_cmd", "status": "success", "message": "ok", "details": {},
    })
    je.execute_scheduled_job(1)
    call = repo.completed[0]
    assert call["success"] is True
    assert call["error"] is None


def test_job_registry_exception_still_fails(monkeypatch):
    """JobRegistry 层抛异常（_execute_command 上层未捕获）→ 外层 failed"""
    import infrastructure.scheduler.job_executor as je

    repo = _patch_execute(monkeypatch, None)
    # 让 _execute_command 抛异常，验证 except 分支仍记 failed
    def boom(command, params):
        raise RuntimeError("hard crash")
    monkeypatch.setattr(je, "_execute_command", boom)
    je.execute_scheduled_job(1)
    call = repo.completed[0]
    assert call["success"] is False
    assert "hard crash" in (call["error"] or "")
