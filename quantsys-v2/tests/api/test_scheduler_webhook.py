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
    async def report_job_result(self, job_id, run_id, result):
        return {}


@pytest.fixture
def isolated_side_effects(monkeypatch):
    """Keep execute_job away from the DB and the network."""
    async def fake_write_run_to_database(**kwargs):
        return None

    monkeypatch.setattr(wh, "_write_run_to_database", fake_write_run_to_database)
    monkeypatch.setattr(
        "application.services.agent_os_client.get_agent_os_client",
        lambda: _FakeAgentOSClient(),
    )


def _make_payload():
    return wh.WebhookPayload(
        job_id="00000000-0000-0000-0000-000000000000",
        job_name="test_job",
        trigger_time="2026-08-18T12:00:00+00:00",
        metadata={"job_type": "test"},
    )


def test_execute_job_runs_handler_off_the_event_loop_thread(isolated_side_effects):
    """Blocking handler must run on a worker thread, not the loop thread."""
    seen = {}

    async def blocking_handler(metadata):
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
        assert metadata == {"job_type": "test"}
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
