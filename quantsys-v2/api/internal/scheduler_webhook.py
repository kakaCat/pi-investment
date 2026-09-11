"""Internal webhook endpoint for Agent OS Scheduler callbacks.

This module provides the webhook receiver that Agent OS calls when
scheduled jobs need to execute. It dispatches to registered job handlers
and manages execution in background tasks.

Architecture:
    Agent OS Scheduler (cron engine)
         ↓ HTTP POST (webhook)
    Webhook Receiver (this module)
         ↓ dispatch by job_type
    Job Handler (registered via @register_job_handler)
         ↓ execute business logic
    PostgreSQL (scheduler_runs table)

Usage:
    # In a job handler module:
    from api.internal.scheduler_webhook import register_job_handler

    @register_job_handler("kline_update")
    async def handle_kline_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
        # Execute job logic
        return {"updated_count": 100}
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Request/Response Models ====================


class WebhookPayload(BaseModel):
    """Webhook payload from Agent OS Scheduler.

    This is the data structure that Agent OS sends when triggering
    a scheduled job via webhook.
    """

    job_id: str  # Job UUID from Agent OS
    job_name: str  # Human-readable job name
    trigger_time: str  # ISO timestamp when job was triggered
    metadata: Dict[str, Any]  # Custom payload (includes job_type)


class WebhookResponse(BaseModel):
    """Webhook response sent back to Agent OS.

    Confirms that the webhook was received and execution has started
    (in background).
    """

    status: str  # "accepted" or "error"
    job_id: str  # Echo back the job_id
    job_name: str  # Echo back the job_name
    message: str = ""  # Optional message


# ==================== Job Handler Registry ====================

# Global registry of job handlers: job_type -> async function
JOB_HANDLERS: Dict[str, Callable] = {}


def register_job_handler(job_type: str):
    """Decorator to register a job handler function.

    Usage:
        @register_job_handler("kline_update")
        async def handle_kline_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
            # Job logic here
            return {"result": "success"}

    Args:
        job_type: The job_type string that will be in webhook metadata

    Returns:
        Decorator function
    """

    def decorator(func: Callable):
        JOB_HANDLERS[job_type] = func
        logger.info(f"Registered job handler: {job_type} -> {func.__name__}")
        return func

    return decorator


# ==================== Webhook Endpoint ====================


@router.post("/webhook", response_model=WebhookResponse)
async def scheduler_webhook(
    payload: WebhookPayload, background_tasks: BackgroundTasks
) -> WebhookResponse:
    """Receive job execution trigger from Agent OS Scheduler.

    This endpoint is called by Agent OS when a scheduled job should run.
    It validates the payload, looks up the appropriate handler, and
    starts execution in a background task.

    The response is returned immediately (non-blocking), and the actual
    job execution happens asynchronously. Results are reported back to
    Agent OS via the client's report_job_result() method.

    Args:
        payload: Webhook payload from Agent OS
        background_tasks: FastAPI background tasks manager

    Returns:
        WebhookResponse confirming acceptance

    Raises:
        HTTPException: If job_type is missing or unknown (400/404)
    """
    job_type = payload.metadata.get("job_type")

    # Fallback: If metadata is missing job_type, infer from job_name
    # (workaround for Agent OS bug where metadata is not passed in webhook)
    if not job_type:
        job_type = payload.job_name
        logger.warning(
            f"Webhook payload missing job_type in metadata, "
            f"using job_name '{job_type}' as fallback"
        )

    if not job_type:
        logger.error(f"Webhook payload missing both job_type and job_name: {payload.model_dump()}")
        raise HTTPException(
            status_code=400, detail="Missing job_type in metadata and job_name"
        )

    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        logger.error(
            f"Unknown job_type '{job_type}' for job {payload.job_name}. "
            f"Available handlers: {list(JOB_HANDLERS.keys())}"
        )
        raise HTTPException(
            status_code=404, detail=f"Unknown job_type: {job_type}"
        )

    logger.info(
        f"Received webhook for job '{payload.job_name}' (type={job_type}, "
        f"job_id={payload.job_id})"
    )

    # Execute in background
    background_tasks.add_task(execute_job, handler, payload)

    return WebhookResponse(
        status="accepted",
        job_id=payload.job_id,
        job_name=payload.job_name,
        message=f"Job execution started for {job_type}",
    )


# ==================== Background Execution ====================


def _run_sync_handler_with_session_release(handler: Callable, metadata: dict):
    """在线程池线程内执行同步 handler，**并在同一线程内释放 ORM 会话**。

    2026-09-11（w-f4aa1f6a）：实测事故根因——同步 handler 经 run_in_threadpool 跑在
    线程池线程里，而 close_session() 只清"当前线程"的 scoped 注册表。线程池线程长期存活，
    于是每个线程读一次 ORM 就把会话永久挂住（session_guard 实测 age_seconds>300、
    thread_name=ThreadPoolExecutor-108_6 等，累计 25 次），最终把 DB 连接池打满
    （事件 ed7d2f6a utilization 100%）。
    修法：把释放放在**执行线程内部**的 finally——从事件循环里调 close_session() 清的是
    asyncio 线程的注册表，解决不了问题。
    """
    try:
        return handler(metadata)
    finally:
        try:
            from infrastructure.persistence.orm.config import close_session

            close_session()
        except Exception as exc:  # 释放失败不应影响任务结果
            logger.warning(f"释放线程会话失败（{exc}）")


async def execute_job(handler: Callable, payload: WebhookPayload):
    """Execute job handler and report results to Agent OS.

    This runs in a FastAPI background task to avoid blocking the
    webhook response. It:
    1. Generates a run_id
    2. Calls the job handler (sync or async)
    3. Writes run record to local database
    4. Reports result back to Agent OS

    Handlers are classified as:
    - Async handlers: awaited directly on the event loop
    - Sync handlers: executed in threadpool to avoid blocking

    Args:
        handler: The job handler function (sync or async)
        payload: Webhook payload from Agent OS
    """
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)

    logger.info(
        f"Executing job '{payload.job_name}' (run_id={run_id}, "
        f"job_id={payload.job_id})"
    )

    try:
        # Detect if handler is async or sync
        if inspect.iscoroutinefunction(handler):
            # Async handler: await directly on the event loop
            logger.debug(f"Executing async handler for {payload.job_name}")
            result = await handler(payload.metadata)
        else:
            # Sync handler: run in threadpool to avoid blocking event loop。
            # 2026-09-11（w-f4aa1f6a）：经 wrapper 执行，保证在线程池线程内释放 ORM 会话，
            # 否则该线程的 scoped 会话永久占住连接（连接池耗尽的根因）。
            logger.debug(f"Executing sync handler for {payload.job_name} in threadpool")
            result = await run_in_threadpool(
                _run_sync_handler_with_session_release, handler, payload.metadata
            )

        # P0-B 修复（2026-09-10 w-23c70356 审计）：此前无论 handler 返回什么，这里都硬编码
        # status="success" —— handler 用 {"success": False, "error": ...} 报告内部失败时
        # （不抛异常），run 记录仍写 success，真实失败只躺在 scheduler_runs.result 里。
        # 实证：market_perception_daily 2026-09-07~09-10 连败 4 天（AttributeError），
        # 4 条 run 全 success，看门狗 v2_health_check 全程报 ok。现以内层结果为准，
        # 判定口径与 APScheduler 路径共用 classify_job_result（避免两套口径再次漂移）。
        from infrastructure.scheduler.job_executor import classify_job_result

        inner_error = classify_job_result(result)
        if inner_error is None:
            status = "success"
            error_msg = None
            logger.info(
                f"Job '{payload.job_name}' succeeded (run_id={run_id}): {result}"
            )
        else:
            status = "failed"
            error_msg = inner_error
            # 结构化 ERROR 日志：Agent OS 错误上报据此带 task 上下文入库
            logger.error(
                f"Job '{payload.job_name}' inner failed (run_id={run_id}): "
                f"{inner_error}; result={result}"
            )
    except Exception as e:
        logger.exception(f"Job '{payload.job_name}' failed (run_id={run_id})")
        status = "failed"
        error_msg = str(e)
        result = None

    end_time = datetime.now(timezone.utc)

    # Write to local database
    try:
        from infrastructure.scheduler.scheduler import SchedulerService

        scheduler = SchedulerService()
        # Note: We don't have a task_id in local DB for Agent OS jobs
        # We'll need to adapt the schema or create a mapping
        # For now, we'll store job_id as a string in params
        logger.debug(
            f"Writing run record to local database: run_id={run_id}, "
            f"status={status}"
        )

        # Create a pseudo-task if needed for compatibility
        # This is a workaround until we update the schema
        await _write_run_to_database(
            run_id=run_id,
            job_id=payload.job_id,
            job_name=payload.job_name,
            status=status,
            started_at=start_time,
            completed_at=end_time,
            result=result,
            error_msg=error_msg,
        )

    except Exception as e:
        logger.error(
            f"Failed to write run record to local database: {e}", exc_info=True
        )

    # Report back to Agent OS — use the scheduler's own run_id (carried in
    # metadata by the executor) so the scheduler's run record reflects the
    # REAL job outcome, not just "webhook accepted". Older executors don't
    # send run_id; skip reporting instead of hitting a wrong URL.
    agent_run_id = payload.metadata.get("run_id")
    if not agent_run_id:
        logger.warning(
            f"No run_id in metadata for job '{payload.job_name}' — "
            "skipping result report to Agent OS"
        )
        return

    try:
        from application.services.agent_os_client import get_agent_os_client

        agent_os_client = get_agent_os_client()
        await agent_os_client.report_job_result(
            agent_run_id,
            {
                "status": status,
                "output": json.dumps(result) if result else "",
                "error": error_msg or "",
            },
        )
        logger.debug(
            f"Reported result to Agent OS: run_id={agent_run_id}, "
            f"status={status}"
        )
    except Exception as e:
        logger.error(f"Failed to report job result to Agent OS: {e}", exc_info=True)


async def _write_run_to_database(
    run_id: str,
    job_id: str,
    job_name: str,
    status: str,
    started_at: datetime,
    completed_at: datetime,
    result: Any,
    error_msg: str | None,
):
    from adapters.outbound.repositories.scheduler_repository import SchedulerRepository

    repo = SchedulerRepository()

    task = repo.get_task_by_name(job_name)
    if task:
        task_id = task["id"]
    else:
        task_id = repo.add_task(
            name=job_name,
            cron_expression="managed_by_agent_os",
            command="agent_os_webhook",
            params={"job_id": job_id, "managed_by": "agent_os"},
            description=f"Agent OS managed job (job_id={job_id})",
        )
        repo.disable_task(task_id)

    # P0-C 修复（2026-09-10 w-23c70356 审计）：本函数收下的 started_at/completed_at
    # 原先是死参数（从未使用），run 记录的两个时间戳都由 repo 内部 now() 生成 ——
    # webhook 路径是"先跑完再写库"，于是 duration_ms 只剩写库开销（恒 3~15ms），
    # 任务真实耗时（0.16s / 3.3s / 数分钟）在 run 表里全部丢失。现如实回传。
    run_db_id = repo.create_run(task_id, started_at=started_at)
    repo.complete_run(
        run_db_id,
        success=(status == "success"),
        result=result,
        error=error_msg,
        completed_at=completed_at,
    )
    logger.debug(f"Wrote run record to database: run_id={run_id}, task_id={task_id}")


# ==================== Auto-import Handlers ====================
# Import all handlers to ensure they are registered at module load time
try:
    from application.services import scheduler_handlers  # noqa: F401
    logger.info(f"Loaded {len(JOB_HANDLERS)} job handlers")
except ImportError as e:
    logger.warning(f"Failed to import scheduler_handlers: {e}")
