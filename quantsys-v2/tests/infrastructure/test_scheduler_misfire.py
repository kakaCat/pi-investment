"""SchedulerService per-task misfire 宽限测试（2026-08-13）

2026-09-02 更新：SchedulerService 改为接受 repo（ISchedulerRepository），
不再有 _get_conn()。fixture 改用 SchedulerRepository 接口操作数据库，
避免 db_cursor（raw psycopg2）与 SQLAlchemy 会话争用连接池导致挂死。

已知问题：SchedulerRepository.session 持锁导致 fixture teardown 阶段
repo.remove_task() 挂死，待重构为纯 mock 或增加 session 超时。暂时全模块跳过。
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="SchedulerRepository session 持锁导致 fixture teardown 挂死，待重构为纯 mock"
)
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from infrastructure.scheduler.scheduler import SchedulerService
from adapters.outbound.repositories.scheduler_repository import SchedulerRepository


@pytest.fixture()
def scheduler():
    from scripts.migrate_20260813_scheduler_tasks import run_migration
    run_migration()

    repo = SchedulerRepository()
    svc = SchedulerService(repo=repo)

    prior = repo.list_tasks(enabled_only=False)
    prior_states = [(t['id'], t['is_enabled']) for t in prior]
    for tid, _ in prior_states:
        repo.update_task(tid, is_enabled=False)

    yield svc

    all_tasks = repo.list_tasks(enabled_only=False)
    for t in all_tasks:
        if t.get('name', '').startswith('test-misfire-'):
            repo.remove_task(t['id'])
    for tid, enabled in prior_states:
        repo.update_task(tid, is_enabled=enabled)

    svc.close()


def _add_task(svc, name, grace, next_run_at):
    from infrastructure.persistence.orm.scheduler_models import SchedulerTaskConfig
    task_id = svc.add_task(
        name=name, cron_expression="* * * * *", command="report_daily")
    repo = svc.repo
    config = repo.session.get(SchedulerTaskConfig, task_id)
    config.next_run_at = next_run_at
    config.misfire_grace_time_seconds = grace
    repo.session.commit()
    return task_id


def _last_run(svc, task_id):
    runs = svc.repo.list_runs(task_id=task_id, limit=1)
    return runs[0] if runs else None


class TestMisfireGrace:
    def test_over_grace_skips_and_reschedules(self, scheduler):
        """超宽限：不执行、记 skipped、next_run_at 重排到未来"""
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        task_id = _add_task(scheduler, 'test-misfire-skip', 300, past)

        executed = []
        scheduler._execute_command = lambda cmd, params: executed.append(cmd) or {}
        results = scheduler.run_due_tasks()

        assert executed == []
        entry = next(r for r in results if r['task_id'] == task_id)
        assert entry['status'] == 'skipped'

        run = _last_run(scheduler, task_id)
        assert run is not None
        assert run['error'] and 'misfire' in run['error']

        task = scheduler.get_task(task_id)
        assert task['next_run_at'].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
        assert task['last_status'] == 'skipped'

    def test_within_grace_executes(self, scheduler):
        """宽限内：正常执行"""
        recent = datetime.now(timezone.utc) - timedelta(seconds=60)
        task_id = _add_task(scheduler, 'test-misfire-run', 300, recent)

        scheduler._execute_command = lambda cmd, params: {'ok': True}
        results = scheduler.run_due_tasks()

        entry = next(r for r in results if r['task_id'] == task_id)
        assert entry['status'] == 'success'

    def test_null_grace_always_catches_up(self, scheduler):
        """NULL 宽限 = 现语义回归：迟到再久也补跑一次"""
        ancient = datetime.now(timezone.utc) - timedelta(days=3)
        task_id = _add_task(scheduler, 'test-misfire-null', None, ancient)

        scheduler._execute_command = lambda cmd, params: {'ok': True}
        results = scheduler.run_due_tasks()

        entry = next(r for r in results if r['task_id'] == task_id)
        assert entry['status'] == 'success'

    def test_rescheduled_next_run_matches_cron(self, scheduler):
        """重排后的 next_run_at 必须匹配 cron 且严格在未来"""
        from infrastructure.scheduler.scheduler import parse_cron
        past = datetime.now(timezone.utc) - timedelta(hours=5)
        task_id = _add_task(scheduler, 'test-misfire-cron', 60, past)

        scheduler._execute_command = lambda cmd, params: {}
        scheduler.run_due_tasks()

        task = scheduler.get_task(task_id)
        nxt = task['next_run_at'].replace(tzinfo=timezone.utc)
        assert nxt > datetime.now(timezone.utc)
        assert parse_cron(task['cron_expression']).matches(nxt)
