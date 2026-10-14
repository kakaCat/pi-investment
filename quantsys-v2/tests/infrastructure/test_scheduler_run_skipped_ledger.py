"""仓储层 `skipped` 终态记账单测（REQ-261006093620-a315 · t4 · FR-3）

## 两段式，各有各的理由

- **语义段（假会话，零 DB）**：验 `status` / `completed_at` / `duration_ms` / `last_error=None` /
  `config.last_status` / `next_run_at` 重算 / result 的 JSON 安全，以及**两种终态的异常策略差异**
  （`complete_run` 上抛、`complete_run_skipped` 吞掉返回 False）。
- **落库段（真库一次往返，自建自删）**：验 `status='skipped'` 真能写进 `quant.scheduler_runs`
  （该列无 CHECK 约束）且 `completed_at` 落盘。

⚠️ 真库段刻意**自建自删 + finally 关会话**：本仓有过 `SchedulerRepository` 会话持锁导致
fixture teardown 挂死的记录（`tests/infrastructure/test_scheduler_misfire.py` 整模块被 skip），
所以这里只用一次提交、绝不跑 `run_migration()`、也不改既有任务行。
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
from infrastructure.persistence.orm.models.scheduler import SchedulerRun, SchedulerTaskConfig


class _FakeSession:
    """只支持 `_finish_run` 用到的三件事：get / commit / rollback。"""

    def __init__(self, run=None, config=None):
        self.run = run
        self.config = config
        self.commits = 0
        self.rollbacks = 0

    def get(self, model, pk):
        if model is SchedulerRun:
            return self.run
        if model is SchedulerTaskConfig:
            return self.config
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _BoomCommitSession(_FakeSession):
    def commit(self):
        raise RuntimeError('commit boom')


def _run(status='running'):
    return SchedulerRun(
        task_id=4242,
        status=status,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=3),
    )


def _config(cron='0 9 * * 1-5'):
    return SchedulerTaskConfig(name='__t4_fake__', cron_expression=cron, command='probe')


# ---------------------------------------------------------------------------
# 语义段（假会话）
# ---------------------------------------------------------------------------


def test_complete_run_skipped_writes_expected_fields():
    run, cfg = _run(), _config()
    session = _FakeSession(run=run, config=cfg)
    repo = SchedulerRepository(session=session)

    ok = repo.complete_run_skipped(7, result={'skipped': True, 'reason': '休市'})

    assert ok is True
    assert run.status == 'skipped'
    assert run.completed_at is not None
    assert run.duration_ms >= 3000          # 由 started_at 算出，不是恒 0
    assert run.error is None                # 跳过不是失败
    assert cfg.last_status == 'skipped'
    assert cfg.last_error is None
    assert session.commits == 1


def test_complete_run_skipped_result_is_json_safe():
    """result 里带 date / Decimal 也必须能落 JSONB（2026-09-13 那次假 failed 的同族坑）。"""
    run = _run()
    repo = SchedulerRepository(session=_FakeSession(run=run, config=_config()))

    repo.complete_run_skipped(7, result={'d': date(2026, 10, 7), 'x': Decimal('1.5'), 'skipped': True})

    assert run.result['skipped'] is True
    assert isinstance(run.result['d'], str)     # date 已被安全化成字符串
    json.dumps(run.result)                      # 不抛 = JSONB 能收


def test_complete_run_skipped_never_raises_and_rolls_back():
    """记账失败**不许影响调度**：返回 False、回滚、不抛。"""
    session = _BoomCommitSession(run=_run(), config=_config())
    repo = SchedulerRepository(session=session)

    assert repo.complete_run_skipped(7, result={'skipped': True}) is False
    assert session.rollbacks == 1


def test_complete_run_still_raises_on_failure():
    """回归锁：`complete_run` 的异常策略**未被本次改动改变**（真跑完失败必须响亮）。"""
    session = _BoomCommitSession(run=_run(), config=_config())
    repo = SchedulerRepository(session=session)

    with pytest.raises(RuntimeError):
        repo.complete_run(7, success=True)
    assert session.rollbacks == 1


def test_complete_run_maps_success_and_failed_unchanged():
    """回归锁：`complete_run(success=...)` 仍然只映射 success / failed 两个终态。"""
    for flag, expected in ((True, 'success'), (False, 'failed')):
        run, cfg = _run(), _config()
        SchedulerRepository(session=_FakeSession(run=run, config=cfg)).complete_run(
            7, success=flag, error=None if flag else 'boom'
        )
        assert run.status == expected
        assert cfg.last_status == expected


def test_complete_run_skipped_missing_run_returns_false():
    """run 不存在（例如已被清理）→ False，不抛。"""
    repo = SchedulerRepository(session=_FakeSession(run=None, config=_config()))
    assert repo.complete_run_skipped(999999, result={'skipped': True}) is False


def test_managed_by_agent_os_task_skips_next_run_recalc():
    """Agent OS 托管伪任务的 next_run_at 不被重算（既有语义，本次未动）。"""
    cfg = _config(cron='managed_by_agent_os')
    cfg.next_run_at = None
    SchedulerRepository(session=_FakeSession(run=_run(), config=cfg)).complete_run_skipped(7)
    assert cfg.next_run_at is None
    assert cfg.last_status == 'skipped'


# ---------------------------------------------------------------------------
# 落库段（真库，一次往返，自建自删）
# ---------------------------------------------------------------------------


def test_skipped_status_persists_in_real_db():
    from sqlalchemy import text

    from infrastructure.persistence.orm import get_session

    session = get_session()
    repo = SchedulerRepository(session=session)
    task_id = None
    probe = f'__t4_probe_{int(time.time())}__'
    try:
        task_id = session.execute(text(
            "insert into quant.scheduler_tasks (name, cron_expression, command, trading_day_policy) "
            "values (:n, '0 9 * * 1-5', 'probe', 'always') returning id"
        ), {'n': probe}).scalar()
        session.commit()

        run_id = repo.create_run(task_id)
        assert repo.complete_run_skipped(run_id, result={'skipped': True, 'reason': '休市'}) is True

        got = session.execute(text(
            "select status, completed_at, error, result from quant.scheduler_runs where id = :i"
        ), {'i': run_id}).mappings().first()
        assert got['status'] == 'skipped'
        assert got['completed_at'] is not None
        assert got['error'] is None
        assert got['result']['skipped'] is True

        last = session.execute(text(
            "select last_status, last_error from quant.scheduler_tasks where id = :i"
        ), {'i': task_id}).mappings().first()
        assert last['last_status'] == 'skipped'
        assert last['last_error'] is None
    finally:
        if task_id is not None:
            session.execute(text("delete from quant.scheduler_runs where task_id = :i"), {'i': task_id})
            session.execute(text("delete from quant.scheduler_tasks where id = :i"), {'i': task_id})
            session.commit()
        session.close()
