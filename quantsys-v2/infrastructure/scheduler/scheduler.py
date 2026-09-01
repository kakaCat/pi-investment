"""
Cron-based task scheduler for quantsys-v2.

Manages scheduled task definitions, cron parsing, task execution,
and a blocking run loop with graceful shutdown support.
"""
from __future__ import annotations

import json
import logging
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import psycopg2
from psycopg2.extras import RealDictCursor

from infrastructure.persistence.database.engine import _resolve_db_dsn

logger = logging.getLogger(__name__)


# ============================================================================
# Custom JSON encoder — handles datetime/date serialisation
# ============================================================================

class _DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that converts datetime / date objects to ISO-8601 strings."""

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


# ============================================================================
# CronSchedule — parsed 5-field cron expression
# ============================================================================


@dataclass
class CronSchedule:
    """Parsed representation of a 5-field cron expression."""

    minute: Set[int]  # 0-59
    hour: Set[int]  # 0-23
    dom: Set[int]  # 1-31 (day of month)
    month: Set[int]  # 1-12
    dow: Set[int]  # 0-6 (0=Sunday, 6=Saturday)

    def matches(self, dt: datetime) -> bool:
        """Return True if *dt* matches this schedule."""
        return (
            dt.minute in self.minute
            and dt.hour in self.hour
            and dt.day in self.dom
            and dt.month in self.month
            and _cron_dow(dt) in self.dow
        )


def _cron_dow(dt: datetime) -> int:
    """Convert a Python datetime weekday to cron-style DOW.

    Python ``isoweekday()`` returns 1 (Monday) through 7 (Sunday).
    Cron DOW is 0 (Sunday) through 6 (Saturday).
    """
    iso = dt.isoweekday()
    return 0 if iso == 7 else iso


# ============================================================================
# Cron parser — no external dependencies
# ============================================================================


def parse_cron(expression: str) -> CronSchedule:
    """Parse a standard 5-field cron expression.

    Args:
        expression: e.g. ``"0 9 * * 1-5"`` or ``"*/30 9-17 * * 1-5"``.

    Returns:
        CronSchedule with parsed field sets.

    Raises:
        ValueError: if the expression cannot be parsed.
    """
    fields = expression.strip().split()
    if len(fields) != 5:
        raise ValueError(
            f"Cron expression must have 5 fields, got {len(fields)}: {expression!r}"
        )

    minute_str, hour_str, dom_str, month_str, dow_str = fields

    schedule = CronSchedule(
        minute=_parse_field(minute_str, 0, 59),
        hour=_parse_field(hour_str, 0, 23),
        dom=_parse_field(dom_str, 1, 31),
        month=_parse_field(month_str, 1, 12),
        dow=_parse_field(dow_str, 0, 7),  # 0 and 7 both mean Sunday
    )

    # Normalize Sunday: both 0 and 7 represent Sunday.
    # If either is present, both are allowed so matches() works.
    if 0 in schedule.dow:
        schedule.dow.add(7)
    if 7 in schedule.dow:
        schedule.dow.add(0)

    return schedule


def _parse_field(field_str: str, min_val: int, max_val: int) -> Set[int]:
    """Parse a single cron field into a set of allowed integer values.

    Supported syntax:
      - ``*``           all values in [min_val, max_val]
      - ``N``           single value
      - ``N-M``         inclusive range
      - ``N,M,O``       comma-separated list of sub-expressions
      - ``*/N``         every N-th value starting from min_val
      - ``N-M/N``       every N-th value within a range
    """
    values: Set[int] = set()

    if field_str == "*":
        return set(range(min_val, max_val + 1))

    # Step:  */N   or   N-M/N
    if "/" in field_str:
        range_part, step_str = field_str.split("/", 1)
        step = int(step_str)
        if step <= 0:
            raise ValueError(f"Step must be positive: {field_str!r}")
        if range_part == "*":
            start, end = min_val, max_val
        elif "-" in range_part:
            start_str, end_str = range_part.split("-", 1)
            start, end = int(start_str), int(end_str)
        else:
            start = int(range_part)
            end = max_val
        for v in range(start, end + 1, step):
            values.add(v)
        return values

    # Comma-separated list
    if "," in field_str:
        for part in field_str.split(","):
            values.update(_parse_field(part, min_val, max_val))
        return values

    # Range: N-M
    if "-" in field_str:
        start_str, end_str = field_str.split("-", 1)
        start, end = int(start_str), int(end_str)
        if start < min_val or end > max_val:
            raise ValueError(
                f"Range {start}-{end} out of bounds [{min_val}, {max_val}]"
            )
        return set(range(start, end + 1))

    # Single value
    v = int(field_str)
    if v < min_val or v > max_val:
        raise ValueError(
            f"Value {v} out of bounds [{min_val}, {max_val}]"
        )
    values.add(v)
    return values


def next_run_time(expression: str, from_time: Optional[datetime] = None) -> datetime:
    """Compute the next datetime after *from_time* that matches *expression*.

    Scans minute-by-minute up to 2 years ahead.

    Args:
        expression: 5-field cron expression.
        from_time: reference datetime (default: now, UTC).

    Returns:
        The earliest matching datetime strictly after *from_time*.

    Raises:
        ValueError: if no match is found within the search window.
    """
    schedule = parse_cron(expression)

    if from_time is None:
        from_time = datetime.now(timezone.utc)

    # Ensure we are working in UTC
    if from_time.tzinfo is None:
        from_time = from_time.replace(tzinfo=timezone.utc)

    # Start from the next whole minute
    current = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Search up to 2 years ahead (~1M minutes)
    end_limit = current + timedelta(days=366 * 2)

    while current <= end_limit:
        if schedule.matches(current):
            return current
        current += timedelta(minutes=1)

    raise ValueError(
        f"No matching time within 2 years for cron expression: {expression!r}"
    )


# ============================================================================
# SchedulerService
# ============================================================================


class SchedulerService:
    """Cron-based task scheduler.

    Manages persistent task definitions in ``quant.scheduler_tasks`` and
    execution history in ``quant.scheduler_runs``.  Task handlers delegate
    to :class:`DataService` repositories for domain logic.

    Typical usage::

        scheduler = SchedulerService()
        scheduler.add_task("daily-report", "0 9 * * 1-5", "report_daily")
        scheduler.run_loop()   # blocking — checks every 30 s
    """

    # running 超过该时长的 run 视为僵尸（进程被杀残留），自动判死放行
    ZOMBIE_RUN_TIMEOUT = timedelta(hours=6)

    def __init__(self):
        self._conn: Any = None
        self._running = False
        self._loop_interval = 30  # seconds

    # ------------------------------------------------------------------
    # DataService lazy accessor
    # ------------------------------------------------------------------
    # Deprecated DataService helpers — kept as no-ops to avoid breaking callers
    # during incremental migration. Will be fully removed once all ds.* references
    # in this file are replaced with direct Repository access.
    # ------------------------------------------------------------------

    def _create_data_service(self):
        """DEPRECATED: Return None. Callers must use direct Repository access."""
        return None

    # ------------------------------------------------------------------
    # Database connection (scheduler-specific tables)
    # ------------------------------------------------------------------

    def _get_conn(self):
        """获取数据库连接(从全局 SQLAlchemy Engine 池)。

        IMPORTANT: 调用方必须在 finally 块里归还连接:
            conn = self._get_conn()
            try:
                # ... SQL 操作 ...
            finally:
                conn.close()  # 归还给 Engine 池

        Returns:
            psycopg2 connection (底层 DBAPI 连接,向后兼容现有代码)
        """
        from infrastructure.persistence.database.engine import get_engine
        engine = get_engine()
        # raw_connection() 返回底层 DBAPI 连接(psycopg2),向后兼容现有 SQL 代码
        return engine.raw_connection()

    def close(self):
        """Deprecated: Engine 池自动管理连接,无需手工 close。

        保留此方法仅为向后兼容,实际不做任何事。
        """
        pass

    # ==================================================================
    # Task CRUD
    # ==================================================================

    def add_task(
        self,
        name: str,
        cron_expression: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
    ) -> int:
        """Register a new scheduled task.

        Args:
            name: unique task name.
            cron_expression: 5-field cron string.
            command: handler name (e.g. ``"data_update"``).
            params: optional JSON-serialisable parameters.
            description: optional human-readable description.

        Returns:
            The new task's ``id``.

        Raises:
            ValueError: on invalid cron expression or duplicate name.
        """
        # Validate cron expression early
        schedule = parse_cron(cron_expression)
        next_run = next_run_time(cron_expression)

        params_json = json.dumps(params or {})

        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                INSERT INTO quant.scheduler_tasks
                    (name, description, cron_expression, command, params,
                     next_run_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (name, description, cron_expression, command, params_json, next_run),
            )
            task_id = cursor.fetchone()["id"]
            conn.commit()
            logger.info(
                "Task %r (id=%s) added — next run at %s",
                name,
                task_id,
                next_run.isoformat(),
            )
            return task_id
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise ValueError(f"Task with name {name!r} already exists")
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            conn.close()  # 归还给 Engine 池

    def remove_task(self, task_id: int) -> bool:
        """Delete a task by id.

        Returns:
            ``True`` if a row was deleted, ``False`` otherwise.
        """
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "DELETE FROM quant.scheduler_tasks WHERE id = %s", (task_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Task id=%s removed", task_id)
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def update_task(self, task_id: int, **kwargs) -> bool:
        """Update fields on an existing task.

        Supported keyword arguments:
            name, description, cron_expression, command, params, is_enabled.

        When *cron_expression* changes, ``next_run_at`` is recalculated.
        When *is_enabled* is toggled on, ``next_run_at`` is recalculated.

        Returns:
            ``True`` if the task was updated.
        """
        allowed = {
            "name",
            "description",
            "cron_expression",
            "command",
            "params",
            "is_enabled",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        # Recalculate next_run_at if cron expression changed or task re-enabled
        if "cron_expression" in updates:
            expr = updates["cron_expression"]
            updates["next_run_at"] = next_run_time(expr)
        elif updates.get("is_enabled") is True:
            task = self.get_task(task_id)
            if task is not None:
                updates["next_run_at"] = next_run_time(task["cron_expression"])

        # JSON-serialise params
        if "params" in updates and isinstance(updates["params"], dict):
            updates["params"] = json.dumps(updates["params"])

        # Build SET clause
        set_clauses = [f"{col} = %s" for col in updates]
        values = list(updates.values())
        set_clauses.append("updated_at = now()")
        values.append(task_id)

        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                f"UPDATE quant.scheduler_tasks SET {', '.join(set_clauses)} "
                f"WHERE id = %s",
                values,
            )
            updated = cursor.rowcount > 0
            conn.commit()
            if updated:
                logger.info("Task id=%s updated with %s", task_id, list(updates.keys()))
            return updated
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Return a single task dict or ``None``."""
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT * FROM quant.scheduler_tasks WHERE id = %s", (task_id,)
            )
            row = cursor.fetchone()
            conn.commit()
            return dict(row) if row else None
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def get_task_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a task dict by name or ``None``."""
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT * FROM quant.scheduler_tasks WHERE name = %s", (name,)
            )
            row = cursor.fetchone()
            conn.commit()
            return dict(row) if row else None
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def list_tasks(
        self,
        enabled_only: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List tasks, optionally only enabled ones.

        Results are ordered by ``next_run_at ASC``.
        """
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            params: List[Any] = []
            if enabled_only:
                query = (
                    "SELECT * FROM quant.scheduler_tasks "
                    "WHERE is_enabled = true "
                    "ORDER BY next_run_at ASC NULLS LAST"
                )
            else:
                query = (
                    "SELECT * FROM quant.scheduler_tasks "
                    "ORDER BY next_run_at ASC NULLS LAST"
                )
            if limit is not None:
                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.commit()
            return [dict(row) for row in rows]
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def count_tasks(self, enabled_only: bool = False) -> int:
        """Count scheduler tasks, optionally only enabled ones."""
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            if enabled_only:
                cursor.execute(
                    "SELECT COUNT(*) AS count FROM quant.scheduler_tasks "
                    "WHERE is_enabled = true"
                )
            else:
                cursor.execute("SELECT COUNT(*) AS count FROM quant.scheduler_tasks")
            row = cursor.fetchone()
            conn.commit()
            return int(row["count"]) if row else 0
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def enable_task(self, task_id: int) -> bool:
        """Enable a task and recalculate its next run time."""
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        next_run = next_run_time(task["cron_expression"])

        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "UPDATE quant.scheduler_tasks "
                "SET is_enabled = true, next_run_at = %s, updated_at = now() "
                "WHERE id = %s",
                (next_run, task_id),
            )
            conn.commit()
            logger.info("Task id=%s enabled — next run at %s", task_id, next_run.isoformat())
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def disable_task(self, task_id: int) -> bool:
        """Disable a task so it will not be picked up by the loop."""
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "UPDATE quant.scheduler_tasks "
                "SET is_enabled = false, updated_at = now() "
                "WHERE id = %s",
                (task_id,),
            )
            conn.commit()
            logger.info("Task id=%s disabled", task_id)
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            conn.close()

    # ==================================================================
    # Run lifecycle
    # ==================================================================

    @staticmethod
    def _parse_started_at(value: Any) -> Optional[datetime]:
        """把 started_at（datetime 或 ISO 字符串）统一解析为带时区的 datetime。

        解析失败返回 None（调用方按非僵尸处理，保持原有阻塞语义）。
        """
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                return None
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return None

    def create_run(self, task_id: int) -> int:
        """Record a new run for *task_id*, mark task as ``'running'``.

        Returns:
            The new run's ``id``.
        """
        now = datetime.now(timezone.utc)

        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # Insert run record
            cursor.execute(
                "INSERT INTO quant.scheduler_runs (task_id, status, started_at) "
                "VALUES (%s, 'running', %s) RETURNING id",
                (task_id, now),
            )
            run_id = cursor.fetchone()["id"]

            # Update task: last_run_at, last_status
            cursor.execute(
                "UPDATE quant.scheduler_tasks "
                "SET last_run_at = %s, last_status = 'running', updated_at = now() "
                "WHERE id = %s",
                (now, task_id),
            )
            conn.commit()
            logger.debug("Run id=%s started for task id=%s", run_id, task_id)
            return run_id
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def complete_run(
        self,
        run_id: int,
        success: bool = True,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Mark a run as completed.

        Args:
            run_id: the run to finalise.
            success: ``True`` for success, ``False`` for failure.
            result: optional JSON result payload.
            error: optional error message (only meaningful when
                   *success* is ``False``).
        """
        status = "success" if success else "failed"
        now = datetime.now(timezone.utc)
        result_json = json.dumps(result, cls=_DateTimeEncoder) if result else None

        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                UPDATE quant.scheduler_runs
                SET status = %s,
                    completed_at = %s,
                    result = %s,
                    error = %s,
                    duration_ms = EXTRACT(EPOCH FROM (%s - started_at)) * 1000
                WHERE id = %s
                RETURNING task_id
                """,
                (status, now, result_json, error, now, run_id),
            )
            row = cursor.fetchone()

            if row is not None:
                task_id = row["task_id"]

                # Update the task's last_status and recalculate next_run_at
                task = self.get_task(task_id)
                if task is not None:
                    next_run = next_run_time(task["cron_expression"])
                    cursor.execute(
                        "UPDATE quant.scheduler_tasks "
                        "SET last_status = %s, last_error = %s, "
                        "    next_run_at = %s, updated_at = now() "
                        "WHERE id = %s",
                        (status, error, next_run, task_id),
                    )

            conn.commit()
            logger.info("Run id=%s completed — status=%s", run_id, status)
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Return a single run record or ``None``."""
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT * FROM quant.scheduler_runs WHERE id = %s", (run_id,)
            )
            row = cursor.fetchone()
            conn.commit()
            return dict(row) if row else None
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def list_runs(
        self,
        task_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        statuses: Optional[List[str]] = None,
        date_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List recent runs, optionally filtered by task.

        Results are ordered by ``started_at DESC``.
        """
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            where = []
            params: List[Any] = []
            if task_id is not None:
                where.append("task_id = %s")
                params.append(task_id)
            if statuses:
                placeholders = ", ".join(["%s"] * len(statuses))
                where.append(f"status IN ({placeholders})")
                params.extend(statuses)
            if date_filter:
                where.append("started_at::date = %s::date")
                params.append(date_filter)
            query = "SELECT * FROM quant.scheduler_runs"
            if where:
                query += " WHERE " + " AND ".join(where)
            query += " ORDER BY started_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.commit()
            return [dict(row) for row in rows]
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def count_runs(
        self,
        task_id: Optional[int] = None,
        statuses: Optional[List[str]] = None,
        date_filter: Optional[str] = None,
    ) -> int:
        """Count scheduler runs, optionally filtered by task and status."""
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            where = []
            params: List[Any] = []
            if task_id is not None:
                where.append("task_id = %s")
                params.append(task_id)
            if statuses:
                placeholders = ", ".join(["%s"] * len(statuses))
                where.append(f"status IN ({placeholders})")
                params.extend(statuses)
            if date_filter:
                where.append("started_at::date = %s::date")
                params.append(date_filter)
            query = "SELECT COUNT(*) AS count FROM quant.scheduler_runs"
            if where:
                query += " WHERE " + " AND ".join(where)
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.commit()
            return int(row["count"]) if row else 0
        finally:
            if cursor:
                cursor.close()
            conn.close()

    # ==================================================================
    # Due-check helpers
    # ==================================================================

    def _is_due(self, task: Dict[str, Any], now: Optional[datetime] = None) -> bool:
        """Return True if *task* should run now."""
        if not task.get("is_enabled"):
            return False
        if now is None:
            now = datetime.now(timezone.utc)
        next_run = task.get("next_run_at")
        if next_run is None:
            return True  # never run before
        if isinstance(next_run, str):
            # Parse ISO string — DB may return strings depending on cursor
            next_run = datetime.fromisoformat(next_run)
        # Make offset-naive datetimes comparable
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)
        return next_run <= now

    def _is_misfired(self, task: Dict[str, Any], now: datetime) -> bool:
        """per-task misfire 宽限判定（2026-08-13，对齐原 daemon/APScheduler 语义）。

        ``misfire_grace_time_seconds`` 为 NULL = 无限宽限 = 保持「唤醒必补跑一次」
        现语义（28 个存量任务零行为变化）；显式配置的任务（如交易类 300s）睡过头
        超过宽限则跳过本次——防止合盖休眠后用陈旧行情污染模拟账户。
        """
        grace = task.get("misfire_grace_time_seconds")
        if grace is None:
            return False
        next_run = task.get("next_run_at")
        if next_run is None:
            return False  # 从未运行过，首次执行不算 misfire
        if isinstance(next_run, str):
            next_run = datetime.fromisoformat(next_run)
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)
        return (now - next_run).total_seconds() > grace

    def _record_misfire_skip(self, task: Dict[str, Any], now: datetime) -> None:
        """记录一次 misfire 跳过：scheduler_runs status='skipped'（≠success 契约）
        并按 cron 重排 next_run_at 到未来（不补跑）。"""
        task_id = task["id"]
        next_run = next_run_time(task["cron_expression"])
        reason = (
            f"misfire: 计划 {task.get('next_run_at')} 超过宽限 "
            f"{task.get('misfire_grace_time_seconds')}s，跳过本次"
        )
        conn = self._get_conn()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO quant.scheduler_runs "
                "(task_id, status, started_at, completed_at, duration_ms, error) "
                "VALUES (%s, 'skipped', %s, %s, 0, %s)",
                (task_id, now, now, reason),
            )
            cursor.execute(
                "UPDATE quant.scheduler_tasks "
                "SET last_status = 'skipped', last_error = %s, "
                "    next_run_at = %s, updated_at = now() "
                "WHERE id = %s",
                (reason, next_run, task_id),
            )
            conn.commit()
            logger.warning(
                "Task %r (id=%s) misfire skipped — %s; next run %s",
                task.get("name"), task_id, reason, next_run,
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            conn.close()

    # ==================================================================
    # Execution engine
    # ==================================================================

    def run_due_tasks(self) -> List[Dict[str, Any]]:
        """Find all enabled tasks whose ``next_run_at`` has passed and
        execute them.

        Returns:
            A list of result dicts, each containing
            ``{task_id, task_name, run_id, status, result/error}``.
        """
        tasks = self.list_tasks(enabled_only=True)
        now = datetime.now(timezone.utc)
        results: List[Dict[str, Any]] = []

        for task in tasks:
            if not self._is_due(task, now):
                continue

            task_id = task["id"]
            task_name = task.get("name", str(task_id))

            # misfire 宽限：超宽限的任务跳过本次并重排（不补跑）
            if self._is_misfired(task, now):
                self._record_misfire_skip(task, now)
                results.append({
                    "task_id": task_id,
                    "task_name": task_name,
                    "run_id": None,
                    "status": "skipped",
                    "error": "misfire: 超过宽限，跳过本次",
                })
                continue

            result_entry = {
                "task_id": task_id,
                "task_name": task_name,
                "run_id": None,
                "status": "skipped",
            }

            try:
                result_entry = self.run_task(task_id)
                results.append(result_entry)
            except Exception as exc:
                logger.error(
                    "Task %r (id=%s) failed with exception: %s",
                    task_name,
                    task_id,
                    exc,
                )
                result_entry["status"] = "failed"
                result_entry["error"] = str(exc)
                results.append(result_entry)

        return results

    def run_task(self, task_id: int) -> Dict[str, Any]:
        """Execute a single task by id immediately (regardless of schedule).

        Always creates a run record and marks it completed.

        Returns:
            ``{task_id, task_name, run_id, status, result?, error?}``

        Raises:
            ValueError: if task is already running (duplicate submission prevention).
        """
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        # Prevent duplicate submissions: check if task is already running
        running_tasks = self.list_runs(task_id=task_id, statuses=['running'], limit=1)
        if running_tasks:
            running = running_tasks[0]
            started_at = self._parse_started_at(running.get('started_at'))
            if started_at is not None and (
                datetime.now(timezone.utc) - started_at > self.ZOMBIE_RUN_TIMEOUT
            ):
                # 僵尸 run：进程被杀导致 running 记录滞留（run 1666/2035 事故），
                # 判死后放行，否则任务被永久阻塞
                logger.warning(
                    "Zombie run id=%s for task %s reaped (started_at=%s, timeout=%s)",
                    running['id'], task_id, started_at, self.ZOMBIE_RUN_TIMEOUT,
                )
                self.complete_run(
                    running['id'],
                    success=False,
                    error=(
                        f"zombie run reaped: running 超过 {self.ZOMBIE_RUN_TIMEOUT}，"
                        f"进程疑似被杀，自动判死放行"
                    ),
                )
            else:
                run_id = running['id']
                raise ValueError(
                    f"Task {task_id} is already running (run_id={run_id}, started at {running.get('started_at', 'unknown')}). "
                    f"Please wait for the current execution to complete."
                )

        task_name = task.get("name", str(task_id))
        command = task["command"]
        params = task.get("params") or {}

        # Parse params JSON if it came back as a string
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {}

        run_id = self.create_run(task_id)

        try:
            handler_result = self._execute_command(command, params)
            self.complete_run(run_id, success=True, result=handler_result)
            logger.info(
                "Task %r (id=%s) completed successfully", task_name, task_id
            )
            return {
                "task_id": task_id,
                "task_name": task_name,
                "run_id": run_id,
                "status": "success",
                "result": handler_result,
            }
        except Exception as exc:
            import traceback
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(
                "Task %r (id=%s) failed: %s\n%s",
                task_name, task_id, error_msg, traceback.format_exc()
            )
            self.complete_run(run_id, success=False, error=error_msg)
            return {
                "task_id": task_id,
                "task_name": task_name,
                "run_id": run_id,
                "status": "failed",
                "error": error_msg,
            }
        finally:
            # 任务在调度线程内执行可能遗留 ORM scoped session（idle in transaction
            # 连接泄漏——2026-08-02 FastAPI 托管 SchedulerService 后实测每次任务
            # 执行泄漏 1 个连接）。每次执行后强制回收。
            try:
                from infrastructure.persistence.orm import close_session
                close_session()
            except Exception:
                pass

    def run_loop(self) -> None:
        """Blocking loop that checks for due tasks every 30 seconds.

        Installs SIGTERM / SIGINT handlers for graceful shutdown.
        Call :meth:`stop_loop` from another thread to stop.
        """
        self._running = True

        def _handle_shutdown(signum: int, frame: Any) -> None:
            logger.info(
                "Received signal %s — stopping scheduler loop", signum
            )
            self._running = False

        # Signal handlers only work in the main thread
        try:
            previous_sigterm = signal.signal(signal.SIGTERM, _handle_shutdown)
            previous_sigint = signal.signal(signal.SIGINT, _handle_shutdown)
            _signals_registered = True
        except ValueError:
            logger.info("Scheduler running in background thread — signal handlers not available")
            _signals_registered = False

        logger.info(
            "Scheduler loop started (interval=%ss)", self._loop_interval
        )
        try:
            while self._running:
                try:
                    due_results = self.run_due_tasks()
                    if due_results:
                        succeeded = sum(
                            1 for r in due_results if r["status"] == "success"
                        )
                        failed = sum(
                            1 for r in due_results if r["status"] == "failed"
                        )
                        logger.info(
                            "Due tasks: %d succeeded, %d failed",
                            succeeded,
                            failed,
                        )
                except Exception as exc:
                    logger.error("Error in scheduler loop iteration: %s", exc)
                finally:
                    # run_due_tasks 即使无到期任务也会 SELECT scheduler_tasks，
                    # 线程级 scoped session 不释放则连接在两次轮询间呈
                    # idle in transaction（挡 autovacuum/持旧快照）。
                    # 任务级 finally（_run_task）已有关闭，这里是轮询级兜底
                    # （2026-08-18 后台线程连接治理）。
                    try:
                        from infrastructure.persistence.orm import close_session
                        close_session()
                    except Exception:
                        pass
                time.sleep(self._loop_interval)
        finally:
            if _signals_registered:
                signal.signal(signal.SIGTERM, previous_sigterm)
                signal.signal(signal.SIGINT, previous_sigint)
            logger.info("Scheduler loop stopped")

    def stop_loop(self) -> None:
        """Signal the running loop to stop (thread-safe)."""
        self._running = False
        logger.info("Scheduler loop stop requested")

    # ==================================================================
    # Command dispatch — delegates to JobRegistry
    # ==================================================================

    def _execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command via JobRegistry (pure scheduler, no business logic)."""
        import asyncio
        from application.jobs.job_registry import job_registry

        result = asyncio.run(job_registry.execute(command, params or {}))
        return {
            "action": result.action,
            "status": "success" if result.success else "failed",
            "message": result.message,
            "error": result.error,
            "details": result.details,
        }

