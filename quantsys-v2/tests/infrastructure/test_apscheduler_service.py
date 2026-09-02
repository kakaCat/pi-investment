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
                 is_enabled=True, misfire_grace_time_seconds=300, task_type='cron'):
        self.id = id
        self.name = name
        self.cron_expression = cron_expression
        self.command = command
        self.params = params or {}
        self.is_enabled = is_enabled
        self.misfire_grace_time_seconds = misfire_grace_time_seconds
        self.task_type = task_type

    def get(self, key, default=None):
        """支持字典式访问"""
        return getattr(self, key, default)


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

    def list_tasks(self, enabled_only=False):
        if enabled_only:
            return [t for t in self.tasks if t.is_enabled]
        return self.tasks

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


def test_delay_task_with_date_trigger(mock_repo):
    """测试延迟任务使用 DateTrigger"""
    from infrastructure.scheduler.apscheduler_service import APSchedulerService

    # 添加延迟任务到 mock_repo
    delay_task = MockTask(
        id=4,
        name="延迟任务测试",
        cron_expression="DELAY:300",  # 300秒后执行
        command="test_command",
        params={"delay_seconds": 300},
        task_type="delay"
    )
    mock_repo.tasks.append(delay_task)

    # 创建服务并加载任务
    db_url = "sqlite:///:memory:"
    service = APSchedulerService(db_url, mock_repo)
    service.load_tasks_from_db()

    # 验证延迟任务已加载
    job = service.scheduler.get_job("task_4")
    assert job is not None

    # 验证 trigger 是 DateTrigger
    from apscheduler.triggers.date import DateTrigger
    assert isinstance(job.trigger, DateTrigger)

    # 验证 run_date 在未来
    from datetime import datetime
    import pytz
    tz = pytz.timezone('Asia/Shanghai')
    assert job.trigger.run_date > datetime.now(tz)

    # 清理
    if service.scheduler.running:
        service.shutdown(wait=False)


def test_interval_task_with_interval_trigger(mock_repo):
    """测试间隔任务使用 IntervalTrigger"""
    from infrastructure.scheduler.apscheduler_service import APSchedulerService

    # 添加间隔任务到 mock_repo
    interval_task = MockTask(
        id=5,
        name="间隔任务测试",
        cron_expression="INTERVAL:60",  # 每60秒执行
        command="test_command",
        params={"interval_seconds": 60},
        task_type="interval"
    )
    mock_repo.tasks.append(interval_task)

    # 创建服务并加载任务
    db_url = "sqlite:///:memory:"
    service = APSchedulerService(db_url, mock_repo)
    service.load_tasks_from_db()

    # 验证间隔任务已加载
    job = service.scheduler.get_job("task_5")
    assert job is not None

    # 验证 trigger 是 IntervalTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    assert isinstance(job.trigger, IntervalTrigger)

    # 验证间隔时间
    assert job.trigger.interval.total_seconds() == 60

    # 清理
    if service.scheduler.running:
        service.shutdown(wait=False)


def test_once_task_with_date_trigger(mock_repo):
    """测试一次性任务使用 DateTrigger"""
    from infrastructure.scheduler.apscheduler_service import APSchedulerService
    from datetime import datetime, timedelta

    # 计算未来时间
    future_time = datetime.now() + timedelta(hours=1)
    future_time_str = future_time.isoformat()

    # 添加一次性任务到 mock_repo
    once_task = MockTask(
        id=6,
        name="一次性任务测试",
        cron_expression=future_time_str,
        command="test_command",
        params={"run_at": future_time_str},
        task_type="once"
    )
    mock_repo.tasks.append(once_task)

    # 创建服务并加载任务
    db_url = "sqlite:///:memory:"
    service = APSchedulerService(db_url, mock_repo)
    service.load_tasks_from_db()

    # 验证一次性任务已加载
    job = service.scheduler.get_job("task_6")
    assert job is not None

    # 验证 trigger 是 DateTrigger
    from apscheduler.triggers.date import DateTrigger
    assert isinstance(job.trigger, DateTrigger)

    # 清理
    if service.scheduler.running:
        service.shutdown(wait=False)


def test_create_trigger_with_invalid_type(apscheduler_service):
    """测试不支持的任务类型抛出异常"""
    with pytest.raises(ValueError, match="Unsupported task_type"):
        apscheduler_service._create_trigger('invalid_type', {'name': 'test', 'cron_expression': '* * * * *'})

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
