"""
调度任务执行器

负责实际执行调度任务，包括：
- 从 scheduler_tasks 读取任务定义
- 创建执行记录到 scheduler_runs
- 路由到 JobRegistry 或 Legacy Handler
- 记录执行结果和错误
- 处理僵尸任务（运行超过 6 小时）

Created: 2026-09-01
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def classify_job_result(result: Any) -> Optional[str]:
    """判定 job handler 返回值是否为「内层失败」，是则返回错误摘要，否则 None。

    P0-B（2026-09-10 w-23c70356 审计）：调度器此前只看「有没有抛异常」决定 run 状态，
    handler 用返回值报告失败（返回 dict 不抛异常）时 run 记录仍写 success —— 真实失败
    只躺在 scheduler_runs.result 里，看门狗一路报 ok。实证：market_perception_daily
    2026-09-07~09-10 连败 4 天，4 条 run 全 success；历史同类 40 条（2026-06-04 起）。

    判定口径（覆盖仓库里并存的三种 handler 约定，任一命中即失败）：
    1. {"success": False, "error": ...}      —— scheduler_handlers 风格
    2. {"status": "failed"|"error", ...}     —— JobRegistry / legacy 风格
    3. 未给 status 且 error 非空             —— 裸错误返回

    对显式 {"success": True} / {"status": "success"} / {"error": None} 一律判成功，
    避免把正常返回误判成失败（宁少报不误报：本函数只做失败升级，不做成功降级）。
    """
    if not isinstance(result, dict):
        return None

    if result.get("success") is False:
        return str(
            result.get("error")
            or result.get("message")
            or "handler reported success=false"
        )[:2000]

    status = result.get("status")
    if isinstance(status, str):
        if status.lower() in ("failed", "error"):
            return str(result.get("error") or f"handler status={status}")[:2000]
        return None  # 显式给出成功态 status → 不再看 error 字段

    if result.get("success") is True:
        return None

    error = result.get("error")
    if error:
        return str(error)[:2000]
    return None


def execute_scheduled_job(task_id: int):
    """APScheduler 调用入口（REQ-a42aa4 Batch C 包装：设/清任务上下文后执行）。

    线程级任务上下文让本线程上任意 ERROR 日志（含深层 logger.exception）
    自动携带 task_id/task_name 结构化上报 Agent OS；finally 确保清空，
    防止线程池复用线程时上下文串扰到下一个任务。
    """
    from infrastructure.error_reporting import agent_os_reporter
    agent_os_reporter.set_task_context(task_id=task_id)
    try:
        return _execute_scheduled_job_impl(task_id)
    finally:
        agent_os_reporter.clear_task_context()


def _execute_scheduled_job_impl(task_id: int):
    """
    计划任务执行体（原 execute_scheduled_job 主体）

    执行流程：
    1. 读取任务定义（scheduler_tasks）
    2. 检查是否已有运行中的实例（防止并发）
    3. 创建执行记录（scheduler_runs，status='running'）
    4. 路由到 JobRegistry 或 Legacy Handler 执行
    5. 更新执行记录（success/failed，记录结果/错误）
    6. 清理数据库连接（防止泄漏）

    Args:
        task_id: scheduler_tasks 表的任务 ID
    """
    from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
    from infrastructure.persistence.orm import get_session

    session = get_session()
    repo = SchedulerRepository(session)

    try:
        # 1. 读取任务定义（repo 返回 dict——2026-09-01 修复对象属性混用）
        task = repo.get_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found in scheduler_tasks")
            return

        task_name = task.get('name', f'task-{task_id}')
        from infrastructure.error_reporting import agent_os_reporter
        agent_os_reporter.set_task_context(task_id=task_id, task_name=task_name)
        if not task.get('is_enabled'):
            logger.warning(f"Task {task_id} ({task_name}) is disabled, skipping")
            return

        # 2. 检查是否已有运行中的实例（防止并发）
        # repo 无 get_running_runs 方法（重构遗漏），用 list_runs(statuses=['running'])
        running_runs = repo.list_runs(task_id=task_id, statuses=['running'], limit=10)
        if running_runs:
            for run in running_runs:
                if _is_zombie_run(run):
                    logger.warning(
                        f"Zombie run detected: run_id={run.get('id')}, "
                        f"started_at={run.get('started_at')}, marking as failed"
                    )
                    repo.complete_run(
                        run_id=run.get('id'),
                        success=False,
                        error="Zombie process: execution timeout (>6 hours)"
                    )
                else:
                    logger.warning(
                        f"Task {task_id} ({task_name}) already running "
                        f"(run_id={run.get('id')}), skipping"
                    )
                    return

        # 3. 创建执行记录
        run_id = repo.create_run(task_id)
        logger.info(
            f"Starting task: {task_name} "
            f"(task_id={task_id}, run_id={run_id}, command={task.get('command')})"
        )

        start_time = datetime.now()

        try:
            # 4. 执行任务（路由到 JobRegistry/Legacy Handler）
            result = _execute_command(task.get('command'), task.get('params') or {})

            # 5. 记录成功/失败
            # Fix②（审计发现）：内层失败曾被无条件 success=True 吞掉——Job 内部失败被
            # JobRegistry 转成 {status:'failed',...} dict 返回，从不抛异常，外层却记 success=True
            # → scheduler_tasks.last_status 假成功、真实失败只藏在 runs.result 内层。
            # 现在以外层内层 result.status 为准：status=='failed' → 外层也记 failed。
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            # P0-B（2026-09-10 w-23c70356）：原判定只认 status=='failed'，漏掉
            # "success: false" 风格的 handler（market_perception_daily 正是这种）→ 统一
            # 走 classify_job_result（与 webhook 路径共用同一口径，见 scheduler_webhook.py）。
            error = classify_job_result(result)
            inner_failed = error is not None
            # REQ-a42aa4 Batch C：Job 内层失败结构化上报 Agent OS（此前该路径无 ERROR
            # 日志，真实失败只躺在 scheduler_runs.result 里 → 主动带 task 上下文上报）。
            if inner_failed and error:
                agent_os_reporter.report_event(
                    f"[scheduler_task] {task_name} inner failed: {error}",
                    detail=str(result.get('details') or result.get('result') or '')[:4000],
                    task_id=task_id, task_name=task_name,
                    logger_name=__name__,
                    metadata={"channel": "scheduler_job", "command": task.get('command'),
                              "run_id": str(run_id), "outer_success": False},
                )
            # Fix（2026-09-05 w-8366e526）：executor 会话与 Job 共享同一线程级 session；
            # Job 内部 DB 工作中途报错会留下 aborted 事务 → complete_run 的 SELECT/UPDATE
            # 报 "Can't reconnect until invalid transaction is rolled back"
            # （实证：data_quality_check 任务 run 3408 等）。落记录前先回滚会话止血。
            session.rollback()
            repo.complete_run(
                run_id=run_id,
                success=not inner_failed,
                result=result,
                error=error,
            )

            logger.info(
                f"Task completed: {task_name} "
                f"(run_id={run_id}, duration={duration_ms}ms, "
                f"outer_success={not inner_failed}, inner_status={result.get('status') if isinstance(result, dict) else 'n/a'})"
            )

        except Exception as e:
            # 6. 记录失败
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            session.rollback()  # 同上：Job 异常可能已污染共享会话，先回滚再写失败记录
            repo.complete_run(
                run_id=run_id,
                success=False,
                error=str(e),
            )

            logger.exception(
                f"Task failed: {task_name} "
                f"(run_id={run_id}, duration={duration_ms}ms, error={e})"
            )

    finally:
        # 7. 清理数据库连接（防止泄漏）——best-effort：session 可能为 None（建会话即失败）
        #    或测试替身（无 close 方法），缺 close() 不构成错误。
        #    2026-09-10 w-8f2c4cc5：原实现把 AttributeError（'object' object has no
        #    attribute 'close'）打成 ERROR 级日志并被上报到错误看板，属纯噪音。
        _close = getattr(session, "close", None)
        if callable(_close):
            try:
                _close()
            except Exception as e:
                logger.warning(f"Failed to close session: {e}")


def _execute_command(command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行命令（路由到 JobRegistry 或 Legacy Handler）

    路由优先级：
    1. JobRegistry（优先） - 28 个已注册的 Job
    2. Legacy Handler（fallback） - 6 个特殊命令

    Args:
        command: 命令名称（如 "fund_flow_update"）
        params: 命令参数字典

    Returns:
        执行结果字典，格式：
        {
            "action": "fund_flow_update",
            "status": "success" | "failed",
            "message": "执行结果说明",
            "details": {...},  # 详细结果
            "error": None | "错误信息"
        }

    Raises:
        ValueError: 命令未在 JobRegistry 或 Legacy Handler 中找到
        Exception: 任务执行过程中的异常
    """
    from application.jobs.job_registry import job_registry

    # 1. 优先从 JobRegistry 获取 job
    job = job_registry.get(command)
    if job is not None:
        logger.info(f"Executing job via JobRegistry: {command}")
        try:
            # JobRegistry.execute 是 async 的，需要用 asyncio.run 包装
            result = asyncio.run(job_registry.execute(command, params or {}))

            # 将 JobResult 转换为 dict 格式（向后兼容）
            return {
                "action": command,
                "status": "success" if result.success else "failed",
                "message": result.message,
                "details": result.details or {},
                "error": result.error,
            }

        except Exception as e:
            logger.exception(f"JobRegistry execution failed for {command}")
            return {
                "action": command,
                "status": "failed",
                "error": str(e),
            }

    # 2. Fallback: 使用旧的 legacy handler
    logger.debug(f"Job not in JobRegistry, trying legacy handler: {command}")
    return _execute_legacy_handler(command, params)


def _execute_legacy_handler(command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行 Legacy Handler（5 个特殊命令）

    这些命令暂未迁移到 JobRegistry：
    - data_update
    - backtest_run
    - model_train
    - benchmark_run
    - index_constituents_update

    Args:
        command: 命令名称
        params: 命令参数

    Returns:
        执行结果字典

    Raises:
        ValueError: 命令未找到
    """
    from infrastructure.scheduler.scheduler import SchedulerService

    # 创建一个临时的 SchedulerService 实例（只用它的 legacy handlers）
    # 注意：这里传 repo=None 是安全的，因为 legacy handlers 不依赖 repo
    legacy_service = SchedulerService(repo=None)

    # 调用 legacy handler
    legacy_handlers = {
        "data_update": legacy_service._handle_data_update,
        "backtest_run": legacy_service._handle_backtest_run,
        "model_train": legacy_service._handle_model_train,
        "benchmark_run": legacy_service._handle_benchmark_run,
        "index_constituents_update": legacy_service._handle_index_constituents_update,
    }

    handler = legacy_handlers.get(command)
    if handler is None:
        raise ValueError(
            f"Unknown scheduler command: {command!r}. "
            f"Not in JobRegistry and not in legacy handlers."
        )

    logger.info(f"Executing legacy handler: {command}")
    return handler(params)


def _is_zombie_run(run) -> bool:
    """
    判断是否为僵尸任务（运行超过 6 小时）

    Args:
        run: SchedulerRun dict（repo._row_to_dict 返回，started_at 为 ISO 字符串或 None）
        ——2026-09-01 修复：原按 ORM 对象访问，repo 实际返回 dict

    Returns:
        True 如果是僵尸任务
    """
    raw = run.get('started_at') if isinstance(run, dict) else getattr(run, 'started_at', None)
    if raw is None:
        return False

    # dict 路径：ISO 字符串解析
    if isinstance(raw, str):
        try:
            started_at = datetime.fromisoformat(raw)
        except ValueError:
            return False
    else:
        started_at = raw

    # 确保 started_at 有时区信息
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    elapsed = datetime.now(timezone.utc) - started_at
    return elapsed > timedelta(hours=6)
