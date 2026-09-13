"""进程内任务台账仓储（quant.inprocess_job_runs）。

2026-09-14（w-32314d00，REQ-24e15d B2）：该表此前无模型无仓储，读写散在
daily_jobs_bootstrap.py（建表/INSERT/UPDATE/多处分页 SELECT）与
financial_timeliness_check_job.py（当天去重）里。本仓储先收口**只读**查询
（作业层真正需要的部分）；写入路径（bootstrap）单独评估，避免与它的幂等语义打架。
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import List, Optional

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
