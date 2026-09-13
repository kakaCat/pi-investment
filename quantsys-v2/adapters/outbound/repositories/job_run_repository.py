"""进程内任务台账仓储（quant.inprocess_job_runs）。

2026-09-14（w-32314d00，REQ-24e15d B2）：该表此前无模型无仓储，读写散在
daily_jobs_bootstrap.py（建表/INSERT/UPDATE/多处分页 SELECT）与
financial_timeliness_check_job.py（当天去重）里。B2 先收口**只读**查询；
B4-c4（同日）补上**写入路径**——bootstrap 的 _mark_running / _mark_done /
孤儿判死 / 终态查询全部改为调用本仓储，SQL 不再出现在 inbound 层。

写入语义要点（与原内联 SQL 逐字对齐，迁移时已在真实库上比对）：
    · **幂等键是 (job_id, run_date)**：mark_running 是 UPSERT，重复调用只刷新
      status/started_at 并清空 finished_at/error，**不动 result**（原 SQL 也只清这两项）；
    · 时间戳一律用 **数据库 now()**（func.now()）而不是进程时钟 —— 原 SQL 就是 now()，
      改成 Python datetime 会让"宿主时钟 vs 库时钟"的偏差进入台账；
    · mark_done 的 result 先按原实现的 json.dumps(..., default=str) 过一遍再交给
      JSONB 类型，保证 default=str 这个兜底（datetime 等不可序列化对象转字符串）
      没有在迁移中丢失。
"""
from __future__ import annotations

import json
import logging
from datetime import date as _date, datetime as _datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import InProcessJobRun

logger = logging.getLogger(__name__)

__all__ = ['JobRunRepository']


class JobRunRepository(BaseORMRepository[InProcessJobRun]):
    """任务台账只读访问。"""

    model = InProcessJobRun

    def get_status(self, job_id: str, run_date: Optional[_date] = None) -> Optional[str]:
        """取某任务在某日（默认今天）的状态；无记录返回 None。

        语义与调用方一致：**"今天跑没跑过"看有没有记录**，而不是看状态值
        （失败也算跑过，避免同一天无限重试）。
        """
        day = run_date or _date.today()
        try:
            row = (
                self.session.query(InProcessJobRun.status)
                .filter(InProcessJobRun.job_id == job_id)
                .filter(InProcessJobRun.run_date == day)
                .limit(1)
                .first()
            )
            return row[0] if row else None
        except Exception as e:  # noqa: BLE001 —— 台账不可读不应阻断业务
            self._safe_rollback()
            logger.warning("读取 inprocess_job_runs 失败（%s/%s）: %s", job_id, day, e)
            raise

    def exists(self, job_id: str, run_date: Optional[_date] = None) -> bool:
        """某任务某日是否已有运行记录（含失败记录）。"""
        try:
            return self.get_status(job_id, run_date) is not None
        except Exception:  # noqa: BLE001
            # 台账不可读时**宁可多跑一次**也不静默不修（与调用方原语义一致）
            return False

    def list_by_date(self, run_date: Optional[_date] = None) -> List[InProcessJobRun]:
        """某日的全部运行记录。"""
        day = run_date or _date.today()
        try:
            return (
                self.session.query(InProcessJobRun)
                .filter(InProcessJobRun.run_date == day)
                .order_by(InProcessJobRun.started_at.asc())
                .all()
            )
        except Exception as e:  # noqa: BLE001
            self._safe_rollback()
            logger.warning("列出 inprocess_job_runs(%s) 失败: %s", day, e)
            return []
    def get_run(self, job_id: str, run_date: str) -> Optional[Dict[str, Any]]:
        """取某任务某日的 {status, started_at}；无记录返回 None。

        与 get_status 的差别：get_status 只回状态字符串，本方法还要 started_at ——
        is_due 判"running 是否僵死"必须看开始时间。
        """
        try:
            row = (
                self.session.query(InProcessJobRun.status, InProcessJobRun.started_at)
                .filter(InProcessJobRun.job_id == job_id)
                .filter(InProcessJobRun.run_date == run_date)
                .first()
            )
            if not row:
                return None
            return {'status': row[0], 'started_at': row[1]}
        except Exception as e:  # noqa: BLE001
            self._safe_rollback()
            logger.warning("读取 inprocess_job_runs(%s/%s) 失败: %s", job_id, run_date, e)
            raise

    # ---------- 写入路径（B4-c4 收口） ----------

    def mark_running(self, job_id: str, run_date: str) -> None:
        """把某任务某日置为 running（UPSERT）。

        与原 SQL 一致：冲突时只刷新 status/started_at 并清空 finished_at/error，
        **不清 result**（历史上 result 只由 mark_done 写）。
        """
        stmt = pg_insert(InProcessJobRun).values(
            job_id=job_id, run_date=run_date, status='running', started_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[InProcessJobRun.job_id, InProcessJobRun.run_date],
            set_={
                'status': 'running',
                'started_at': func.now(),
                'finished_at': None,
                'error': None,
            },
        )
        try:
            self.session.execute(stmt)
            self.session.commit()
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise

    def mark_done(self, job_id: str, run_date: str, status: str,
                  result: Optional[Dict] = None,
                  error: Optional[str] = None) -> None:
        """写入任务终态（status / finished_at=now() / result / error）。

        与原 SQL 一致：
          · finished_at 取**数据库 now()**；
          · error 截断到 1000 字符，空串归一为 NULL；
          · result 先过 json.dumps(..., ensure_ascii=False, default=str) 再存 ——
            保留原实现"不可序列化对象降级为字符串"的兜底（直接交给 JSONB 会在
            datetime 等对象上抛 TypeError，是行为差异而不是等价迁移）。
        """
        payload = None
        if result:
            payload = json.loads(json.dumps(result, ensure_ascii=False, default=str))
        stmt = (
            update(InProcessJobRun)
            .where(InProcessJobRun.job_id == job_id,
                   InProcessJobRun.run_date == run_date)
            .values(status=status, finished_at=func.now(),
                    result=payload, error=((error or '')[:1000] or None))
        )
        try:
            self.session.execute(stmt)
            self.session.commit()
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise

    # ---------- 巡检查询（B4-c4 收口） ----------

    def list_recent_failures(self, job_ids: Iterable[str],
                             days: int = 3) -> List[Dict[str, Any]]:
        """近 N 个自然日内仍 failed 的活跃任务（不含今天——今天的失败仍在冷却期内）。

        与原 SQL 一致：run_date < CURRENT_DATE AND run_date >= CURRENT_DATE - :days，
        按 run_date DESC, job_id 排序；空 job_ids 直接返回 []（原实现在调用方早退）。
        """
        ids = [j for j in job_ids]
        if not ids:
            return []
        try:
            rows = self.session.execute(
                select(InProcessJobRun.job_id, InProcessJobRun.run_date, InProcessJobRun.error)
                .where(InProcessJobRun.status == 'failed')
                .where(InProcessJobRun.run_date < func.current_date())
                .where(InProcessJobRun.run_date >= func.current_date() - days)
                .where(InProcessJobRun.job_id.in_(ids))
                .order_by(InProcessJobRun.run_date.desc(), InProcessJobRun.job_id)
            ).all()
            return [{'job_id': r[0], 'run_date': str(r[1]), 'error': (r[2] or '')[:200]}
                    for r in rows]
        except Exception as e:  # noqa: BLE001
            self._safe_rollback()
            logger.warning("巡检 inprocess_job_runs 失败记录出错: %s", e)
            raise

    def get_recent_failed(self, job_id: str, days: int = 3) -> Optional[Dict[str, Any]]:
        """近 N 天内最近一条 failed 记录（跨日补跑判定用）。"""
        try:
            row = self.session.execute(
                select(InProcessJobRun.run_date, InProcessJobRun.started_at, InProcessJobRun.error)
                .where(InProcessJobRun.job_id == job_id)
                .where(InProcessJobRun.status == 'failed')
                .where(InProcessJobRun.run_date < func.current_date())
                .where(InProcessJobRun.run_date >= func.current_date() - days)
                .order_by(InProcessJobRun.run_date.desc())
                .limit(1)
            ).first()
            if not row:
                return None
            return {'run_date': str(row[0]), 'started_at': row[1], 'error': row[2]}
        except Exception as e:  # noqa: BLE001
            self._safe_rollback()
            logger.warning("读取最近失败记录(%s)出错: %s", job_id, e)
            raise

    def list_orphan_runs(self, cutoff: _datetime) -> List[Tuple[str, Any]]:
        """早于 cutoff 仍为 running 的行 = 上一进程遗留（判死对象）。"""
        try:
            rows = self.session.execute(
                select(InProcessJobRun.job_id, InProcessJobRun.run_date)
                .where(InProcessJobRun.status == 'running')
                .where(InProcessJobRun.started_at < cutoff)
            ).all()
            return [(r[0], r[1]) for r in rows]
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise

    def mark_orphans_failed(self, cutoff: _datetime) -> int:
        """把早于 cutoff 仍为 running 的行标 failed，返回受影响行数。

        与原 SQL 一致：error = COALESCE(error, '宿主重启导致中断（孤儿 running 行，进程已不在）')，
        finished_at = now()。
        """
        stmt = (
            update(InProcessJobRun)
            .where(InProcessJobRun.status == 'running')
            .where(InProcessJobRun.started_at < cutoff)
            .values(
                status='failed',
                finished_at=func.now(),
                error=func.coalesce(
                    InProcessJobRun.error,
                    '宿主重启导致中断（孤儿 running 行，进程已不在）',
                ),
            )
        )
        try:
            res = self.session.execute(stmt)
            self.session.commit()
            return int(res.rowcount or 0)
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise

    def map_by_date(self, run_date: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """某日的 {job_id: {status, started_at, finished_at, error}}（list_today_runs 用）。"""
        day = run_date or _date.today()
        try:
            rows = self.session.execute(
                select(InProcessJobRun.job_id, InProcessJobRun.status,
                       InProcessJobRun.started_at, InProcessJobRun.finished_at,
                       InProcessJobRun.error)
                .where(InProcessJobRun.run_date == day)
                .order_by(InProcessJobRun.started_at.asc())
            ).all()
            return {r[0]: {'status': r[1], 'started_at': str(r[2]),
                           'finished_at': str(r[3]) if r[3] else None,
                           'error': r[4]} for r in rows}
        except Exception as e:  # noqa: BLE001
            self._safe_rollback()
            logger.warning("列出 inprocess_job_runs(%s) 失败: %s", day, e)
            return {}
