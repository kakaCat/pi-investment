"""Tests for the Agent OS scheduler webhook receiver.

Focus: job handlers do blocking synchronous work (requests, psycopg2,
data providers). They must NOT run on the FastAPI event loop, otherwise
the whole 5001 service (including the webhook HTTP response back to
Agent OS) is stuck for the entire job duration — observed 2026-08-18
when a 10-minute data_quality_check caused Agent OS to time out and
misrecord a successful job as failed.
"""
import asyncio
import threading
import time

import pytest

from api.internal import scheduler_webhook as wh


class _FakeAgentOSClient:
    """Captures report_job_result calls for assertions."""

    def __init__(self):
        self.reports = []

    async def report_job_result(self, run_id, result):
        self.reports.append((run_id, result))
        return {}


@pytest.fixture
def fake_agent_os_client():
    return _FakeAgentOSClient()


@pytest.fixture
def isolated_side_effects(monkeypatch, fake_agent_os_client):
    """Keep execute_job away from the DB and the network."""
    async def fake_write_run_to_database(**kwargs):
        return None

    monkeypatch.setattr(wh, "_write_run_to_database", fake_write_run_to_database)
    monkeypatch.setattr(
        "application.services.agent_os_client.get_agent_os_client",
        lambda: fake_agent_os_client,
    )


def _make_payload(metadata=None):
    base = {"job_type": "test", "run_id": "agent-os-run-123"}
    if metadata:
        base.update(metadata)
    return wh.WebhookPayload(
        job_id="00000000-0000-0000-0000-000000000000",
        job_name="test_job",
        trigger_time="2026-08-18T12:00:00+00:00",
        metadata=base,
    )


def test_execute_job_runs_handler_off_the_event_loop_thread(isolated_side_effects):
    """Blocking handler must run on a worker thread, not the loop thread."""
    seen = {}

    def blocking_handler(metadata):
        seen["handler_thread"] = threading.get_ident()
        time.sleep(0.1)  # sync blocking work, like real handlers
        return {"ok": True}

    loop_thread = {}

    async def main():
        loop_thread["id"] = threading.get_ident()
        await wh.execute_job(blocking_handler, _make_payload())

    asyncio.run(main())

    assert seen["handler_thread"] != loop_thread["id"], (
        "handler ran on the event loop thread — blocking work would stall "
        "the whole FastAPI service"
    )


def test_execute_job_keeps_loop_responsive_while_handler_blocks(isolated_side_effects):
    """While a handler blocks, other coroutines must keep being served."""

    async def blocking_handler(metadata):
        time.sleep(0.5)
        return {"ok": True}

    async def main():
        job = asyncio.create_task(wh.execute_job(blocking_handler, _make_payload()))
        await asyncio.sleep(0)  # let the job start
        start = time.monotonic()
        # 5 event-loop ticks; with a blocked loop these would only run
        # after the 0.5s handler finishes
        for _ in range(5):
            await asyncio.sleep(0.01)
        elapsed = time.monotonic() - start
        await job
        return elapsed

    elapsed = asyncio.run(main())
    assert elapsed < 0.4, f"event loop was blocked for {elapsed:.2f}s by the handler"


def test_execute_job_returns_handler_result(isolated_side_effects):
    """Threadpool execution must not change the handler contract."""
    captured = {}

    async def fake_write_run_to_database(**kwargs):
        captured.update(kwargs)

    async def handler(metadata):
        assert metadata["job_type"] == "test"
        return {"updated": 42}

    # Re-patch with capturing version
    import api.internal.scheduler_webhook as module
    original = module._write_run_to_database
    module._write_run_to_database = fake_write_run_to_database
    try:
        asyncio.run(wh.execute_job(handler, _make_payload()))
    finally:
        module._write_run_to_database = original

    assert captured["status"] == "success"
    assert captured["result"] == {"updated": 42}


# ==================== Result reporting back to Agent OS ====================
#
# The scheduler's own run record only tracks "webhook accepted" (the
# receiver responds immediately). The REAL job outcome must be reported
# back via PUT /api/v1/scheduler/executions/{run_id} using the Agent OS
# run_id carried in payload.metadata["run_id"] — otherwise failed jobs
# show as success on the Agent OS side (2026-08-18: the report path
# previously POSTed to a non-existent /tasks/{id}/runs/{id} route → 404).


def test_execute_job_reports_success_with_agent_os_run_id(
    isolated_side_effects, fake_agent_os_client
):
    async def handler(metadata):
        return {"updated": 7}

    asyncio.run(wh.execute_job(handler, _make_payload()))

    assert len(fake_agent_os_client.reports) == 1
    run_id, result = fake_agent_os_client.reports[0]
    assert run_id == "agent-os-run-123"  # Agent OS run id, NOT the local one
    assert result["status"] == "success"
    assert "updated" in result["output"]


def test_execute_job_reports_failure_with_error(
    isolated_side_effects, fake_agent_os_client
):
    async def handler(metadata):
        raise RuntimeError("boom")

    asyncio.run(wh.execute_job(handler, _make_payload()))

    assert len(fake_agent_os_client.reports) == 1
    run_id, result = fake_agent_os_client.reports[0]
    assert run_id == "agent-os-run-123"
    assert result["status"] == "failed"
    assert "boom" in result["error"]


def test_execute_job_skips_report_when_run_id_missing(
    isolated_side_effects, fake_agent_os_client
):
    """Payloads from older executors lack metadata.run_id — never 404-spam."""

    async def handler(metadata):
        return {"ok": True}

    payload = _make_payload()
    payload.metadata.pop("run_id")
    asyncio.run(wh.execute_job(handler, payload))

    assert fake_agent_os_client.reports == []


# ==================== Agent OS client singleton self-healing ====================
#
# register_jobs_to_agent_os.py closes the shared client directly
# (client.close() instead of close_agent_os_client()), leaving the global
# singleton pointing at a CLOSED httpx client. Every later
# get_agent_os_client() returned it → "Cannot send a request, as the
# client has been closed" on every job result report (2026-08-18 13:00).


def test_get_agent_os_client_recreates_a_closed_singleton():
    from application.services import agent_os_client as client_mod

    c1 = client_mod.get_agent_os_client()
    asyncio.run(c1.client.aclose())  # simulate the register-script bug
    assert c1.client.is_closed

    c2 = client_mod.get_agent_os_client()
    try:
        assert c2 is not c1
        assert not c2.client.is_closed
    finally:
        asyncio.run(c2.client.aclose())
        client_mod._agent_os_client = None


# ==================== Local run record write ====================


def test_write_run_to_database_persists_run():
    """Regression: run_id (uuid) must NOT be inserted into the bigint id
    column — psycopg2 InvalidTextRepresentation killed the local audit
    write for every Agent OS job."""
    from datetime import datetime, timezone

    from psycopg2.extras import RealDictCursor

    from infrastructure.persistence.database.engine import get_engine

    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        asyncio.run(
            wh._write_run_to_database(
                run_id="11111111-2222-3333-4444-555555555555",
                job_id="00000000-0000-0000-0000-000000000000",
                job_name="pytest_webhook_probe",
                status="success",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                result={"probe": True},
                error_msg=None,
            )
        )
        cursor.execute(
            "SELECT status FROM quant.scheduler_runs "
            "WHERE result->>'probe' = 'true' ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        assert row is not None, "run record was not persisted"
        assert row["status"] == "success"

        # The auto-created placeholder task must be DISABLED — the legacy
        # SchedulerService polls `WHERE is_enabled = true`, and an enabled
        # placeholder (cron 'managed_by_agent_os') gets executed as junk
        # 'running' rows by the local scheduler (2026-08-18, task 276).
        cursor.execute(
            "SELECT is_enabled FROM quant.scheduler_tasks "
            "WHERE name = 'pytest_webhook_probe'"
        )
        task_row = cursor.fetchone()
        assert task_row is not None
        assert task_row["is_enabled"] is False

        # cleanup
        cursor.execute("DELETE FROM quant.scheduler_runs WHERE result->>'probe' = 'true'")
        cursor.execute("DELETE FROM quant.scheduler_tasks WHERE name = 'pytest_webhook_probe'")
        conn.commit()
    finally:
        conn.close()
