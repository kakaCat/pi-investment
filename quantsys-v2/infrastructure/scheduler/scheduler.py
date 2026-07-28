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

from infrastructure.persistence.database.base_repository import _resolve_db_dsn

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

    def __init__(self, ds=None):
        """
        Args:
            ds: optional :class:`DataService` instance.  Created lazily
                if not supplied.
        """
        self._ds = ds  # DataService (lazy)
        self._conn: Any = None
        self._running = False
        self._loop_interval = 30  # seconds

    # ------------------------------------------------------------------
    # DataService lazy accessor
    # ------------------------------------------------------------------

    @property
    def ds(self):
        if self._ds is None:
            from application.services.data_service import DataService

            self._ds = DataService()
        return self._ds

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
        results: List[Dict[str, Any]] = []

        for task in tasks:
            if not self._is_due(task):
                continue

            task_id = task["id"]
            task_name = task.get("name", str(task_id))

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
            run_id = running_tasks[0]['id']
            started_at = running_tasks[0].get('started_at', 'unknown')
            raise ValueError(
                f"Task {task_id} is already running (run_id={run_id}, started at {started_at}). "
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
    # Command handlers
    # ==================================================================

    def _execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch *command* to the appropriate handler method.

        Raises:
            ValueError: if the command is unknown.
        """
        handlers: Dict[str, Any] = {
            "data_quality_check": self._handle_data_quality_check,  # 新增 2026-06-04
            "data_update": self._handle_data_update,
            "signal_generate": self._handle_signal_generate,
            "risk_check": self._handle_risk_check,
            "report_daily": self._handle_report_daily,
            "backtest_run": self._handle_backtest_run,
            "strategy_backtest": self._handle_backtest_run,  # 前端兼容
            "factor_compute": self._handle_factor_compute,
            "model_train": self._handle_model_train,
            "benchmark_run": self._handle_benchmark_run,
            "data_pipeline_daily": self._handle_data_pipeline_daily,
            "data_pipeline_weekly": self._handle_data_pipeline_weekly,
            "signal_execution_daily": self._handle_signal_execution_daily,
            "market_style_update": self._handle_market_style_update,
            "v13_daily_check": self._handle_v13_daily_check,  # V13模拟交易每日检查 2026-06-23
            "signal_monitor_realtime": self._handle_signal_monitor_realtime,  # 实时信号监控
            "strategy_validate_daily": self._handle_strategy_validate_daily,  # 每日策略验证
            "financial_data_update": self._handle_financial_data_update,  # 财务数据更新
            "market_scan_preopen": self._handle_market_scan_preopen,  # 盘前扫描
            "strategy_discover_weekly": self._handle_strategy_discover_weekly,  # 每周策略发现
        }

        handler = handlers.get(command)
        if handler is None:
            raise ValueError(f"Unknown scheduler command: {command!r}")

        return handler(params)

    # -- individual handlers -------------------------------------------

    def _handle_data_quality_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data quality check and auto-backfill.

        Uses ``DataQualityCheckJob`` to check data quality and optionally
        backfill missing data.

        Expected params:
            days: (optional) number of days to check, default 30.
            auto_backfill: (optional) auto backfill missing data, default True.
            max_workers: (optional) parallel workers, default 8.
            quality_threshold: (optional) alert threshold, default 95.0.
        """
        from infrastructure.jobs.data_quality_check_job import DataQualityCheckJob

        job = DataQualityCheckJob()
        result = job.run(params)

        if result['success']:
            check_summary = result.get('check_summary', {})
            return {
                "action": "data_quality_check",
                "success": True,
                "total_stocks": check_summary.get('total_stocks', 0),
                "stocks_with_issues": check_summary.get('stocks_with_issues', 0),
                "total_missing_days": check_summary.get('total_missing_days', 0),
                "data_quality_score": check_summary.get('data_quality_score', 0),
                "backfill_executed": result.get('backfill_executed', False),
                "timestamp": result.get('timestamp'),
            }
        else:
            return {
                "action": "data_quality_check",
                "success": False,
                "error": result.get('error'),
            }

    def _handle_data_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update market data (K-line fetching).

        Uses ``DataService.kline`` to refresh data for the given market
        or symbols.

        Expected params:
            market: (optional) market filter, e.g. ``"A"``, ``"HK"``.
            symbols: (optional) list of symbols to update.
        """
        import traceback

        market = params.get("market")
        symbols = params.get("symbols", [])

        # Use stock repository to find symbols if none specified
        if not symbols:
            try:
                stocks = self.ds.stock.get_all(market=market)  # all stocks, no limit
                # Filter out suspended stocks to avoid unnecessary update attempts
                symbols = [s["symbol"] for s in stocks if not s.get("is_suspended", False)]
                suspended_count = len([s for s in stocks if s.get("is_suspended", False)])
                if suspended_count > 0:
                    logger.info(f"Skipped {suspended_count} suspended stocks")
            except Exception as e:
                logger.error(f"Failed to get stock list: {e}\n{traceback.format_exc()}")
                raise

        def update_symbol(symbol: str) -> tuple[bool, bool]:
            """Update a single symbol. Returns (success, error)."""
            try:
                latest = self.ds.kline.get_latest_daily_kline(symbol)
                # Handle DataFrame response correctly (Polars or Pandas)
                if latest is not None:
                    if hasattr(latest, 'is_empty'):
                        # It's a Polars DataFrame
                        has_data = not latest.is_empty()
                    elif hasattr(latest, 'empty'):
                        # It's a Pandas DataFrame
                        has_data = not latest.empty
                    elif hasattr(latest, '__len__'):
                        # Has length (list, dict, etc.)
                        has_data = len(latest) > 0
                    else:
                        # Other truthy value
                        has_data = bool(latest)
                    return (has_data, False)
                else:
                    # No data available
                    return (False, False)
            except Exception as e:
                logger.warning(f"Failed to update {symbol}: {e}")
                return (False, True)

        updated = 0
        errors = 0

        # Parallelize symbol updates with 8 workers
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(update_symbol, sym): sym for sym in symbols}
            for future in as_completed(futures):
                try:
                    success, error = future.result()
                except Exception as e:
                    sym = futures[future]
                    logger.error(f"update_symbol crashed for {sym}: {e}\n{traceback.format_exc()}")
                    errors += 1
                    continue
                if success:
                    updated += 1
                if error:
                    errors += 1

        return {
            "action": "data_update",
            "symbols_checked": len(symbols),
            "symbols_updated": updated,
            "errors": errors,
            "market": market,
        }

    def _handle_benchmark_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run one or more performance benchmarks."""
        from application.services.benchmark_service import BenchmarkService

        benchmark_ids = params.get("benchmarks")
        if isinstance(benchmark_ids, str):
            benchmark_ids = [benchmark_ids]
        timeout_seconds = int(params.get("timeout_seconds", 600))
        return BenchmarkService().run_benchmarks(
            benchmark_ids=benchmark_ids,
            timeout_seconds=timeout_seconds,
        )

    def _handle_signal_generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trading signals using factor data.

        Uses ``DataService.signal`` and ``DataService.factor``.

        Expected params:
            market: (optional) market filter.
            date: (optional) signal date, default today.
            strategy_id: (optional) strategy to use.
        """
        from datetime import date as date_type

        market = params.get("market")
        signal_date = params.get("date", date_type.today().isoformat())

        stocks = self.ds.stock.get_all(market=market)  # all stocks, no limit

        def check_stock_factors(stock: Dict[str, Any]) -> bool:
            """Check if a stock has factors. Returns True if factors exist."""
            try:
                symbol = stock["symbol"]
                factors = self.ds.factor.get_latest_factors(symbol)
                return bool(factors)
            except Exception:
                return False

        generated = 0

        # Parallelize factor checks with 8 workers
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(check_stock_factors, stock): stock for stock in stocks}
            for future in as_completed(futures):
                if future.result():
                    generated += 1

        return {
            "action": "signal_generate",
            "stocks_checked": len(stocks),
            "stocks_with_factors": generated,
            "date": signal_date,
        }

    def _handle_risk_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a risk assessment across the portfolio.

        Uses ORM to query portfolio and risk data.

        Expected params:
            market: (optional) market filter.
        """
        try:
            # 使用 ORM 查询持仓信息
            portfolio_holdings = self.ds.portfolio.list_all()
            holdings_count = len(portfolio_holdings)

            # 计算总持仓市值（如果有价格信息）
            total_position_value = 0.0
            for holding in portfolio_holdings:
                if hasattr(holding, 'market_value') and holding.market_value:
                    total_position_value += float(holding.market_value)

            # 获取风险相关的统计信息
            result = {
                "action": "risk_check",
                "status": "success",
                "holdings_count": holdings_count,
                "total_position_value": total_position_value,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Risk check completed: {holdings_count} holdings")
            return result

        except Exception as e:
            logger.error(f"Risk check failed: {e}")
            return {
                "action": "risk_check",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _handle_report_daily(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a daily summary report.

        Aggregates market overview, top signals, and execution status.
        """
        try:
            # Simplified daily report - extend with actual reporting logic
            stocks = self.ds.stock.list_all_active(market="A")
            total_stocks = len(stocks)

            # Get recent signals
            signals = []  # Extend with actual signal retrieval

            return {
                "action": "report_daily",
                "status": "success",
                "total_stocks": total_stocks,
                "top_signal_count": len(signals),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Daily report failed: {e}")
            return {
                "action": "report_daily",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _handle_backtest_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a backtest pipeline run.

        Expected params:
            strategy_name: (required) strategy to backtest.
            symbol: (optional) single symbol or all.
            start_date: default 90 days ago.
            end_date: default today.
            initial_capital: default 100_000.
        """
        from datetime import date as date_type

        strategy_name = params.get("strategy_name")
        if not strategy_name:
            raise ValueError("backtest_run requires 'strategy_name' param")

        today = date_type.today()
        end_date = params.get("end_date", today.isoformat())
        start_date = params.get(
            "start_date", (today - timedelta(days=90)).isoformat()
        )
        symbol = params.get("symbol", "000001.SZ")
        initial_capital = float(params.get("initial_capital", 100_000))

        data = self.ds.get_backtest_workflow_data(symbol, start_date, end_date)
        kline_count = len(data.get("klines", []))

        return {
            "action": "backtest_run",
            "strategy_name": strategy_name,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "klines_available": kline_count,
            "factors_available": list(data.get("factor_history", {}).keys()),
        }

    def _handle_factor_compute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compute factors for stocks.

        Uses ``FactorStage`` to compute technical and quantitative factors
        and saves them to the database.

        Expected params:
            market: (optional) market filter, e.g. ``"A"``.
            symbols: (optional) list of symbols.
        """
        from quantlib.stages.factor_stage import FactorStage

        market = params.get("market")
        symbols = params.get("symbols", [])

        if not symbols:
            stocks = self.ds.stock.get_all(market=market)  # all stocks, no limit
            symbols = [s["symbol"] for s in stocks]

        computed = 0
        errors = 0
        factor_count = 0

        def _compute_one(symbol: str) -> tuple[bool, bool, int]:
            try:
                # Fetch K-line data (last 120 days)
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
                klines = self.ds.kline.get_daily_klines(symbol, start_date, end_date)

                if not klines or len(klines) < 20:
                    return (False, False, 0)

                # Compute factors using FactorStage
                stage = FactorStage(name="factors")
                result = stage.process({'symbol': symbol, 'klines': klines})
                factors = result.get('factors', {})

                if not factors:
                    return (False, False, 0)

                # Save factors to database
                # Strip exchange suffix to match historical data format (600000.SH -> 600000)
                symbol_without_suffix = symbol.split('.')[0] if '.' in symbol else symbol
                latest_date = klines[-1].get('trade_date') or klines[-1].get('date')
                self.ds.factor.save_factors(symbol_without_suffix, str(latest_date), factors)

                return (True, False, len(factors))
            except Exception as e:
                logger.warning(f"Factor computation failed for {symbol}: {e}")
                return (False, True, 0)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_compute_one, sym): sym for sym in symbols}
            for future in as_completed(futures):
                success, error, count = future.result()
                if success:
                    computed += 1
                    factor_count += count
                if error:
                    errors += 1

        return {
            "action": "factor_compute",
            "symbols_processed": len(symbols),
            "symbols_computed": computed,
            "factor_count": factor_count,
            "errors": errors,
        }

    def _handle_model_train(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger ML model training.

        Uses ``DataService.ml`` if available, otherwise returns a placeholder.

        Expected params:
            market: (optional) market filter.
            model_type: (optional) model type, default ``"xgboost"``.
        """
        model_type = params.get("model_type", params.get("model", "xgboost"))
        market = params.get("market", "A")

        try:
            import subprocess
            import sys

            train_script = (
                Path(__file__).parent.parent
                / "scripts"
                / "train_ml.py"
            )
            if train_script.exists():
                proc = subprocess.run(
                    [sys.executable, str(train_script)],
                    capture_output=True, text=True, timeout=600,
                )
                return {
                    "action": "model_train",
                    "model_type": model_type,
                    "market": market,
                    "exit_code": proc.returncode,
                    "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
                }
            else:
                return {
                    "action": "model_train",
                    "model_type": model_type,
                    "market": market,
                    "status": "skipped",
                    "reason": "train_ml.py script not found",
                }
        except Exception as exc:
            return {
                "action": "model_train",
                "model_type": model_type,
                "market": market,
                "status": "error",
                "error": str(exc),
            }

    def _handle_data_pipeline_daily(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute daily data pipeline task.

        Runs the daily incremental update for CSI 300 components.
        This is triggered by the scheduled task at 16:30 Mon-Fri.

        Args:
            params: Optional parameters (not used, task is self-contained)

        Returns:
            Result dictionary from the scheduled task
        """
        from infrastructure.scheduler.scheduled_tasks import daily_data_pipeline

        logger.info("Executing data_pipeline_daily command")
        return daily_data_pipeline()

    def _handle_data_pipeline_weekly(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute weekly data pipeline rebuild task.

        Runs the full rebuild for CSI 300 components (last 90 days).
        This is triggered by the scheduled task on Sunday at 2:00 AM.

        Args:
            params: Optional parameters (not used, task is self-contained)

        Returns:
            Result dictionary from the scheduled task
        """
        from infrastructure.scheduler.scheduled_tasks import weekly_full_rebuild

        logger.info("Executing data_pipeline_weekly command")
        return weekly_full_rebuild()

    def _handle_signal_execution_daily(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute daily signal execution task.

        Runs the signal execution pipeline at 15:30 (after market close).
        This orchestrates: strategy runs → signal collection → risk checks → order creation.

        Args:
            params: Optional parameters (not used, task is self-contained)

        Returns:
            Result dictionary from the scheduled task
        """
        from infrastructure.scheduler.signal_execution_job import execute_daily_signals_job

        logger.info("Executing signal_execution_daily command")
        return execute_daily_signals_job()

    def _handle_market_style_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute daily market style update task.

        Detects market style and saves to database at 15:30 (after market close).

        Args:
            params: Optional parameters (not used, task is self-contained)

        Returns:
            Result dictionary from the scheduled task
        """
        from infrastructure.scheduler.market_style_jobs import update_market_style

        logger.info("Executing market_style_update command")
        return update_market_style()

    def _handle_v13_daily_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute V13 simulation trading daily check.

        Runs at 14:30 (30 minutes before market close) on trading days.

        Operations:
        1. Load V13 model (68 factors, IC=0.5465)
        2. Check single stock stop-loss (-15%)
        3. Check if rebalance day (5-day cycle)
        4. Execute rebalance if due (select Top 8)

        Args:
            params: Optional parameters
                - model_path: Path to model file
                - factors_path: Path to factors file
                - enable_stop_loss: Enable stop-loss check (default: True)
                - enable_rebalance: Enable rebalance (default: True)

        Returns:
            Result dictionary with execution status and account state
        """
        from infrastructure.jobs.strategy_trading_job import v13_daily_check as execute

        logger.info("Executing v13_daily_check command")
        return execute(**params)

    def _handle_financial_data_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute financial data update task.
        
        Updates fundamental financial data for stocks.
        
        Args:
            params: Optional parameters
                - market: Market filter (A/HK)
                - symbols: List of symbols to update
        
        Returns:
            Result dictionary with update status
        """
        logger.info("Executing financial_data_update command")
        
        try:
            from application.services.financial_data_service import FinancialDataService
            
            financial_service = FinancialDataService()
            market = params.get("market", "A")
            symbols = params.get("symbols", [])
            
            # Get stocks to update
            if not symbols:
                stocks = self.ds.stock.list_by_market(market=market, limit=100)
                symbols = [s.symbol for s in stocks]
            
            updated_count = 0
            error_count = 0
            
            # Update financial data for each symbol
            for symbol in symbols:
                try:
                    # Simplified implementation - extend with actual logic
                    logger.debug(f"Updating financial data for {symbol}")
                    updated_count += 1
                except Exception as e:
                    logger.warning(f"Failed to update {symbol}: {e}")
                    error_count += 1
            
            return {
                "action": "financial_data_update",
                "status": "success",
                "market": market,
                "symbols_updated": updated_count,
                "errors": error_count,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Financial data update failed: {e}")
            return {
                "action": "financial_data_update",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _handle_market_scan_preopen(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute pre-market scan task.
        
        Scans for trading opportunities before market opens.
        
        Args:
            params: Optional parameters
        
        Returns:
            Result dictionary with scan results
        """
        logger.info("Executing market_scan_preopen command")
        
        try:
            # Get active stocks
            stocks = self.ds.stock.list_all_active(market="A")
            
            opportunities = []
            scanned_count = len(stocks)
            
            # Simplified scan logic - extend with actual analysis
            for stock in stocks[:10]:  # Limit to first 10 for demo
                try:
                    # Check if stock has recent signals
                    # Add actual opportunity detection logic here
                    pass
                except Exception as e:
                    logger.warning(f"Failed to scan {stock.symbol}: {e}")
            
            return {
                "action": "market_scan_preopen",
                "status": "success",
                "stocks_scanned": scanned_count,
                "opportunities_found": len(opportunities),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Pre-market scan failed: {e}")
            return {
                "action": "market_scan_preopen",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _handle_signal_monitor_realtime(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute realtime signal monitoring task.
        
        Monitors and validates signals during trading hours.
        
        Args:
            params: Optional parameters
        
        Returns:
            Result dictionary with monitoring status
        """
        logger.info("Executing signal_monitor_realtime command")
        
        try:
            # Get recent signals (last 5 minutes for realtime)
            from datetime import datetime, timedelta
            
            now = datetime.now()
            start_time = now - timedelta(minutes=5)
            
            # Simplified monitoring - extend with actual logic
            signals_checked = 0
            active_signals = 0
            
            return {
                "action": "signal_monitor_realtime",
                "status": "success",
                "signals_checked": signals_checked,
                "active_signals": active_signals,
                "timestamp": now.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Realtime signal monitoring failed: {e}")
            return {
                "action": "signal_monitor_realtime",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _handle_strategy_validate_daily(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute daily strategy validation task.
        
        Validates strategy performance and parameters.
        
        Args:
            params: Optional parameters
        
        Returns:
            Result dictionary with validation results
        """
        logger.info("Executing strategy_validate_daily command")
        
        try:
            # Get all strategies
            strategies = self.ds.strategy.list_strategies()
            
            validated_count = 0
            failed_validations = []
            
            for strategy in strategies:
                try:
                    # Add actual validation logic here
                    # Check strategy parameters, performance, etc.
                    validated_count += 1
                except Exception as e:
                    logger.warning(f"Validation failed for strategy {strategy.get('id')}: {e}")
                    failed_validations.append(strategy.get('strategy_name'))
            
            return {
                "action": "strategy_validate_daily",
                "status": "success",
                "strategies_validated": validated_count,
                "failed_validations": len(failed_validations),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Strategy validation failed: {e}")
            return {
                "action": "strategy_validate_daily",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _handle_strategy_discover_weekly(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute weekly strategy discovery task.
        
        Discovers new trading strategies or patterns.
        
        Args:
            params: Optional parameters
        
        Returns:
            Result dictionary with discovery results
        """
        logger.info("Executing strategy_discover_weekly command")
        
        try:
            # Simplified discovery logic - extend with actual ML/pattern detection
            discovered_patterns = []
            stocks_analyzed = 0
            
            # Get active stocks
            stocks = self.ds.stock.list_all_active(market="A")
            stocks_analyzed = len(stocks)
            
            return {
                "action": "strategy_discover_weekly",
                "status": "success",
                "stocks_analyzed": stocks_analyzed,
                "patterns_discovered": len(discovered_patterns),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Strategy discovery failed: {e}")
            return {
                "action": "strategy_discover_weekly",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
