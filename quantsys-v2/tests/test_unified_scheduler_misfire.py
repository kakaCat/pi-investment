"""
UnifiedSchedulerService 的 misfire 宽限配置测试。

背景（2026-07-22 根因分析）：
调度 daemon 跑在会合盖休眠的笔记本上。APScheduler BackgroundScheduler
用 threading.Event.wait(timeout) 等待下一次任务，底层是 monotonic 时钟
（macOS mach_absolute_time），系统睡眠期间该时钟冻结。
机器睡醒后任务往往已迟到数小时，若 misfire_grace_time 过短（原 300s），
每日任务会被静默跳过——睡眠日 = 无数据更新日。

宽限时间必须覆盖一次完整的夜间休眠（≥12h），配合 coalesce=True，
机器唤醒后立即补跑一次错过的任务。
"""
from application.services.unified_scheduler import (
    DEFAULT_MISFIRE_GRACE_TIME,
    UnifiedSchedulerService,
)


def test_misfire_grace_time_covers_overnight_sleep():
    """默认宽限时间必须 ≥12h，覆盖笔记本合盖过夜休眠的场景。"""
    assert DEFAULT_MISFIRE_GRACE_TIME >= 12 * 3600


def test_scheduler_job_defaults_use_misfire_grace_time():
    """调度器 job_defaults 应用统一的宽限配置。"""
    service = UnifiedSchedulerService()
    assert (
        service.scheduler._job_defaults['misfire_grace_time']
        == DEFAULT_MISFIRE_GRACE_TIME
    )
    # coalesce 必须开启：多次错过合并为一次补跑
    assert service.scheduler._job_defaults['coalesce'] is True


def test_add_cron_job_before_scheduler_start_does_not_raise():
    """调度器未启动时注册任务不应报错。

    daemon 在 start() 之前 load_tasks()，此时 job 处于 pending 状态，
    没有 next_run_time 属性；注册表记账必须容忍（2026-07-02 起日志中
    "Failed to load task ... has no attribute 'next_run_time'" 假错误）。
    """
    service = UnifiedSchedulerService()
    job_id = service.add_cron_job(
        func=lambda: None,
        cron_expr="0 8 * * 0-4",
        job_id="test_pending_job",
    )
    assert service.task_registry[job_id]['next_run'] is None


def test_daemon_job_wrappers_are_pickle_safe():
    """注册进持久化 jobstore 的任务函数必须可 pickle。

    SQLAlchemyJobStore 序列化任务函数：绑定方法会连带序列化实例持有的
    ORM Session 导致 PicklingError（2026-07-22 daemon 启动失败根因）。
    必须改用模块级包装函数（按 "模块:函数名" 引用序列化）。
    """
    import pickle

    from infrastructure.jobs import monitor_jobs

    pickle.dumps(monitor_jobs.daily_orchestrator_tick)
    pickle.dumps(monitor_jobs.intraday_monitor_check)


def test_all_enabled_db_tasks_have_importable_execute():
    """DB 里启用任务的 command（<module>.execute）必须真实存在。

    v13_risk_check / v13_verification / v13_weekly_report 三个任务的
    command 曾指向不存在的 execute 函数，导致启用中却静默不运行
    （2026-07-23 code review 发现#7）。
    """
    import importlib

    commands = [
        'infrastructure.jobs.kline_update_job.execute',
        'infrastructure.jobs.data_quality_check_job.execute',
        'infrastructure.jobs.strategy_trading_job.v13_daily_check',
        'infrastructure.jobs.strategy_trading_job.v14_daily_check',
        'infrastructure.jobs.risk_check_job.execute',
        'infrastructure.jobs.verification_job.execute',
        'infrastructure.jobs.weekly_report_job.execute',
    ]
    for command in commands:
        module_path, func_name = command.rsplit('.', 1)
        func = getattr(importlib.import_module(module_path), func_name, None)
        assert callable(func), f"任务入口不存在: {command}"


def test_add_cron_job_forwards_per_job_misfire_config():
    """add_cron_job 必须把 per-task 的 misfire/coalesce/max_instances 传给 add_job。

    交易类任务（v13/v14 模拟交易）不应享受全局 12h 补跑宽限——
    休眠后迟到数小时的"14:25 交易"会用陈旧报价污染模拟账户。
    DB quant.scheduler_task_configs 有对应列，但此前从未被接线
    （2026-07-23 code review 发现#6）。
    """
    service = UnifiedSchedulerService()
    job_id = service.add_cron_job(
        func=lambda: None,
        cron_expr="25 14 * * 0-4",
        job_id="test_per_task_misfire",
        misfire_grace_time=300,
        coalesce=False,
        max_instances=2,
    )
    # 调度器未启动，job 在 _pending_jobs 缓冲里
    pending = [j for j, _, _ in service.scheduler._pending_jobs if j.id == job_id]
    assert len(pending) == 1
    job = pending[0]
    assert job.misfire_grace_time == 300
    assert job.coalesce is False
    assert job.max_instances == 2
