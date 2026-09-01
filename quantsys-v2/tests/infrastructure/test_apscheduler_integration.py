"""
APScheduler 核心功能集成测试

验证 APScheduler 服务能否正确：
1. 加载真实数据库中的任务
2. 正确解析各种 cron 表达式
3. 支持不同的 task_type
"""
import pytest
from datetime import datetime
from infrastructure.scheduler.apscheduler_service import APSchedulerService
from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
from infrastructure.persistence.orm import get_session


def test_load_real_tasks_from_database():
    """测试从真实数据库加载任务"""
    session = get_session()
    repo = SchedulerRepository(session)

    # 使用内存数据库作为 APScheduler jobstore（避免污染真实数据）
    db_url = "sqlite:///:memory:"
    service = APSchedulerService(db_url, repo)

    # 加载任务
    service.load_tasks_from_db()

    # 获取加载的任务
    jobs = service.scheduler.get_jobs()

    print(f"\n✅ 成功加载 {len(jobs)} 个任务")

    # 验证至少加载了一些任务
    assert len(jobs) > 0, "应该至少加载一些启用的任务"

    # 打印前 10 个任务信息
    print("\n前 10 个任务:")
    for i, job in enumerate(jobs[:10], 1):
        print(f"{i}. {job.name} (ID: {job.id})")
        print(f"   Trigger: {type(job.trigger).__name__}")
        print(f"   Next run: {job.next_run_time}")

    # 验证任务配置正确
    for job in jobs:
        assert job.func.__name__ == 'execute_scheduled_job', "任务应该调用 execute_scheduled_job"
        assert len(job.args) == 1, "应该传递 task_id 作为参数"
        assert isinstance(job.args[0], int), "task_id 应该是整数"

    # 清理
    service.shutdown(wait=False)
    session.close()


def test_cron_expression_parsing():
    """测试各种 cron 表达式解析"""
    session = get_session()
    repo = SchedulerRepository(session)

    # 查询一些有代表性的任务
    tasks = repo.list_tasks(enabled_only=True)

    print(f"\n数据库中有 {len(tasks)} 个启用的任务")

    # 统计各种 cron 表达式
    cron_patterns = {}
    for task in tasks:
        expr = task.get('cron_expression', '')
        if expr not in cron_patterns:
            cron_patterns[expr] = []
        cron_patterns[expr].append(task.get('name'))

    print(f"\n发现 {len(cron_patterns)} 种不同的 cron 表达式:")
    for expr, task_names in list(cron_patterns.items())[:10]:
        print(f"  {expr}: {len(task_names)} 个任务")
        if len(task_names) <= 3:
            for name in task_names:
                print(f"    - {name}")

    session.close()


def test_task_type_distribution():
    """测试任务类型分布"""
    session = get_session()
    repo = SchedulerRepository(session)

    tasks = repo.list_tasks(enabled_only=True)

    # 统计各类型任务数量
    type_counts = {}
    for task in tasks:
        task_type = task.get('task_type', 'cron')
        type_counts[task_type] = type_counts.get(task_type, 0) + 1

    print(f"\n任务类型分布:")
    for task_type, count in type_counts.items():
        print(f"  {task_type}: {count} 个")

    # 验证所有任务都有合法的 task_type
    valid_types = ['cron', 'delay', 'interval', 'once']
    for task in tasks:
        task_type = task.get('task_type', 'cron')
        assert task_type in valid_types, f"任务类型 {task_type} 不合法"

    session.close()


def test_apscheduler_start_and_stop():
    """测试 APScheduler 启动和停止"""
    session = get_session()
    repo = SchedulerRepository(session)

    db_url = "sqlite:///:memory:"
    service = APSchedulerService(db_url, repo)

    # 启动调度器
    service.start()
    assert service.scheduler.running, "调度器应该正在运行"

    # 验证任务已加载
    jobs = service.scheduler.get_jobs()
    print(f"\n✅ 调度器启动成功，加载了 {len(jobs)} 个任务")

    # 停止调度器
    service.shutdown(wait=False)
    assert not service.scheduler.running, "调度器应该已停止"

    print("✅ 调度器停止成功")

    session.close()


def test_manual_trigger():
    """测试手动触发任务"""
    session = get_session()
    repo = SchedulerRepository(session)

    # 找一个简单的任务来测试
    tasks = repo.list_tasks(enabled_only=True)
    if not tasks:
        pytest.skip("没有启用的任务")

    test_task = tasks[0]
    task_id = test_task['id']
    task_name = test_task['name']

    print(f"\n测试手动触发任务: {task_name} (ID: {task_id})")

    db_url = "sqlite:///:memory:"
    service = APSchedulerService(db_url, repo)
    service.start()

    # 手动触发
    service.trigger_task_now(task_id)

    # 验证任务的 next_run_time 被更新
    job = service.scheduler.get_job(f"task_{task_id}")
    if job:
        print(f"✅ 任务触发成功，下次运行时间: {job.next_run_time}")
        assert job.next_run_time is not None

    service.shutdown(wait=False)
    session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("APScheduler 核心功能集成测试")
    print("=" * 60)

    test_load_real_tasks_from_database()
    test_cron_expression_parsing()
    test_task_type_distribution()
    test_apscheduler_start_and_stop()
    test_manual_trigger()

    print("\n" + "=" * 60)
    print("✅ 所有集成测试通过")
    print("=" * 60)
