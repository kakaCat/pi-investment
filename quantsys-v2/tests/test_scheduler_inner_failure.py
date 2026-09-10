"""调度器「内层失败」判定回归测试（P0-B，2026-09-10 w-23c70356）。

背景（审计发现）：调度器 run 状态原本只看「有没有抛异常」——handler 用返回值报告
失败（返回 dict，不抛异常）时 run 仍写 success，真实失败只躺在 scheduler_runs.result
里；看门狗 v2_health_check 的失败率统计同源失真，一路报 ok。
实证：market_perception_daily 2026-09-07~09-10 连续 4 个工作日空转（AttributeError，
耗时 3~10ms），4 条 run 全 success；2026-06-04 起同类静默失败共 40 条。

本文件是故障注入测试：把 handler 的失败返回值注入真实执行路径，断言 run 记录变为
failed。修复前（硬编码 status="success" / 只认 status=='failed'）这些用例必失败。
"""
from __future__ import annotations

import asyncio

import pytest

from api.internal import scheduler_webhook as wh
from infrastructure.scheduler.job_executor import classify_job_result


# --------------------------- 判定口径（单一真源） ---------------------------


@pytest.mark.parametrize(
    "result,expected_failed",
    [
        # scheduler_handlers 风格：{"success": bool, "error": ...}
        ({"success": False, "error": "boom"}, True),
        ({"success": False}, True),
        ({"success": False, "message": "partial failure"}, True),
        # JobRegistry / legacy 风格：{"status": "failed"|"error", ...}
        ({"status": "failed", "error": "x"}, True),
        ({"status": "error"}, True),
        ({"status": "FAILED"}, True),
        # 裸错误返回（无 status / success）
        ({"error": "some error"}, True),
        # 正常返回一律不能误判为失败
        ({"success": True, "trade_date": "2026-09-10"}, False),
        ({"status": "success", "error": None}, False),
        ({"status": "success"}, False),
        ({"error": None}, False),
        ({"updated": 0, "skipped": True}, False),
        ({}, False),
        (None, False),
        ("ok", False),
        ([], False),
    ],
)
def test_classify_job_result(result, expected_failed):
    assert (classify_job_result(result) is not None) is expected_failed


# --------------------------- webhook 执行路径 ---------------------------


def _execute_job_capturing_write(handler, monkeypatch):
    """跑真实 execute_job，只把「写库」换成捕获（不碰 DB / 不碰网络）。"""
    captured = {}

    async def fake_write_run_to_database(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(wh, "_write_run_to_database", fake_write_run_to_database)

    payload = wh.WebhookPayload(
        job_id="job-fault-inject",
        job_name="fault_inject",
        trigger_time="2026-09-10T15:30:00+08:00",
        metadata={},  # 无 run_id → 不再回报 Agent OS（本用例只关心库内记录）
    )
    asyncio.run(wh.execute_job(handler, payload))
    return captured


def test_execute_job_records_inner_failure_as_failed(monkeypatch):
    """故障注入：handler 返回 success=false（不抛异常）→ run 必须记 failed。"""

    async def failing_handler(metadata):
        return {
            "success": False,
            "error": "MarketPerceptionService object has no attribute 'regime_daily'",
        }

    rec = _execute_job_capturing_write(failing_handler, monkeypatch)
    assert rec.get("status") == "failed", "内层失败被写成了 success（本次修复的缺陷）"
    assert "regime_daily" in (rec.get("error_msg") or "")
    assert rec["result"]["success"] is False


def test_execute_job_records_failed_status_style(monkeypatch):
    async def failing_handler(metadata):
        return {"status": "failed", "error": "kline sync failed"}

    rec = _execute_job_capturing_write(failing_handler, monkeypatch)
    assert rec.get("status") == "failed"
    assert "kline sync failed" in (rec.get("error_msg") or "")


def test_execute_job_keeps_success_for_real_success(monkeypatch):
    async def ok_handler(metadata):
        return {"success": True, "trade_date": "2026-09-10", "error": None}

    rec = _execute_job_capturing_write(ok_handler, monkeypatch)
    assert rec.get("status") == "success"
    assert rec.get("error_msg") is None


def test_execute_job_exception_still_failed(monkeypatch):
    async def boom_handler(metadata):
        raise RuntimeError("kaboom")

    rec = _execute_job_capturing_write(boom_handler, monkeypatch)
    assert rec.get("status") == "failed"
    assert "kaboom" in (rec.get("error_msg") or "")


# --------------------------- market_perception_daily 任务 ---------------------------


def _patch_service(monkeypatch, service_factory):
    monkeypatch.setattr(
        "application.services.market_perception_service.MarketPerceptionService",
        service_factory,
    )


def test_market_perception_uses_run_daily_snapshot(monkeypatch):
    """回归：handler 必须调真实存在的 run_daily_snapshot（原来调不存在的 regime_daily）。"""
    from application.services import scheduler_handlers as sh

    calls = []

    class FakeService:
        def run_daily_snapshot(self, trade_date=None):
            calls.append(trade_date)
            return {
                "trade_date": "2026-09-10",
                "success": True,
                "all_steps_success": True,
                "failed_steps": None,
                "steps": {"sentiment": {"stored": True}, "regime": {"stored": True}},
            }

    _patch_service(monkeypatch, FakeService)

    out = asyncio.run(sh.handle_market_perception_daily({}))
    assert calls == [None], "未调用 run_daily_snapshot"
    assert out["success"] is True
    assert out["trade_date"] == "2026-09-10"
    assert out["failed_steps"] is None
    assert "steps" in out


def test_market_perception_partial_failure_is_surfaced(monkeypatch):
    """部分步骤未落库时：success=False + failed_steps 显式带出（不再静默）。"""
    from application.services import scheduler_handlers as sh

    class FakeService:
        def run_daily_snapshot(self, trade_date=None):
            return {
                "trade_date": "2026-09-10",
                "success": False,
                "all_steps_success": False,
                "failed_steps": ["regime", "themes"],
                "steps": {"sentiment": {"stored": False, "error": "kline 未同步"}},
            }

    _patch_service(monkeypatch, FakeService)

    out = asyncio.run(sh.handle_market_perception_daily({}))
    assert out["success"] is False
    assert out["failed_steps"] == ["regime", "themes"]


def test_market_perception_fault_injected_end_to_end(monkeypatch):
    """端到端故障注入：快照全步失败 → handler 返回 success=false → run 记 failed。"""
    from application.services import scheduler_handlers as sh

    class BrokenService:
        def run_daily_snapshot(self, trade_date=None):
            raise RuntimeError("db down")

    _patch_service(monkeypatch, BrokenService)

    rec = _execute_job_capturing_write(sh.handle_market_perception_daily, monkeypatch)
    assert rec.get("status") == "failed"
    assert "db down" in (rec.get("error_msg") or "")
