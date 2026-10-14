"""调度宽限语义与「被跳过」留痕测试（REQ-261004154902-a7cd · t5 / FR-4 / FR-8）。

覆盖验收标准：
- 时刻口径：`30 14 * * 1-5` 在本地时区（Asia/Shanghai）下必须落在 **14:30**（防 8 小时漂移回归）；
- misfire 语义：库值 NULL = **唤醒必补跑**（不再被 `or 300` 抹成 5 分钟），显式值才按期跳过；
- 「被跳过」必须落库：MISSED 事件要写成一条 `status='missed'` 的 `scheduler_runs`
  （此前只打一行纯文本 warning，库里查不到、`last_status` 还停在前几天的 success）。

全部用例零数据库、零网络：调度器、仓储与事件都用假对象。
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from infrastructure.scheduler.apscheduler_service import (
    APSchedulerService,
    parse_task_id_from_job_id,
    resolve_misfire_grace,
)
from infrastructure.scheduler.cron_compat import build_cron_trigger


# ── ① misfire 语义（纯函数）───────────────────────────────────────────────

@pytest.mark.parametrize("value", [None, 0, -1, "abc", ""])
def test_null_or_garbage_means_no_misfire_skip(value):
    """NULL / 脏值 = 唤醒必补跑（旧代码 `or 300` 会把它抹成 5 分钟）。"""
    assert resolve_misfire_grace(value) is None


@pytest.mark.parametrize("value,expected", [(300, 300), ("3600", 3600), (60.0, 60)])
def test_explicit_value_is_passed_through(value, expected):
    assert resolve_misfire_grace(value) == expected


# ── ② job_id → task_id ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "job_id,expected",
    [("task_249", 249), ("task_1", 1), ("task_x", None), ("249", None), (None, None), (249, None)],
)
def test_parse_task_id_from_job_id(job_id, expected):
    assert parse_task_id_from_job_id(job_id) == expected


# ── ③ 时刻口径：14:30 必须是本地 14:30 ────────────────────────────────────

def test_1430_cron_fires_at_local_1430():
    """回归锁：曾因时区口径从 UTC 变本地，库里的 `30 6` 静默变成 06:30 盘前。"""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Shanghai")
    trigger = build_cron_trigger("30 14 * * 1-5", tz="Asia/Shanghai")
    nxt = trigger.get_next_fire_time(None, datetime(2026, 10, 5, 0, 0, tzinfo=tz))

    assert nxt is not None
    assert (nxt.hour, nxt.minute) == (14, 30), f"实际落在 {nxt.isoformat()}"
    assert nxt.weekday() < 5, "必须是工作日（周一是 0）"


# ── ④ 装载器把 NULL 传成 None（不再回落 300 秒）──────────────────────────

class _FakeScheduler:
    def __init__(self):
        self.added = []

    def add_job(self, **kwargs):
        self.added.append(kwargs)


class _FakeRepo:
    def __init__(self, tasks):
        self._tasks = tasks
        self.missed_calls = []
        self.raise_on_missed = False

    def list_tasks(self, enabled_only=False):
        return self._tasks

    def count_tasks(self, enabled_only=False):
        return len(self._tasks)

    def record_missed_run(self, task_id, scheduled_run_time=None, note=None):
        if self.raise_on_missed:
            raise RuntimeError("db down")
        self.missed_calls.append(
            {"task_id": task_id, "scheduled_run_time": scheduled_run_time, "note": note}
        )
        return 42


def _service_with(tasks):
    service = object.__new__(APSchedulerService)
    service.repo = _FakeRepo(tasks)
    service.scheduler = _FakeScheduler()
    service.reconcile_jobs = lambda desired: 0  # 本用例只测装载
    return service


def _task(task_id=249, grace=None):
    return {
        "id": task_id,
        "name": "v13-simulation-trading",
        "cron_expression": "30 14 * * 1-5",
        "task_type": "cron",
        "params": {},
        "misfire_grace_time_seconds": grace,
    }


def test_loader_maps_null_grace_to_none():
    service = _service_with([_task(grace=None)])

    service.load_tasks_from_db()

    assert service.scheduler.added, "任务没被装载"
    assert service.scheduler.added[0]["misfire_grace_time"] is None


def test_loader_passes_explicit_grace_through():
    service = _service_with([_task(grace=300)])

    service.load_tasks_from_db()

    assert service.scheduler.added[0]["misfire_grace_time"] == 300


# ── ⑤ MISSED 事件必须落库 ─────────────────────────────────────────────────

def test_missed_event_is_recorded_as_run():
    service = _service_with([_task()])
    scheduled = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)
    event = SimpleNamespace(job_id="task_249", scheduled_run_time=scheduled)

    service._on_job_missed(event)

    assert len(service.repo.missed_calls) == 1
    call = service.repo.missed_calls[0]
    assert call["task_id"] == 249
    assert call["scheduled_run_time"] == scheduled
    assert "missed" in (call["note"] or "")


def test_missed_event_for_unknown_job_id_is_loud_but_safe(caplog):
    import logging

    service = _service_with([_task()])
    with caplog.at_level(logging.ERROR):
        service._on_job_missed(SimpleNamespace(job_id="not_a_task", scheduled_run_time=None))

    assert "无法解析" in caplog.text
    assert service.repo.missed_calls == []


def test_missed_recording_failure_does_not_escape(caplog):
    import logging

    service = _service_with([_task()])
    service.repo.raise_on_missed = True
    with caplog.at_level(logging.ERROR):
        service._on_job_missed(
            SimpleNamespace(job_id="task_249", scheduled_run_time=None)
        )  # 不得抛

    assert "记录 missed run 失败" in caplog.text


# ── ⑥ 仓储：missed 行的字段与「不许动 next_run_at」──────────────────────

class _FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.config = SimpleNamespace(
            last_status="success", last_error=None, next_run_at="SHOULD_NOT_CHANGE"
        )

    def add(self, obj):
        self.added.append(obj)

    def get(self, model, pk):
        return self.config

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, obj):
        obj.id = 123


def test_record_missed_run_writes_missed_status():
    from adapters.outbound.repositories.scheduler_repository import (
        SchedulerRepository,
    )

    session = _FakeSession()
    repo = SchedulerRepository(session=session)  # 注入假会话：session 是只读属性

    run_id = repo.record_missed_run(249, note="missed by 0:08:37")

    assert run_id == 123
    assert session.committed
    row = session.added[0]
    assert row.status == "missed"
    assert row.task_id == 249
    assert "missed by 0:08:37" in (row.error or "")
    assert session.config.last_status == "missed"
    assert session.config.last_error == "missed by 0:08:37"
    # 排期的事实归 APScheduler，记账逻辑不许改它
    assert session.config.next_run_at == "SHOULD_NOT_CHANGE"


def test_record_missed_run_swallows_db_error():
    from adapters.outbound.repositories.scheduler_repository import (
        SchedulerRepository,
    )

    class _Boom(_FakeSession):
        def commit(self):
            raise RuntimeError("db down")

    repo = SchedulerRepository(session=_Boom())

    assert repo.record_missed_run(249) is None  # 记账失败不许击穿调度
