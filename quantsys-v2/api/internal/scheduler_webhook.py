from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

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


def _get_job_registry():
    from application.jobs.job_registry import job_registry
    return job_registry


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

    registry = _get_job_registry()
    job = registry.get(job_type)
    if not job:
        available = list(registry.list_jobs().keys())
        logger.error(
            f"Unknown job_type '{job_type}' for job {payload.job_name}. "
            f"Available jobs: {available}"
        )
        raise HTTPException(
            status_code=404, detail=f"Unknown job_type: {job_type}"
        )

    logger.info(
        f"Received webhook for job '{payload.job_name}' (type={job_type}, "
        f"job_id={payload.job_id})"
    )

    background_tasks.add_task(execute_job, job_type, payload)

    return WebhookResponse(
        status="accepted",
        job_id=payload.job_id,
        job_name=payload.job_name,
        message=f"Job execution started for {job_type}",
    )


# ==================== Background Execution ====================


async def execute_job(job_type: str, payload: WebhookPayload):
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)

    logger.info(
        f"Executing job '{payload.job_name}' (run_id={run_id}, "
        f"job_id={payload.job_id})"
    )

    try:
        registry = _get_job_registry()
        job_result = await registry.execute(job_type, payload.metadata)
        status = "success" if job_result.success else "failed"
        error_msg = job_result.error
        result = {
            "action": job_result.action,
            "message": job_result.message,
            "details": job_result.details,
        }
        if job_result.success:
            logger.info(f"Job '{payload.job_name}' succeeded (run_id={run_id})")
        else:
            logger.warning(f"Job '{payload.job_name}' failed (run_id={run_id}): {error_msg}")
    except Exception as e:
        logger.exception(f"Job '{payload.job_name}' failed with exception (run_id={run_id})")
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
            # This maintains compatibility with existing schema.
            # MUST be is_enabled=false: the legacy SchedulerService polls
            # `WHERE is_enabled = true` and would execute the placeholder
            # (cron 'managed_by_agent_os') as junk runs (2026-08-18).
            cursor.execute(
                """
                INSERT INTO quant.scheduler_tasks
                    (name, description, cron_expression, command, params, is_enabled)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET updated_at = now()
                RETURNING id
                """,
                (
                    job_name,
                    f"Agent OS managed job (job_id={job_id})",
                    "managed_by_agent_os",  # Placeholder cron
                    "agent_os_webhook",  # Placeholder command
                    json.dumps({"job_id": job_id, "managed_by": "agent_os"}),
                    False,
                ),
            )
            task_id = cursor.fetchone()["id"]

        # Insert run record — id is a bigint identity column, let the
        # sequence assign it (the uuid run_id must NOT go into it;
        # 2026-08-18: InvalidTextRepresentation killed every local write)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        result_json = json.dumps(result) if result else None

        cursor.execute(
            """
            INSERT INTO quant.scheduler_runs
                (task_id, status, started_at, completed_at, duration_ms, result, error)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
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
