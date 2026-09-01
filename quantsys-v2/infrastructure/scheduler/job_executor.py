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


def execute_scheduled_job(task_id: int):
    """
    APScheduler 调用的任务执行入口

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
        # 1. 读取任务定义
        task = repo.get_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found in scheduler_tasks")
            return

        if not task.is_enabled:
            logger.warning(f"Task {task_id} ({task.name}) is disabled, skipping")
            return

        # 2. 检查是否已有运行中的实例（防止并发）
        running_runs = repo.get_running_runs(task_id)
        if running_runs:
            # 检查僵尸任务（运行超过 6 小时）
            for run in running_runs:
                if _is_zombie_run(run):
                    logger.warning(
                        f"Zombie run detected: run_id={run.id}, "
                        f"started_at={run.started_at}, marking as failed"
                    )
                    repo.complete_run(
                        run_id=run.id,
                        success=False,
                        error="Zombie process: execution timeout (>6 hours)"
                    )
                else:
                    logger.warning(
                        f"Task {task_id} ({task.name}) already running "
                        f"(run_id={run.id}), skipping"
                    )
                    return

        # 3. 创建执行记录
        run_id = repo.create_run(task_id)
        logger.info(
            f"Starting task: {task.name} "
            f"(task_id={task_id}, run_id={run_id}, command={task.command})"
        )

        start_time = datetime.now()

        try:
            # 4. 执行任务（路由到 JobRegistry/Legacy Handler）
            result = _execute_command(task.command, task.params or {})

            # 5. 记录成功
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            repo.complete_run(
                run_id=run_id,
                success=True,
                result=result,
                duration_ms=duration_ms
            )

            logger.info(
                f"Task completed successfully: {task.name} "
                f"(run_id={run_id}, duration={duration_ms}ms)"
            )

        except Exception as e:
            # 6. 记录失败
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            repo.complete_run(
                run_id=run_id,
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )

            logger.exception(
                f"Task failed: {task.name} "
                f"(run_id={run_id}, duration={duration_ms}ms, error={e})"
            )

    finally:
        # 7. 清理数据库连接（防止泄漏）
        try:
            session.close()
        except Exception as e:
            logger.error(f"Failed to close session: {e}")


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
    执行 Legacy Handler（6 个特殊命令）

    这些命令暂未迁移到 JobRegistry：
    - data_update
    - risk_check
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
        "risk_check": legacy_service._handle_risk_check,
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
        run: SchedulerRun 对象

    Returns:
        True 如果是僵尸任务
    """
    if run.started_at is None:
        return False

    # 确保 started_at 有时区信息
    started_at = run.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    elapsed = datetime.now(timezone.utc) - started_at
    return elapsed > timedelta(hours=6)
