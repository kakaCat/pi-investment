"""
调度任务Repository - 实现 ISchedulerRepository 接口

使用 SQLAlchemy ORM 操作 quant.scheduler_tasks 和 quant.scheduler_runs 表。
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy import and_, case, func, or_, text
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
        task_type: str = 'cron',
    ) -> int:
        # 验证 task_type
        valid_types = ['cron', 'delay', 'interval', 'once']
        if task_type not in valid_types:
            raise ValueError(f"Invalid task_type {task_type!r}, must be one of {valid_types}")

        # 只有 cron 类型需要验证 cron 表达式；Agent OS 托管伪任务（cron 保留字
        # managed_by_agent_*）不是真实 cron，跳过校验与 next_run 计算
        # （2026-09-01 修复：webhook 新任务名写库曾因 parse_cron 抛异常被吞）。
        _is_agent_os_placeholder = str(cron_expression).startswith("managed_by_agent_")
        if task_type == 'cron' and not _is_agent_os_placeholder:
            parse_cron(cron_expression)

        existing = self.session.query(SchedulerTaskConfig).filter_by(name=name).first()
        if existing is not None:
            raise ValueError(f"Task name {name!r} already exists")

        # 延迟任务和一次性任务不需要计算 next_run（由 APScheduler 管理）
        next_run = None
        if task_type == 'cron' and not _is_agent_os_placeholder:
            next_run = _calc_next_run_time(cron_expression)

        config = SchedulerTaskConfig(
            name=name,
            description=description,
            cron_expression=cron_expression,
            command=command,
            params=params or {},
            is_enabled=True,
            task_type=task_type,
            next_run_at=next_run,
        )
        try:
            self.session.add(config)
            self.session.commit()
            self.session.refresh(config)
            logger.info("Task %r added (id=%s, type=%s)", name, config.id, task_type)
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
        allowed = {"name", "description", "cron_expression", "command", "params", "is_enabled", "task_type"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        # 验证 task_type
        if "task_type" in updates:
            valid_types = ['cron', 'delay', 'interval', 'once']
            if updates["task_type"] not in valid_types:
                raise ValueError(f"Invalid task_type {updates['task_type']!r}, must be one of {valid_types}")

        # 获取当前任务配置
        task = self.get_task(task_id)
        if task is None:
            return False

        # 确定最终的 task_type
        final_task_type = updates.get("task_type", task.get("task_type", "cron"))

        # 只有 cron 类型需要更新 next_run_at
        if "cron_expression" in updates and final_task_type == "cron":
            updates["next_run_at"] = _calc_next_run_time(updates["cron_expression"])
        elif updates.get("is_enabled") is True and final_task_type == "cron":
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

    def create_run(self, task_id: int, started_at: Optional[datetime] = None) -> int:
        # P0-C（2026-09-10 w-23c70356 审计）：started_at 原本硬用"写库时刻"，
        # webhook 路径（先跑完 handler 再写库）因此把 started_at/completed_at 都记成
        # 写库瞬间 → duration_ms 恒为 3~15ms，执行时间列对 Agent OS 委托任务完全失真
        # （实测 market_style_update 真实 elapsed 0.16s、market_daily_snapshot 3.3s，
        # 而 run.duration_ms 显示 11ms/13ms）。允许调用方传入真实开始时刻；
        # 不传（APScheduler 路径在跑任务前调用）保持 now() 原语义不变。
        now = datetime.now(timezone.utc)
        run = SchedulerRun(
            task_id=task_id,
            status="running",
            started_at=started_at or now,
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
        completed_at: Optional[datetime] = None,
    ) -> bool:
        status = "success" if success else "failed"
        # P0-C：同上，允许传入真实完成时刻（webhook 路径在 handler 结束后写库，
        # 不传时用 now()，与 APScheduler 路径原语义一致）。
        now = completed_at or datetime.now(timezone.utc)
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
                # Agent OS 托管伪任务（cron 保留字）无真实调度，跳过 next_run 计算
                # （2026-09-01 修复：complete_run 曾因 parse_cron 抛异常致 run 卡 running）
                if not str(config.cron_expression).startswith("managed_by_agent_"):
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

    def recover_orphan_runs(self, note: str = "孤儿 run：进程重启遗留") -> List[int]:
        """启动时回收上一进程遗留的 running run（闭环为 failed）。

        2026-09-11 w-23c70356：APScheduler 运行在 API 进程内，进程重启会打断 run 的
        收尾记账，run 行会永久停留 running（实例 run 3527 自 2026-09-10 22:00 卡死
        1.9 小时，只能人工闭环）。启动时统一回收，避免僵尸累积与看门狗误报。
        安全性：本进程刚启动时不存在"本进程在跑"的 run；仅跳过 60 秒内创建的行，
        防止与同进程并发启动的 run 竞争。
        """
        try:
            now = datetime.now(timezone.utc)
            guard = now - timedelta(seconds=60)
            rows = (
                self.session.query(SchedulerRun)
                .filter(SchedulerRun.status == "running")
                .all()
            )
            recovered: List[int] = []
            touched_tasks: set = set()
            for run in rows:
                if run.started_at is not None and run.started_at > guard:
                    continue  # 刚创建，可能仍在执行（同进程并发）
                run.status = "failed"
                run.completed_at = now
                run.error = note
                if run.started_at:
                    run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
                recovered.append(run.id)
                touched_tasks.add(run.task_id)

            # 同步回写任务行（2026-09-11 w-f436d4ea）：原先只闭环 run 行，任务行的
            # last_status/last_error/next_run_at **一个都不动**。后果三连（实测任务 232
            # 『每日数据质量检查』09-10、09-11 两次被进程重启打断）：
            #   ① 任务列表显示 failed 却**没有任何原因**——原因只躺在 scheduler_runs.error
            #      里，看板与排查入口（scheduler_tasks.last_error）读不到；
            #   ② next_run_at 停在被打断的那次时刻（实测停在 2026-09-11 22:00:00）不推进；
            #   ③ 于是「任务失败」这件事在运维面上表现为「失败且无可解释信息」。
            # 回写口径与 complete_run 保持一致（含 managed_by_agent_ 伪任务跳过 next_run）。
            for task_id in touched_tasks:
                config = self.session.get(SchedulerTaskConfig, task_id)
                if config is None:
                    continue
                config.last_status = "failed"
                config.last_error = note
                if not str(config.cron_expression).startswith("managed_by_agent_"):
                    config.next_run_at = _calc_next_run_time(config.cron_expression)

            if recovered:
                self.session.commit()
            return recovered
        except Exception:
            self.session.rollback()
            raise

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
            # ADR-002（2026-09-01）后 v2 本地 APScheduler 为主调度：已入 job store
            # 且 next_run_time 在未来的任务视为"已排期"，即使 last_run 陈旧也不算
            # missed（切换日 cron 时点已过不补跑是设计内行为，非故障）。
            now_epoch = datetime.now(timezone.utc).timestamp()
            scheduled_task_ids: set = set()
            try:
                rows = self.session.execute(
                    text(
                        "SELECT id FROM public.apscheduler_jobs "
                        "WHERE id LIKE 'task_%' AND next_run_time > :now_epoch"
                    ),
                    {"now_epoch": now_epoch},
                ).fetchall()
                scheduled_task_ids = {
                    int(r[0].split("_", 1)[1]) for r in rows if "_" in r[0]
                }
            except Exception as e:
                logger.warning(f"apscheduler jobstore query failed, fallback to strict check: {e}")

            rows = (
                self.session.query(SchedulerTaskConfig)
                .filter(
                    SchedulerTaskConfig.is_enabled == True,
                    ~SchedulerTaskConfig.cron_expression.like("managed_by_agent_%"),
                    (SchedulerTaskConfig.last_run_at == None) | (SchedulerTaskConfig.last_run_at < cutoff),
                )
                .all()
            )
            result = []
            for r in rows:
                if r.id in scheduled_task_ids:
                    continue  # 已由本地 APScheduler 排期（next_run 在未来），不算 missed
                result.append({
                    "name": r.name,
                    "cron_expression": r.cron_expression,
                    "last_run_at": r.last_run_at.isoformat() if r.last_run_at else "NEVER",
                })
            return result
        except Exception:
            self._safe_rollback()
            return []

    def find_high_failure_tasks(
        self, days: int = 7, min_runs: int = 3, fail_rate_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            # 排除"孤儿 run"（error 含 孤儿/进程重启 字样）：进程重启打断的 run 是
            # 调度环境事故，不代表任务逻辑失败，计入失败率会造成误报。
            # P0-B 修复（2026-09-10 w-23c70356 审计）：
            # ① 原失败计数 func.sum(func.cast(status=="failed", func.cast(0, func.cast(1, id))))
            #    是非法聚合表达式，实测恒为 0 —— 真失败也测不出来（实证：任务 325
            #    market_style_update 近 7 天 4 次运行 4 次 failed，本方法仍返回 []），
            #    失败率看门狗形同虚设；
            # ② 只统计行级 status，漏掉"行级 success + 内层 result 报错"的静默失败
            #    （同次审计发现 2026-06-04 起 40 条静默失败全部逃过看门狗）。
            # 现改为 case() 显式计数，并把内层失败一并计入 failed。
            inner_failed = or_(
                SchedulerRun.result["status"].astext.in_(["failed", "error"]),
                SchedulerRun.result["success"].astext == "false",
                and_(
                    SchedulerRun.result["status"].astext.is_(None),
                    SchedulerRun.result["error"].astext.isnot(None),
                ),
            )
            is_failed = case(
                (or_(SchedulerRun.status == "failed", inner_failed), 1),
                else_=0,
            )
            rows = (
                self.session.query(
                    SchedulerTaskConfig.name,
                    func.count(SchedulerRun.id).label("total"),
                    func.sum(is_failed).label("failed"),
                )
                .join(SchedulerRun, SchedulerRun.task_id == SchedulerTaskConfig.id)
                .filter(
                    SchedulerRun.started_at > cutoff,
                    or_(
                        SchedulerRun.error.is_(None),
                        ~SchedulerRun.error.like("%孤儿%"),
                        ~SchedulerRun.error.like("%进程重启%"),
                    ),
                )
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
