"""Webhook 调度不得把事件循环冻住（2026-10-21 w-36c3225e 事故复现与修复验证）。

事故（实测证据，见 docs/work-logs 归档）：
  Agent OS 触发 kline_update → POST /internal/scheduler/webhook →
  background_tasks.add_task(execute_job, ...) → execute_job 里
  `await handler(payload.metadata)` 把协程**直接 await 在 uvicorn 事件循环
  线程上** → handler 是 async 壳但内部调**同步**的
  kline_update_job.execute() → update_gem_klines() 逐只 `time.sleep(0.3~0.8)`
  + 同步 HTTP（5277 只实测约 1.7s/只 ⇒ 单次约 2.5 小时）。
  ⇒ 事件循环被同步 sleep 冻结，accept 循环停摆，**连 TCP 握手都完成不了**：
  /health、/metrics、/docs、/openapi.json 全部超时（curl 返回 000），
  全站失聪 2.5 小时。

  本文件守两件事：
  1. **async handler 必须在事件循环线程之外执行**（硬指标，不依赖时序）；
  2. **事件循环在 handler 阻塞期间仍能调度其它协程**（真实可观测行为）。

  ⚠️ 既有 tests/api/test_scheduler_webhook.py 里有一个同名的
  "keeps_loop_responsive" 测试，但它的计时窗口开在 `await asyncio.sleep(0)`
  **之后**——而阻塞恰恰发生在那一轮里，于是它量到的是"阻塞结束后的
  0.05s"，**假通过**（2026-10-21 实测：修复前该测试 8/8 全绿，
  而 handler 实际跑在事件循环线程上）。本文件的用例刻意避开这个陷阱：
  计时窗口覆盖 handler 的**整个执行期**，并额外用线程号做无时序依赖的断言。
"""
import asyncio
import threading
import time

import pytest

from api.internal import scheduler_webhook as wh


class _FakeAgentOSClient:
    def __init__(self):
        self.reports = []

    async def report_job_result(self, run_id, result):
        self.reports.append((run_id, result))
        return {}


@pytest.fixture
def isolated_side_effects(monkeypatch):
    """把 execute_job 的两个副作用（写库 / 回报 Agent OS）隔离开。"""
    fake_client = _FakeAgentOSClient()

    async def fake_write_run_to_database(**kwargs):
        return None

    monkeypatch.setattr(wh, "_write_run_to_database", fake_write_run_to_database)
    monkeypatch.setattr(
        "qs_agenthub.application.services.agent_os_client.get_agent_os_client",
        lambda: fake_client,
    )
    return fake_client


def _payload():
    return wh.WebhookPayload(
        job_id="00000000-0000-0000-0000-000000000000",
        job_name="kline_update",
        trigger_time="2026-10-21T17:40:00+00:00",
        metadata={"job_type": "kline_update", "run_id": "agent-os-run-1"},
    )


# ==================== 硬指标：线程隔离 ====================


def test_async_handler_runs_off_the_event_loop_thread(isolated_side_effects):
    """async handler 必须在事件循环线程之外跑。

    这是本次事故的**充分条件**：handler 内部只要有同步阻塞（time.sleep /
    同步 requests / 同步 psycopg2），跑在事件循环线程上就等于冻住整个服务。
    断言用线程号而非时序——时序断言会被"阻塞已结束"的测量窗口骗过
    （既有测试就是这样假通过的）。
    """
    seen = {}

    async def blocking_handler(metadata):
        seen["handler_thread"] = threading.get_ident()
        time.sleep(0.2)  # 同步阻塞，模拟 update_gem_klines 的 time.sleep
        return {"ok": True}

    loop_thread = {}

    async def main():
        loop_thread["id"] = threading.get_ident()
        await wh.execute_job(blocking_handler, _payload())

    asyncio.run(main())

    assert seen["handler_thread"] != loop_thread["id"], (
        "async handler 跑在了事件循环线程上——它内部的同步阻塞会冻住整个 "
        "FastAPI 服务（2026-10-21 事故：kline_update 跑 2.5 小时，全站 /health 超时）"
    )


def test_sync_handler_runs_off_the_event_loop_thread(isolated_side_effects):
    """同步 handler 同样必须在事件循环线程之外跑（回归护栏）。"""
    seen = {}

    def blocking_handler(metadata):
        seen["handler_thread"] = threading.get_ident()
        time.sleep(0.05)
        return {"ok": True}

    loop_thread = {}

    async def main():
        loop_thread["id"] = threading.get_ident()
        await wh.execute_job(blocking_handler, _payload())

    asyncio.run(main())

    assert seen["handler_thread"] != loop_thread["id"]


# ==================== 真实可观测：循环仍能调度 ====================


def test_event_loop_stays_responsive_during_blocking_handler(isolated_side_effects):
    """handler 阻塞期间，事件循环必须还能调度其它协程。

    计时窗口覆盖 handler 的**整个执行期**——这是与既有"假通过"测试的
    关键差别：那个测试在 `await asyncio.sleep(0)` 之后才起表，而阻塞恰恰
    发生在那一轮里，量到的永远是阻塞结束后的时间。
    """
    handler_started = threading.Event()
    handler_may_finish = threading.Event()
    loop_thread = {}

    async def blocking_handler(metadata):
        handler_started.set()
        # 等主协程确认"我已经在计时了"再放行 —— 保证阻塞落在计时窗口内
        handler_may_finish.wait(timeout=5)
        time.sleep(0.3)
        return {"ok": True}

    async def main():
        loop_thread["id"] = threading.get_ident()
        t0 = time.monotonic()
        job = asyncio.create_task(wh.execute_job(blocking_handler, _payload()))

        # 等 handler 真的起来了（此时它正卡在 handler_may_finish.wait）
        deadline = time.monotonic() + 5
        while not handler_started.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.005)

        handler_may_finish.set()
        # 关键：计时从此刻开始，且**必须跨过 handler 的整个 0.3s 阻塞**
        ticks = 0
        while time.monotonic() - t0 < 0.45:
            await asyncio.sleep(0.01)
            ticks += 1
        elapsed = time.monotonic() - t0
        await job
        return elapsed, ticks

    elapsed, ticks = asyncio.run(main())

    assert ticks >= 20, (
        f"事件循环在 handler 阻塞期间只调度了 {ticks} 次 tick（应 ≥20）——"
        f"事件循环被冻住了（elapsed={elapsed:.3f}s）"
    )
    assert elapsed < 1.0, f"事件循环被阻塞了 {elapsed:.3f}s"


def test_real_kline_update_handler_shape_does_not_block_loop(isolated_side_effects):
    """用真实 handler 的形状（async 壳 + 同步 execute）复现事故形态。

    事故的 handler 形态是：`async def handle_kline_update(...)` 内部直接调
    **同步**的 `execute()`。本用例照抄这个形状，确认它不再冻住事件循环。
    """
    started = threading.Event()
    release = threading.Event()

    def sync_execute(**params):
        """模拟 update_gem_klines：同步 time.sleep 逐只处理。"""
        started.set()
        release.wait(timeout=5)
        time.sleep(0.25)
        return {"status": "success", "success": 5277}

    async def handle_like_real(metadata):
        return sync_execute(**(metadata or {}))

    async def main():
        t0 = time.monotonic()
        job = asyncio.create_task(
            wh.execute_job(handle_like_real, _payload())
        )
        deadline = time.monotonic() + 5
        while not started.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.005)
        release.set()
        ticks = 0
        while time.monotonic() - t0 < 0.4:
            await asyncio.sleep(0.01)
            ticks += 1
        await job
        return ticks

    ticks = asyncio.run(main())
    assert ticks >= 15, (
        f"真实形态的 handler 冻住了事件循环（只调度 {ticks} 次 tick）"
    )


# ==================== 契约不变 ====================


def test_handler_result_and_report_contract_preserved(isolated_side_effects):
    """修复不得改变 handler 的返回契约与回报内容。"""
    async def handler(metadata):
        return {"updated": 42, "status": "success"}

    asyncio.run(wh.execute_job(handler, _payload()))

    assert len(isolated_side_effects.reports) == 1
    run_id, result = isolated_side_effects.reports[0]
    assert run_id == "agent-os-run-1"
    assert result["status"] == "success"
    assert "updated" in result["output"]


def test_handler_exception_still_reported_as_failed(isolated_side_effects):
    """handler 抛错仍要如实报 failed（不能被线程池改造吞掉）。"""
    async def handler(metadata):
        raise RuntimeError("boom")

    asyncio.run(wh.execute_job(handler, _payload()))

    assert len(isolated_side_effects.reports) == 1
    _, result = isolated_side_effects.reports[0]
    assert result["status"] == "failed"
    assert "boom" in result["error"]


def test_async_handler_using_asyncio_to_thread_still_works(isolated_side_effects):
    """handler 内部使用 await asyncio.to_thread(...) 仍要正常。

    修复后 handler 跑在**新建的**事件循环里（线程池线程内 asyncio.run）。
    `asyncio.to_thread` 绑定的是**当前运行中的循环**，因此语义不变——
    这一点必须有测试兜住，否则将来有人把 asyncio.run 改回直接 await，
    这里会静默地挂到 uvicorn 的循环上。
    """
    captured = {}

    async def handler(metadata):
        def blocking():
            time.sleep(0.05)
            return threading.get_ident()

        tid = await asyncio.to_thread(blocking)
        captured["to_thread_tid"] = tid
        captured["handler_tid"] = threading.get_ident()
        return {"ok": True}

    async def main():
        captured["loop_tid"] = threading.get_ident()
        await wh.execute_job(handler, _payload())

    asyncio.run(main())

    # handler 自身在 worker 线程上跑
    assert captured["handler_tid"] != captured["loop_tid"]
    # to_thread 派出的线程也不是事件循环线程（说明绑定到了新建的循环，
    # 且该循环确实在跑——否则 to_thread 会直接抛 RuntimeError）
    assert captured["to_thread_tid"] != captured["loop_tid"]
    assert captured["to_thread_tid"] is not None
