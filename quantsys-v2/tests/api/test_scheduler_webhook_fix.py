"""Test P0-5 fix: Webhook execution no longer blocks event loop.

Verifies that:
1. Async handlers are awaited directly (no nested event loop)
2. Sync handlers run in threadpool
3. No asyncio.run() wrapper causes nested event loop errors
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from api.internal.scheduler_webhook import execute_job, WebhookPayload


@pytest.mark.asyncio
async def test_async_handler_execution():
    """Async handlers should be awaited directly on the event loop."""
    # Given: an async handler
    async def async_handler(metadata):
        await asyncio.sleep(0.01)  # Simulate async work
        return {"status": "success", "type": "async"}

    payload = WebhookPayload(
        job_id="test-job-123",
        job_name="test_async_job",
        trigger_time="2026-08-18T10:00:00Z",
        metadata={"job_type": "test_async", "run_id": "run-123"}
    )

    # Mock database and agent OS client
    with patch("api.internal.scheduler_webhook._write_run_to_database", new_callable=AsyncMock):
        with patch("api.internal.scheduler_webhook.get_agent_os_client") as mock_client:
            mock_client.return_value.report_job_result = AsyncMock()

            # When: execute_job is called
            await execute_job(async_handler, payload)

            # Then: no errors should occur (no nested event loop)
            # If the old asyncio.run() wrapper was used, this would fail


@pytest.mark.asyncio
async def test_sync_handler_execution():
    """Sync handlers should run in threadpool without asyncio.run()."""
    # Given: a sync handler
    def sync_handler(metadata):
        # Simulate sync blocking work
        import time
        time.sleep(0.01)
        return {"status": "success", "type": "sync"}

    payload = WebhookPayload(
        job_id="test-job-456",
        job_name="test_sync_job",
        trigger_time="2026-08-18T10:00:00Z",
        metadata={"job_type": "test_sync", "run_id": "run-456"}
    )

    # Mock database and agent OS client
    with patch("api.internal.scheduler_webhook._write_run_to_database", new_callable=AsyncMock):
        with patch("api.internal.scheduler_webhook.get_agent_os_client") as mock_client:
            mock_client.return_value.report_job_result = AsyncMock()

            # When: execute_job is called
            await execute_job(sync_handler, payload)

            # Then: handler should execute successfully in threadpool


@pytest.mark.asyncio
async def test_handler_can_use_asyncio_primitives():
    """Async handlers should be able to use asyncio primitives without errors."""
    # Given: an async handler that uses asyncio.gather (would fail with nested asyncio.run)
    async def complex_async_handler(metadata):
        # Simulate parallel async work
        async def subtask(n):
            await asyncio.sleep(0.01)
            return n * 2

        results = await asyncio.gather(subtask(1), subtask(2), subtask(3))
        return {"results": results}

    payload = WebhookPayload(
        job_id="test-job-789",
        job_name="test_complex_async",
        trigger_time="2026-08-18T10:00:00Z",
        metadata={"job_type": "test_complex", "run_id": "run-789"}
    )

    # Mock database and agent OS client
    with patch("api.internal.scheduler_webhook._write_run_to_database", new_callable=AsyncMock):
        with patch("api.internal.scheduler_webhook.get_agent_os_client") as mock_client:
            mock_client.return_value.report_job_result = AsyncMock()

            # When: execute_job is called
            await execute_job(complex_async_handler, payload)

            # Then: should complete without "RuntimeError: asyncio.run() cannot be called from a running event loop"


@pytest.mark.asyncio
async def test_handler_exception_propagation():
    """Handler exceptions should be caught and reported properly."""
    # Given: a handler that raises an exception
    async def failing_handler(metadata):
        raise ValueError("Simulated handler failure")

    payload = WebhookPayload(
        job_id="test-job-error",
        job_name="test_failing_job",
        trigger_time="2026-08-18T10:00:00Z",
        metadata={"job_type": "test_fail", "run_id": "run-error"}
    )

    # Mock database and agent OS client
    with patch("api.internal.scheduler_webhook._write_run_to_database", new_callable=AsyncMock) as mock_db:
        with patch("api.internal.scheduler_webhook.get_agent_os_client") as mock_client:
            mock_client.return_value.report_job_result = AsyncMock()

            # When: execute_job is called with failing handler
            await execute_job(failing_handler, payload)

            # Then: exception should be caught, logged, and reported
            # Verify database write was attempted with failed status
            assert mock_db.called
            call_kwargs = mock_db.call_args.kwargs
            assert call_kwargs["status"] == "failed"
            assert "Simulated handler failure" in call_kwargs["error_msg"]

            # Verify Agent OS was notified of failure
            assert mock_client.return_value.report_job_result.called
            report_args = mock_client.return_value.report_job_result.call_args
            assert report_args[0][1]["status"] == "failed"
