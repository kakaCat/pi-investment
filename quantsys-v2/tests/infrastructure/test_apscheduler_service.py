"""
APScheduler 服务单元测试

测试 APSchedulerService 的核心功能：
- 初始化
- 任务加载
- 启动/关闭
- 手动触发
- 重新加载

Created: 2026-09-01
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class MockTask:
    """模拟任务对象"""
    def __init__(self, id, name, cron_expression, command, params=None,
                 is_enabled=True, misfire_grace_time_seconds=300):
        self.id = id
        self.name = name
        self.cron_expression = cron_expression
        self.command = command
        self.params = params or {}
        self.is_enabled = is_enabled
        self.misfire_grace_time_seconds = misfire_grace_time_seconds


class MockSchedulerRepository:
    """模拟调度器仓储"""
    def __init__(self):
        self.tasks = [
            MockTask(1, "测试任务1", "0 9 * * *", "fund_flow_update"),
            MockTask(2, "测试任务2", "*/30 * * * *", "pool_refresh_daily"),
            MockTask(3, "Agent OS 任务", "managed_by_agent_os", "signal_generate"),
        ]

    def list_enabled_tasks(self):
        return [t for t in self.tasks if t.is_enabled]

    def get_task(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


@pytest.fixture
def mock_repo():
    """创建模拟仓储"""
    return MockSchedulerRepository()


@pytest.fixture
def apscheduler_service(mock_repo):
    """创建 APScheduler 服务实例"""
    from infrastructure.scheduler.apscheduler_service import APSchedulerService

    # 使用内存数据库进行测试
    db_url = "sqlite:///:memory:"
    service = APSchedulerService(db_url, mock_repo)

    yield service

    # 清理：关闭调度器
    if service.scheduler.running:
        service.shutdown(wait=False)


def test_apscheduler_service_initialization(apscheduler_service):
    """测试 APScheduler 服务初始化"""
    assert apscheduler_service is not None
    assert apscheduler_service.scheduler is not None
    assert not apscheduler_service.scheduler.running


def test_load_tasks_from_db(apscheduler_service, mock_repo):
    """测试从数据库加载任务"""
    apscheduler_service.load_tasks_from_db()

    # 验证任务已加载（应该加载 2 个，跳过 Agent OS 管理的任务）
    jobs = apscheduler_service.scheduler.get_jobs()
    assert len(jobs) == 2

    # 验证任务 ID 格式
    job_ids = [job.id for job in jobs]
    assert "task_1" in job_ids
    assert "task_2" in job_ids
    assert "task_3" not in job_ids  # Agent OS 任务被跳过


def test_start_and_shutdown(apscheduler_service):
    """测试启动和关闭调度器"""
    # 启动
    apscheduler_service.start()
    assert apscheduler_service.scheduler.running

    # 关闭
    apscheduler_service.shutdown(wait=False)
    assert not apscheduler_service.scheduler.running


def test_reload_tasks(apscheduler_service):
    """测试重新加载任务"""
    # 先启动
    apscheduler_service.start()

    # 获取初始任务数量
    initial_jobs = apscheduler_service.scheduler.get_jobs()
    initial_count = len(initial_jobs)

    # 重新加载
    apscheduler_service.reload_tasks()

    # 验证任务数量一致
    reloaded_jobs = apscheduler_service.scheduler.get_jobs()
    assert len(reloaded_jobs) == initial_count

    # 清理
    apscheduler_service.shutdown(wait=False)


def test_get_job_status(apscheduler_service):
    """测试获取任务状态"""
    apscheduler_service.start()

    # 获取存在的任务状态
    status = apscheduler_service.get_job_status(1)
    assert status["exists"] is True
    assert status["name"] == "测试任务1"

    # 获取不存在的任务状态
    status = apscheduler_service.get_job_status(999)
    assert status["exists"] is False

    # 清理
    apscheduler_service.shutdown(wait=False)


def test_trigger_task_now(apscheduler_service):
    """测试手动触发任务"""
    apscheduler_service.start()

    # 触发任务
    apscheduler_service.trigger_task_now(1)

    # 验证任务的 next_run_time 被修改
    job = apscheduler_service.scheduler.get_job("task_1")
    assert job is not None
    assert job.next_run_time is not None

    # 清理
    apscheduler_service.shutdown(wait=False)


def test_skip_agent_os_managed_tasks(apscheduler_service, mock_repo):
    """测试跳过 Agent OS 管理的任务"""
    apscheduler_service.load_tasks_from_db()

    # 验证 Agent OS 任务未加载
    job = apscheduler_service.scheduler.get_job("task_3")
    assert job is None


def test_job_execution_integration(apscheduler_service):
    """测试任务执行集成（验证 APScheduler 调用 execute_scheduled_job）"""
    apscheduler_service.start()

    # 手动触发任务执行（通过修改 next_run_time）
    from datetime import datetime
    job = apscheduler_service.scheduler.get_job("task_1")

    # 注意：在实际运行中，APScheduler 会在到期时自动调用 execute_scheduled_job
    # 这里只验证 job 是否正确配置
    assert job is not None
    # 验证 func 的模块和名称
    assert job.func.__module__ == 'infrastructure.scheduler.job_executor'
    assert job.func.__name__ == 'execute_scheduled_job'
    assert job.args == (1,)

    # 清理
    apscheduler_service.shutdown(wait=False)


def test_cron_trigger_parsing(apscheduler_service):
    """测试 cron 表达式解析"""
    apscheduler_service.load_tasks_from_db()

    # 获取任务
    job = apscheduler_service.scheduler.get_job("task_1")
    assert job is not None

    # 验证 trigger 是 CronTrigger
    from apscheduler.triggers.cron import CronTrigger
    assert isinstance(job.trigger, CronTrigger)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
