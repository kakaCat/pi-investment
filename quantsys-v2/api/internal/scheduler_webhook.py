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

    if not job_type:
        logger.error(f"Webhook payload missing job_type: {payload.model_dump()}")
        raise HTTPException(
            status_code=400, detail="Missing job_type in metadata"
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


def _run_handler_blocking(handler: Callable, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Run an async job handler in a worker thread with its own event loop.

    Job handlers do blocking synchronous work (HTTP requests, psycopg2,
    data providers) inside `async def` bodies. Awaiting them directly on
    the FastAPI event loop stalls the entire service for the job's whole
    duration — including the webhook response back to Agent OS (2026-08-18
    incident: 10-minute data quality job made Agent OS time out and
    misrecord a successful job as failed).
    """
    return asyncio.run(handler(metadata))


async def execute_job(handler: Callable, payload: WebhookPayload):
    """Execute job handler and report results to Agent OS.

    This runs in a FastAPI background task to avoid blocking the
    webhook response. It:
    1. Generates a run_id
    2. Calls the job handler
    3. Writes run record to local database
    4. Reports result back to Agent OS

    Args:
        handler: The async job handler function
        payload: Webhook payload from Agent OS
    """
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)

    logger.info(
        f"Executing job '{payload.job_name}' (run_id={run_id}, "
        f"job_id={payload.job_id})"
    )

    try:
        # Call the job handler with metadata — off the event loop, since
        # handlers do blocking sync work (see _run_handler_blocking)
        result = await run_in_threadpool(_run_handler_blocking, handler, payload.metadata)
        status = "success"
        error_msg = None
        logger.info(
            f"Job '{payload.job_name}' succeeded (run_id={run_id}): {result}"
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

    # Report back to Agent OS
    try:
        from application.services.agent_os_client import get_agent_os_client

        agent_os_client = get_agent_os_client()
        await agent_os_client.report_job_result(
            payload.job_id,
            run_id,
            {
                "status": status,
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "error_message": error_msg,
            },
        )
        logger.debug(
            f"Reported result to Agent OS: job_id={payload.job_id}, "
            f"run_id={run_id}, status={status}"
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
    """Write run record to local PostgreSQL database.

    This maintains local audit trail of all job executions, even when
    executed via Agent OS scheduler.

    Args:
        run_id: Run UUID (generated locally)
        job_id: Job UUID from Agent OS
        job_name: Human-readable job name
        status: "success" or "failed"
        started_at: Execution start time
        completed_at: Execution end time
        result: Job result dictionary
        error_msg: Error message if failed
    """
    import json

    import psycopg2
    from psycopg2.extras import RealDictCursor

    from infrastructure.persistence.database.engine import get_engine

    engine = get_engine()
    conn = engine.raw_connection()

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # We need to get or create a task_id for the scheduler_runs table
        # First, check if a task exists with this job name
        cursor.execute(
            "SELECT id FROM quant.scheduler_tasks WHERE name = %s", (job_name,)
        )
        row = cursor.fetchone()

        if row:
            task_id = row["id"]
        else:
            # Create a placeholder task for Agent OS jobs
            # This maintains compatibility with existing schema
            cursor.execute(
                """
                INSERT INTO quant.scheduler_tasks
                    (name, description, cron_expression, command, params)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET updated_at = now()
                RETURNING id
                """,
                (
                    job_name,
                    f"Agent OS managed job (job_id={job_id})",
                    "managed_by_agent_os",  # Placeholder cron
                    "agent_os_webhook",  # Placeholder command
                    json.dumps({"job_id": job_id, "managed_by": "agent_os"}),
                ),
            )
            task_id = cursor.fetchone()["id"]

        # Insert run record
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        result_json = json.dumps(result) if result else None

        cursor.execute(
            """
            INSERT INTO quant.scheduler_runs
                (id, task_id, status, started_at, completed_at, duration_ms, result, error)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                task_id,
                status,
                started_at,
                completed_at,
                duration_ms,
                result_json,
                error_msg,
            ),
        )

        # Update task's last run status
        cursor.execute(
            """
            UPDATE quant.scheduler_tasks
            SET last_run_at = %s, last_status = %s, last_error = %s, updated_at = now()
            WHERE id = %s
            """,
            (started_at, status, error_msg, task_id),
        )

        conn.commit()
        logger.debug(f"Wrote run record to database: run_id={run_id}, task_id={task_id}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Database write failed: {e}", exc_info=True)
        raise
    finally:
        if cursor:
            cursor.close()
        conn.close()


# ==================== Auto-import Handlers ====================
# Import all handlers to ensure they are registered at module load time
try:
    from application.services import scheduler_handlers  # noqa: F401
    logger.info(f"Loaded {len(JOB_HANDLERS)} job handlers")
except ImportError as e:
    logger.warning(f"Failed to import scheduler_handlers: {e}")
