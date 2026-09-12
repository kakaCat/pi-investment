"""回归测（2026-09-13，w-c8cae280）：任务列表读取异常时**不得清空 jobstore**。

实证事故（2026-09-13 01:03）：reload_tasks() 先 remove_all_jobs() 再重建，而
SchedulerRepository.list_tasks 对读库异常是**静默 return []** → 一次瞬时读库失败把
27 个 job 全删，日志还打印 "✅ Tasks reloaded"，调度静默停摆直到下次进程重启。
本测锁定三层护栏：①读库为空但库中有任务 → 中止加载且不碰 jobstore
②reconcile 拒绝空 desired_ids ③reload 不再 remove_all_jobs。
"""
import pytest


class FakeTask:
    def __init__(self, id, name, cron_expression, command, is_enabled=True):
        self.id = id
        self.name = name
        self.cron_expression = cron_expression
        self.command = command
        self.is_enabled = is_enabled
        self.params = {}
        self.misfire_grace_time_seconds = 300
        self.task_type = 'cron'

    def get(self, key, default=None):
        return getattr(self, key, default)


class FlakyRepo:
    """可切换为"读库瞬时失败"的仓储：list 返回空，但 count 仍能看到真实任务数。"""

    def __init__(self, tasks):
        self._tasks = tasks
        self.failing = False

    def list_tasks(self, enabled_only=False):
        if self.failing:
            return []
        return [t for t in self._tasks if t.is_enabled or not enabled_only]

    def count_tasks(self, enabled_only=False):
        return len([t for t in self._tasks if t.is_enabled or not enabled_only])

    def get_task(self, task_id):
        for t in self._tasks:
            if t.id == task_id:
                return t
        return None


@pytest.fixture
def flaky_service():
    from infrastructure.scheduler.apscheduler_service import APSchedulerService

    repo = FlakyRepo([
        FakeTask(1, '任务甲', '0 9 * * 1-5', 'fund_flow_update'),
        FakeTask(2, '任务乙', '30 22 * * 1-5', 'data_update'),
    ])
    service = APSchedulerService('sqlite:///:memory:', repo)
    service.start()
    yield service, repo
    if service.scheduler.running:
        service.shutdown(wait=False)


def test_reload_does_not_wipe_jobstore_when_db_read_fails(flaky_service):
    """读库失败（空列表但库中有任务）时，reload 必须保持 jobstore 原样。"""
    service, repo = flaky_service
    before = len(service.scheduler.get_jobs())
    assert before == 2

    repo.failing = True
    service.reload_tasks()  # 旧实现：remove_all_jobs + 0 条重载 → jobstore 被清空

    assert len(service.scheduler.get_jobs()) == before, "读库异常时不得清空 jobstore"

    repo.failing = False
    service.reload_tasks()
    assert len(service.scheduler.get_jobs()) == 2


def test_reconcile_refuses_empty_desired_set(flaky_service):
    """空 desired_ids 无依据，必须拒绝据此摘除 job。"""
    service, _repo = flaky_service
    removed = service.reconcile_jobs(set())
    assert removed == 0
    assert len(service.scheduler.get_jobs()) == 2


def test_load_returns_none_on_suspicious_empty(flaky_service):
    """读库为空但库中有启用任务 → 判定异常，返回 None（调用方据此中止）。"""
    service, repo = flaky_service
    repo.failing = True
    assert service.load_tasks_from_db() is None
