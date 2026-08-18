"""Agent OS HTTP client for Scheduler and Skill Hub.

This client provides a Python interface to the Agent OS HTTP API,
specifically for the Scheduler service.

Usage:
    from application.services.agent_os_client import get_agent_os_client

    client = get_agent_os_client()

    # Register a scheduled job
    job = await client.register_job({
        "name": "daily-kline-update",
        "cron": "40 17 * * 1-5",
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "enabled": True,
        "metadata": {"job_type": "kline_update"}
    })

    # List all jobs
    jobs = await client.list_jobs()

    # Report execution result
    await client.report_job_result(job_id, run_id, {
        "status": "success",
        "started_at": "2026-08-16T10:00:00Z",
        "completed_at": "2026-08-16T10:05:00Z"
    })
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class AgentOSClient:
    """Client for Agent OS HTTP API.

    Provides methods to interact with the Agent OS Scheduler service
    via HTTP. Supports task registration, management, triggering, and
    execution result reporting.

    The client uses httpx for async HTTP operations and maintains a
    persistent connection pool for efficiency.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        """Initialize Agent OS client.

        Args:
            base_url: Base URL for Agent OS HTTP API (default: http://127.0.0.1:8080)
        """
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True
        )
        logger.debug(f"AgentOSClient initialized with base_url={self.base_url}")

    async def close(self):
        """Close the HTTP client and release resources.

        Should be called when the client is no longer needed,
        typically in application shutdown handlers.
        """
        await self.client.aclose()
        logger.debug("AgentOSClient closed")

    # ==================== Scheduler API ====================

    async def register_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new scheduled job in Agent OS.

        Args:
            job: Job definition dictionary with keys:
                - name (str): Unique job name
                - cron (str): Cron expression (5-field or 6-field)
                - webhook_url (str): URL to call when job triggers
                - enabled (bool): Whether job is enabled
                - metadata (dict): Custom metadata/payload for webhook
                - timeout (int, optional): Timeout in seconds (default: 3600)
                - retry_count (int, optional): Max retry attempts (default: 0)

        Returns:
            Dict with registered job details including:
                - id (str): Job UUID
                - name (str): Job name
                - cron (str): Cron expression
                - enabled (bool): Enabled status
                - created_at (str): ISO timestamp

        Raises:
            httpx.HTTPStatusError: If registration fails (4xx/5xx)
        """
        logger.info(f"Registering job: {job.get('name')}")

        response = await self.client.post(
            f"{self.base_url}/api/v1/scheduler/tasks",
            json=job
        )
        response.raise_for_status()

        result = response.json()
        logger.info(f"Job registered: {result.get('name')} (id={result.get('id')})")
        return result

    async def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get details of a specific job.

        Args:
            job_id: Job UUID

        Returns:
            Job details dictionary

        Raises:
            httpx.HTTPStatusError: If job not found (404) or other error
        """
        response = await self.client.get(
            f"{self.base_url}/api/v1/scheduler/tasks/{job_id}"
        )
        response.raise_for_status()
        return response.json()

    async def list_jobs(self, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered jobs, optionally filtered by owner.

        Args:
            owner: Optional owner filter (e.g., "quantsys-v2")

        Returns:
            List of job dictionaries

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        params = {}
        if owner:
            params['owner'] = owner

        response = await self.client.get(
            f"{self.base_url}/api/v1/scheduler/tasks",
            params=params
        )
        response.raise_for_status()

        result = response.json()
        # Agent OS returns {"count": N, "tasks": [...]}
        tasks = result.get('tasks', []) if isinstance(result, dict) else result
        logger.debug(f"Listed {len(tasks)} jobs")
        return tasks

    async def update_job(
        self,
        job_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing job's configuration.

        Args:
            job_id: Job UUID
            updates: Dictionary of fields to update (name, cron, enabled, etc.)

        Returns:
            Updated job details

        Raises:
            httpx.HTTPStatusError: If job not found (404) or update fails
        """
        logger.info(f"Updating job {job_id}: {list(updates.keys())}")

        response = await self.client.put(
            f"{self.base_url}/api/v1/scheduler/tasks/{job_id}",
            json=updates
        )
        response.raise_for_status()

        result = response.json()
        logger.info(f"Job updated: {job_id}")
        return result

    async def delete_job(self, job_id: str) -> None:
        """Delete a job from the scheduler.

        Args:
            job_id: Job UUID

        Raises:
            httpx.HTTPStatusError: If job not found (404) or deletion fails
        """
        logger.info(f"Deleting job: {job_id}")

        response = await self.client.delete(
            f"{self.base_url}/api/v1/scheduler/tasks/{job_id}"
        )
        response.raise_for_status()

        logger.info(f"Job deleted: {job_id}")

    async def trigger_job(self, job_id: str) -> Dict[str, Any]:
        """Manually trigger a job execution immediately.

        Args:
            job_id: Job UUID

        Returns:
            Trigger result with execution details

        Raises:
            httpx.HTTPStatusError: If job not found (404) or trigger fails
        """
        logger.info(f"Triggering job: {job_id}")

        response = await self.client.post(
            f"{self.base_url}/api/v1/scheduler/tasks/{job_id}/trigger"
        )
        response.raise_for_status()

        result = response.json()
        logger.info(f"Job triggered: {job_id}")
        return result

    async def pause_job(self, job_id: str) -> Dict[str, Any]:
        """Pause a job (sets enabled=false).

        Args:
            job_id: Job UUID

        Returns:
            Updated job details

        Raises:
            httpx.HTTPStatusError: If job not found (404) or pause fails
        """
        logger.info(f"Pausing job: {job_id}")

        response = await self.client.post(
            f"{self.base_url}/api/v1/scheduler/tasks/{job_id}/pause"
        )
        response.raise_for_status()

        result = response.json()
        logger.info(f"Job paused: {job_id}")
        return result

    async def resume_job(self, job_id: str) -> Dict[str, Any]:
        """Resume a paused job (sets enabled=true).

        Args:
            job_id: Job UUID

        Returns:
            Updated job details

        Raises:
            httpx.HTTPStatusError: If job not found (404) or resume fails
        """
        logger.info(f"Resuming job: {job_id}")

        response = await self.client.post(
            f"{self.base_url}/api/v1/scheduler/tasks/{job_id}/resume"
        )
        response.raise_for_status()

        result = response.json()
        logger.info(f"Job resumed: {job_id}")
        return result

    async def report_job_result(
        self,
        job_id: str,
        run_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Report job execution result back to Agent OS.

        This is called after a webhook execution completes to inform
        Agent OS of the outcome.

        Args:
            job_id: Job UUID
            run_id: Run UUID (generated by quantsys-v2)
            result: Result dictionary with keys:
                - status (str): "success" or "failed"
                - started_at (str): ISO timestamp
                - completed_at (str): ISO timestamp
                - error_message (str, optional): Error details if failed

        Raises:
            httpx.HTTPStatusError: If report fails
        """
        logger.debug(f"Reporting result for job {job_id}, run {run_id}")

        response = await self.client.post(
            f"{self.base_url}/api/v1/scheduler/tasks/{job_id}/runs/{run_id}",
            json=result
        )
        response.raise_for_status()

        logger.debug(f"Result reported: {job_id}/{run_id} - {result.get('status')}")

    async def list_executions(
        self,
        task_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List job execution history.

        Args:
            task_id: Optional task UUID to filter by
            limit: Maximum number of results (default: 50)

        Returns:
            List of execution records

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        params = {'limit': limit}
        if task_id:
            params['task_id'] = task_id

        response = await self.client.get(
            f"{self.base_url}/api/v1/scheduler/executions",
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def get_task_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics.

        Returns:
            Statistics dictionary with counts and metrics

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        response = await self.client.get(
            f"{self.base_url}/api/v1/scheduler/tasks/stats"
        )
        response.raise_for_status()
        return response.json()


# ==================== Global Singleton ====================

_agent_os_client: Optional[AgentOSClient] = None


def get_agent_os_client(base_url: str = "http://127.0.0.1:8080") -> AgentOSClient:
    """Get global Agent OS client instance.

    Returns a singleton client that is reused across the application.
    The client maintains a persistent HTTP connection pool.

    Args:
        base_url: Base URL for Agent OS (default: http://127.0.0.1:8080)

    Returns:
        AgentOSClient instance
    """
    global _agent_os_client
    if _agent_os_client is None:
        _agent_os_client = AgentOSClient(base_url=base_url)
    return _agent_os_client


async def close_agent_os_client():
    """Close the global Agent OS client.

    Should be called during application shutdown to release resources.
    """
    global _agent_os_client
    if _agent_os_client is not None:
        await _agent_os_client.close()
        _agent_os_client = None
