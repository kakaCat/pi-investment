"""SchedulerService per-task misfire 宽限测试（2026-08-13）

背景：scheduler_daemon 退役统一调度宿主到 FastAPI SchedulerService。daemon
路线的交易类任务配了 300s misfire 宽限（防合盖休眠后用陈旧行情污染模拟
账户），SchedulerService 原是「唤醒必补跑一次」，语义相反。本次补上：
- misfire_grace_time_seconds IS NULL → 无限宽限（存量任务零行为变化）
- 显式配置 → 睡过头超过宽限则跳过本次、记 status='skipped'、按 cron 重排
"""
from datetime import datetime, timedelta, timezone

import pytest

from infrastructure.scheduler.scheduler import SchedulerService


@pytest.fixture()
def scheduler():
    from scripts.migrate_20260813_scheduler_tasks import run_migration
    run_migration()  # 幂等，确保 quant_test 已有 misfire_grace_time_seconds 列
    svc = SchedulerService()
    # 隔离：禁用所有现存任务，跑完恢复（避免 run_due_tasks 触发真实 handler）
    conn = svc._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, is_enabled FROM quant.scheduler_tasks")
    prior = cur.fetchall()
    cur.execute("UPDATE quant.scheduler_tasks SET is_enabled = false")
    conn.commit()
    cur.close()
    conn.close()

    yield svc

    conn = svc._get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM quant.scheduler_runs WHERE task_id IN "
        "(SELECT id FROM quant.scheduler_tasks WHERE name LIKE 'test-misfire-%')")
    cur.execute("DELETE FROM quant.scheduler_tasks WHERE name LIKE 'test-misfire-%'")
    for tid, enabled in prior:
        cur.execute(
            "UPDATE quant.scheduler_tasks SET is_enabled = %s WHERE id = %s",
            (enabled, tid))
    conn.commit()
    cur.close()
    conn.close()
    svc.close()


def _add_task(svc, name, grace, next_run_at):
    task_id = svc.add_task(
        name=name, cron_expression="* * * * *", command="report_daily")
    conn = svc._get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE quant.scheduler_tasks SET next_run_at = %s, "
        "misfire_grace_time_seconds = %s WHERE id = %s",
        (next_run_at, grace, task_id))
    conn.commit()
    cur.close()
    conn.close()
    return task_id


def _last_run(svc, task_id):
    conn = svc._get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT status, error FROM quant.scheduler_runs "
        "WHERE task_id = %s ORDER BY id DESC LIMIT 1", (task_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


class TestMisfireGrace:
    def test_over_grace_skips_and_reschedules(self, scheduler):
        """超宽限：不执行、记 skipped、next_run_at 重排到未来"""
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        task_id = _add_task(scheduler, 'test-misfire-skip', 300, past)

        executed = []
        scheduler._execute_command = lambda cmd, params: executed.append(cmd) or {}
        results = scheduler.run_due_tasks()

        assert executed == []  # 未执行
        entry = next(r for r in results if r['task_id'] == task_id)
        assert entry['status'] == 'skipped'

        run = _last_run(scheduler, task_id)
        assert run[0] == 'skipped'
        assert 'misfire' in run[1]

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
