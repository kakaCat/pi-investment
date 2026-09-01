"""
调度任务Repository - 实现 ISchedulerRepository 接口

使用 SQLAlchemy ORM 操作 quant.scheduler_tasks 和 quant.scheduler_runs 表。
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import and_, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domain.ports import ISchedulerRepository
from infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models.scheduler import (
    SchedulerTaskConfig,
    SchedulerRun,
)
from infrastructure.scheduler.scheduler import next_run_time as _calc_next_run_time, parse_cron

logger = logging.getLogger(__name__)


class SchedulerRepository(ISchedulerRepository):
    """调度任务仓储 - SQLAlchemy ORM 实现"""

    def __init__(self, session=None):
        self._session = session

    @property
    def session(self):
        return self._session or get_session()

    def _safe_rollback(self):
        try:
            self.session.rollback()
        except Exception as e:
            logger.warning(f"rollback failed: {e}")

    def _row_to_dict(self, row) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return {c.key: getattr(row, c.key) for c in row.__table__.columns}

    # ── Task CRUD ──

    def add_task(
        self,
        name: str,
        cron_expression: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
    ) -> int:
        parse_cron(cron_expression)

        existing = self.session.query(SchedulerTaskConfig).filter_by(name=name).first()
        if existing is not None:
            raise ValueError(f"Task name {name!r} already exists")

        next_run = _calc_next_run_time(cron_expression)
        config = SchedulerTaskConfig(
            name=name,
            description=description,
            cron_expression=cron_expression,
            command=command,
            params=params or {},
            is_enabled=True,
            next_run_at=next_run,
        )
        try:
            self.session.add(config)
            self.session.commit()
            self.session.refresh(config)
            logger.info("Task %r added (id=%s)", name, config.id)
            return config.id
        except Exception:
            self.session.rollback()
            raise

    def remove_task(self, task_id: int) -> bool:
        try:
            config = self.session.get(SchedulerTaskConfig, task_id)
            if config is None:
                return False
            self.session.delete(config)
            self.session.commit()
            logger.info("Task id=%s removed", task_id)
            return True
        except Exception:
            self.session.rollback()
            raise

    def update_task(self, task_id: int, **kwargs) -> bool:
        allowed = {"name", "description", "cron_expression", "command", "params", "is_enabled"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        if "cron_expression" in updates:
            updates["next_run_at"] = _calc_next_run_time(updates["cron_expression"])
        elif updates.get("is_enabled") is True:
            task = self.get_task(task_id)
            if task is not None:
                updates["next_run_at"] = _calc_next_run_time(task["cron_expression"])

        if "params" in updates and isinstance(updates["params"], dict):
            updates["params"] = json.dumps(updates["params"])

        try:
            config = self.session.get(SchedulerTaskConfig, task_id)
            if config is None:
                return False
            for key, value in updates.items():
                setattr(config, key, value)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        try:
            config = self.session.get(SchedulerTaskConfig, task_id)
            return self._row_to_dict(config)
        except Exception:
            self._safe_rollback()
            return None

    def get_task_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        try:
            config = self.session.query(SchedulerTaskConfig).filter_by(name=name).first()
            return self._row_to_dict(config)
        except Exception:
            self._safe_rollback()
            return None

    def list_tasks(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        try:
            query = self.session.query(SchedulerTaskConfig)
            if enabled_only:
                query = query.filter_by(is_enabled=True)
            return [self._row_to_dict(r) for r in query.all()]
        except Exception:
            self._safe_rollback()
            return []

    def count_tasks(self, enabled_only: bool = False) -> int:
        try:
            query = self.session.query(func.count(SchedulerTaskConfig.id))
            if enabled_only:
                query = query.filter_by(is_enabled=True)
            return query.scalar() or 0
        except Exception:
            self._safe_rollback()
            return 0

    def enable_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        next_run = _calc_next_run_time(task["cron_expression"])
        try:
            config = self.session.get(SchedulerTaskConfig, task_id)
            config.is_enabled = True
            config.next_run_at = next_run
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def disable_task(self, task_id: int) -> bool:
        try:
            config = self.session.get(SchedulerTaskConfig, task_id)
            if config is None:
                return False
            config.is_enabled = False
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    # ── Run Lifecycle ──

    def create_run(self, task_id: int) -> int:
        now = datetime.now(timezone.utc)
        run = SchedulerRun(
            task_id=task_id,
            status="running",
            started_at=now,
        )
        try:
            self.session.add(run)
            config = self.session.get(SchedulerTaskConfig, task_id)
            if config:
                config.last_run_at = now
                config.last_status = "running"
            self.session.commit()
            self.session.refresh(run)
            return run.id
        except Exception:
            self.session.rollback()
            raise

    def complete_run(
        self,
        run_id: int,
        success: bool = True,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        status = "success" if success else "failed"
        now = datetime.now(timezone.utc)
        try:
            run = self.session.get(SchedulerRun, run_id)
            if run is None:
                return False
            run.status = status
            run.completed_at = now
            run.result = result
            run.error = error
            if run.started_at:
                run.duration_ms = int((now - run.started_at).total_seconds() * 1000)

            config = self.session.get(SchedulerTaskConfig, run.task_id)
            if config:
                config.last_status = status
                config.last_error = error
                config.next_run_at = _calc_next_run_time(config.cron_expression)

            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        try:
            run = self.session.get(SchedulerRun, run_id)
            return self._row_to_dict(run)
        except Exception:
            self._safe_rollback()
            return None

    def list_runs(
        self,
        task_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
        statuses: Optional[List[str]] = None,
        date_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            query = self.session.query(SchedulerRun)
            if task_id is not None:
                query = query.filter(SchedulerRun.task_id == task_id)
            if statuses:
                query = query.filter(SchedulerRun.status.in_(statuses))
            if date_filter:
                query = query.filter(func.date(SchedulerRun.started_at) == date_filter)
            query = query.order_by(SchedulerRun.started_at.desc()).offset(offset).limit(limit)
            return [self._row_to_dict(r) for r in query.all()]
        except Exception:
            self._safe_rollback()
            return []

    def count_runs(
        self,
        task_id: Optional[int] = None,
        statuses: Optional[List[str]] = None,
        date_filter: Optional[str] = None,
    ) -> int:
        try:
            query = self.session.query(func.count(SchedulerRun.id))
            if task_id is not None:
                query = query.filter(SchedulerRun.task_id == task_id)
            if statuses:
                query = query.filter(SchedulerRun.status.in_(statuses))
            if date_filter:
                query = query.filter(func.date(SchedulerRun.started_at) == date_filter)
            return query.scalar() or 0
        except Exception:
            self._safe_rollback()
            return 0

    # ── Health Check ──

    def find_zombie_runs(self, threshold_hours: int = 1) -> List[Dict[str, Any]]:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
            rows = (
                self.session.query(SchedulerRun, SchedulerTaskConfig.name)
                .join(SchedulerTaskConfig, SchedulerRun.task_id == SchedulerTaskConfig.id)
                .filter(
                    SchedulerRun.status == "running",
                    SchedulerRun.started_at < cutoff,
                )
                .all()
            )
            return [
                {
                    "run_id": run.id,
                    "name": name,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "hours_running": (datetime.now(timezone.utc) - run.started_at).total_seconds() / 3600
                    if run.started_at
                    else 0,
                }
                for run, name in rows
            ]
        except Exception:
            self._safe_rollback()
            return []

    def find_missed_tasks(self, threshold_hours: int = 24) -> List[Dict[str, Any]]:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
            rows = (
                self.session.query(SchedulerTaskConfig)
                .filter(
                    SchedulerTaskConfig.is_enabled == True,
                    ~SchedulerTaskConfig.cron_expression.like("managed_by_agent_%"),
                    (SchedulerTaskConfig.last_run_at == None) | (SchedulerTaskConfig.last_run_at < cutoff),
                )
                .all()
            )
            return [
                {
                    "name": r.name,
                    "cron_expression": r.cron_expression,
                    "last_run_at": r.last_run_at.isoformat() if r.last_run_at else "NEVER",
                }
                for r in rows
            ]
        except Exception:
            self._safe_rollback()
            return []

    def find_high_failure_tasks(
        self, days: int = 7, min_runs: int = 3, fail_rate_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            rows = (
                self.session.query(
                    SchedulerTaskConfig.name,
                    func.count(SchedulerRun.id).label("total"),
                    func.sum(func.cast(SchedulerRun.status == "failed", func.cast(0, func.cast(1, SchedulerRun.id)))).label("failed"),
                )
                .join(SchedulerRun, SchedulerRun.task_id == SchedulerTaskConfig.id)
                .filter(SchedulerRun.started_at > cutoff)
                .group_by(SchedulerTaskConfig.name)
                .having(func.count(SchedulerRun.id) >= min_runs)
                .all()
            )
            result = []
            for name, total, failed in rows:
                total = total or 0
                failed = failed or 0
                if total > 0 and failed / total > fail_rate_threshold:
                    result.append({
                        "name": name,
                        "total": total,
                        "failed": failed,
                        "fail_rate": failed / total,
                    })
            return result
        except Exception:
            self._safe_rollback()
            return []

    def count_enabled_tasks(self) -> int:
        try:
            return (
                self.session.query(func.count(SchedulerTaskConfig.id))
                .filter(SchedulerTaskConfig.is_enabled == True)
                .scalar()
                or 0
            )
        except Exception:
            self._safe_rollback()
            return 0
