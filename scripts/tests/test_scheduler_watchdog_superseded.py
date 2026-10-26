"""后续成功覆盖 missed 槽位的闭环与幂等审计测试。

全部连接、探活、通知和补跑均为 mock，不访问数据库或真实调度服务。
"""
import importlib.util
import pathlib
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

WATCHDOG = pathlib.Path(__file__).resolve().parents[1] / "scheduler_watchdog.py"
UTC = timezone.utc
NOW = datetime(2026, 10, 26, 1, 0, tzinfo=UTC)  # 北京 09:00
SINCE = NOW - timedelta(hours=2)
SLOT = datetime(2026, 10, 26, 0, 0, tzinfo=UTC)  # 北京 08:00


@pytest.fixture(scope="module")
def wd():
    spec = importlib.util.spec_from_file_location("scheduler_watchdog_superseded", WATCHDOG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ScanCursor:
    """只提供扫描所需查询的内存游标。"""

    def __init__(self, conn):
        self.conn = conn
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, sql, params=None):
        query = " ".join(sql.split())
        params = params or ()
        if "agent_line IS NULL" in query or "apscheduler_jobs" in query:
            self.result = []
        elif "FROM quant.scheduler_tasks WHERE is_enabled=true" in query:
            self.result = [self.conn.task]
        elif "FROM public.tasks WHERE enabled=true" in query:
            self.result = [self.conn.task]
        elif query.startswith("SELECT started_at FROM quant.scheduler_runs") or \
                query.startswith("SELECT started_at FROM public.task_runs"):
            self.result = [{"started_at": r["started_at"]} for r in self.conn.later_runs]
        elif query.startswith("SELECT count(*) AS n FROM quant.scheduler_runs") or \
                query.startswith("SELECT count(*) AS n FROM public.task_runs"):
            # 覆盖只能由 success 产生；failed/running/空结果都必须保持未覆盖。
            assert "status='success'" in query
            self.result = [{
                "n": sum(
                    r["status"] == "success" and r["started_at"] > params[1]
                    for r in self.conn.later_runs
                )
            }]
        elif "status='running'" in query:
            self.result = []  # zombie 与本组用例无关
        else:
            raise AssertionError(f"未预期的扫描 SQL: {query}")

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0] if self.result else None


class ScanConnection:
    def __init__(self, system, later_status):
        self.later_runs = [] if later_status is None else [{
            "started_at": SLOT + timedelta(minutes=30),
            "status": later_status,
        }]
        if system == "v2":
            self.task = {
                "id": 42, "name": "v2-daily", "cron_expression": "0 8 * * *",
                "command": "daily", "compensation_enabled": True, "last_run_at": None,
                "misfire_grace_time_seconds": 300, "compensation_check_after": None,
                "compensation_max_attempts": 1, "task_type": "cron", "params": {},
            }
        else:
            self.task = {
                "id": "os-task", "name": "os-daily", "cron": "0 8 * * *",
                "command": "daily", "metadata": {"watchdog": "auto_rerun", "catchup": {}},
            }

    def cursor(self, *args, **kwargs):
        return ScanCursor(self)


class LogCursor:
    """quant.scheduler_watchdog_log 的纯内存实现。"""

    def __init__(self, conn):
        self.conn = conn
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, sql, params=None):
        query = " ".join(sql.split())
        params = params or ()
        rows = self.conn.rows
        if query.startswith("SELECT id, issue_key FROM quant.scheduler_watchdog_log"):
            self.result = [(r["id"], r["issue_key"]) for r in rows if not r["resolved"]]
        elif query.startswith("SELECT id, resolved FROM quant.scheduler_watchdog_log"):
            matches = [r for r in rows if r["issue_key"] == params[0]]
            matches.sort(key=lambda r: (r["resolved"], -r["id"]))
            self.result = [(r["id"], r["resolved"]) for r in matches[:1]]
        elif query.startswith("SELECT id FROM quant.scheduler_watchdog_log"):
            matches = [r for r in rows if r["issue_key"] == params[0] and not r["resolved"]]
            self.result = [(r["id"],) for r in matches[:1]]
        elif query.startswith("UPDATE quant.scheduler_watchdog_log") and "resolved_at=COALESCE" in query:
            detail, action, row_id = params
            row = self.conn.row(row_id)
            row.update(detail=detail, action=action, resolved=True)
            if row["resolved_at"] is None:
                row["resolved_at"] = "db-now"
            self.result = []
        elif query.startswith("UPDATE quant.scheduler_watchdog_log") and "SET resolved=true" in query:
            row = self.conn.row(params[0])
            row.update(resolved=True, resolved_at="db-now")
            self.result = []
        elif query.startswith("UPDATE quant.scheduler_watchdog_log"):
            detail, action, row_id = params
            self.conn.row(row_id).update(detail=detail, action=action)
            self.result = []
        elif query.startswith("INSERT INTO quant.scheduler_watchdog_log"):
            if "resolved, resolved_at" in query:
                key, system, issue_type, detail, action = params
                self.conn.add_row(key, system, issue_type, detail, action, resolved=True)
            else:
                key, system, issue_type, detail, action = params
                self.conn.add_row(key, system, issue_type, detail, action, resolved=False)
            self.result = []
        else:
            raise AssertionError(f"未预期的日志 SQL: {query}")

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0] if self.result else None


class LogConnection:
    def __init__(self):
        self.rows = []
        self.next_id = 1

    def cursor(self, *args, **kwargs):
        return LogCursor(self)

    def row(self, row_id):
        return next(r for r in self.rows if r["id"] == row_id)

    def add_row(self, key, system, issue_type, detail, action, resolved):
        row = {
            "id": self.next_id, "issue_key": key, "system": system,
            "issue_type": issue_type, "detail": detail, "action": action,
            "resolved": resolved, "resolved_at": "db-now" if resolved else None,
        }
        self.next_id += 1
        self.rows.append(row)
        return row

    def commit(self):
        return None

    def close(self):
        return None  # 同一内存库可连续跑两轮 main


def _missed(system, superseded, enabled=True):
    task_id = 42 if system == "v2" else "os-task"
    prefix = "v2" if system == "v2" else "os"
    return {
        "key": f"{prefix}:missed:{task_id}:202610260800",
        "type": "missed", "system": system, "task_id": task_id,
        "task": f"{prefix}-daily", "policy": "auto_rerun" if enabled else "alert_only",
        "detail": "应于 10-26 08:00 执行（0 8 * * *）",
        "catchup": {
            "enabled": enabled, "max_attempts": 1, "check_after": None,
            "window_hours": 12, "market_hours_only": False, "task_type": "cron",
            "superseded": superseded, "slot_age_hours": 1.0,
        },
    }


def _run_main(wd, monkeypatch, conn, issues):
    """在完全隔离的依赖下执行一轮 main。"""
    notify = Mock()
    trigger = Mock()
    attempts = Mock(return_value=0)
    monkeypatch.setattr(wd, "db_conn", lambda: conn)
    monkeypatch.setattr(wd, "ensure_log_table", lambda _conn: None)
    monkeypatch.setattr(wd, "ensure_catchup_table", lambda _conn: None)
    monkeypatch.setattr(wd, "probe_health", lambda _url: True)
    monkeypatch.setattr(wd, "scan_v2", lambda _conn, _now, _since: [
        it for it in issues if it["system"] == "v2"
    ])
    monkeypatch.setattr(wd, "scan_agent_os", lambda _conn, _now, _since: [
        it for it in issues if it["system"] == "agent_os"
    ])
    monkeypatch.setattr(wd, "reconcile_task_status", lambda _conn: [])
    monkeypatch.setattr(wd, "catchup_attempts", attempts)
    monkeypatch.setattr(wd, "record_catchup", Mock())
    monkeypatch.setattr(wd, "trigger_rerun", trigger)
    monkeypatch.setattr(wd, "send_feishu", notify)
    monkeypatch.setattr(wd, "AUTO_RERUN_ENABLED", True)
    assert wd.main() == 0
    return notify, trigger, attempts


@pytest.mark.parametrize("system", ["v2", "agent_os"])
@pytest.mark.parametrize("later_status,covered", [
    (None, False), ("failed", False), ("success", True),
])
def test_scans_only_success_covers_slot(wd, system, later_status, covered):
    conn = ScanConnection(system, later_status)
    scan = wd.scan_v2 if system == "v2" else wd.scan_agent_os
    issues = scan(conn, NOW, SINCE)
    missed = [it for it in issues if it["type"] == "missed"]
    assert len(missed) == 1
    assert missed[0]["catchup"]["superseded"] is covered


@pytest.mark.parametrize("system", ["v2", "agent_os"])
def test_open_missed_resolves_when_later_success_covers(wd, monkeypatch, system):
    issue = _missed(system, superseded=True)
    conn = LogConnection()
    row = conn.add_row(issue["key"], system, "missed", "旧告警", "alerted", resolved=False)

    notify, trigger, attempts = _run_main(wd, monkeypatch, conn, [issue])

    assert row["resolved"] is True
    assert row["resolved_at"] == "db-now"
    assert row["action"] == "covered_by_later_success"
    assert "原槽位曾漏跑" in row["detail"]
    trigger.assert_not_called()
    attempts.assert_not_called()  # 覆盖问题连补跑资格都不应再评估
    assert notify.call_count == 1
    assert "covered_by_later_success" in notify.call_args.args[1]


@pytest.mark.parametrize("system", ["v2", "agent_os"])
def test_first_scan_covered_audit_is_idempotent(wd, monkeypatch, system):
    issue = _missed(system, superseded=True)
    conn = LogConnection()

    first_notify, first_trigger, first_attempts = _run_main(wd, monkeypatch, conn, [issue])
    resolved_at = conn.rows[0]["resolved_at"]
    second_notify, second_trigger, second_attempts = _run_main(wd, monkeypatch, conn, [issue])

    assert len(conn.rows) == 1
    assert conn.rows[0]["resolved"] is True
    assert conn.rows[0]["action"] == "covered_by_later_success"
    assert conn.rows[0]["resolved_at"] == resolved_at
    assert "covered_by_later_success" in conn.rows[0]["detail"]
    assert first_notify.call_count == second_notify.call_count == 0  # 首次即覆盖只审计，不报开放告警
    first_trigger.assert_not_called()
    second_trigger.assert_not_called()
    first_attempts.assert_not_called()
    second_attempts.assert_not_called()


@pytest.mark.parametrize("system", ["v2", "agent_os"])
def test_uncovered_missed_stays_open(wd, monkeypatch, system):
    issue = _missed(system, superseded=False, enabled=False)
    conn = LogConnection()

    first_notify, first_trigger, first_attempts = _run_main(wd, monkeypatch, conn, [issue])
    second_notify, second_trigger, _ = _run_main(wd, monkeypatch, conn, [issue])

    assert len(conn.rows) == 1
    assert conn.rows[0]["resolved"] is False
    assert conn.rows[0]["action"] == "alerted"
    assert first_notify.call_count == 1
    assert second_notify.call_count == 0  # 未覆盖告警仍按原逻辑去重
    first_trigger.assert_not_called()
    second_trigger.assert_not_called()
    first_attempts.assert_called_once()


def test_untagged_and_zombie_behavior_unchanged(wd, monkeypatch):
    issues = [
        {"key": "os:untagged:9", "type": "untagged", "system": "agent_os",
         "task_id": "9", "task": "untagged", "policy": "alert_only", "detail": "未打标"},
        {"key": "v2:zombie:8", "type": "zombie", "system": "v2",
         "task_id": None, "task": "zombie", "policy": "alert_only", "detail": "卡 running"},
    ]
    conn = LogConnection()

    notify, trigger, attempts = _run_main(wd, monkeypatch, conn, issues)

    assert len(conn.rows) == 2
    assert all(row["resolved"] is False for row in conn.rows)
    assert all(row["action"] == "alerted" for row in conn.rows)
    assert notify.call_count == 1
    assert "2 项" in notify.call_args.args[0]
    trigger.assert_not_called()
    attempts.assert_not_called()
