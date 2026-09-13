"""Agent 操作日志仓储（quant.agent_logs）。

背景（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
    原先 /api/agent/logs 路由自己 `db_cursor()` + f-string 拼 WHERE 子句查两张表
    （计数 + 明细）。按计划 §3.1「SQL 只允许出现在 adapters/outbound/repositories/」，
    查询收口到本仓储，路由只做展示映射。

行为契约（与原内联 SQL 逐值一致，迁移时已在真实库上做过等价性比对）：
    · 日期区间是 **date 语义**：start >= CAST(:start AS DATE)、
      end < CAST(:end AS DATE) + interval '1 day'（不是按时刻）；
    · 三个筛选项均可选，缺省即不加条件（原实现是 where TRUE）；
    · 明细按 timestamp DESC 排序，LIMIT/OFFSET 由调用方给；
    · 返回的是**原始列值**（UUID / datetime / dict），不是字符串 ——
      展示层（isoformat、str()）留在路由里，避免仓储越界做格式化。
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, cast, func, literal_column, select
from sqlalchemy.exc import SQLAlchemyError

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import AgentLog

import structlog

logger = structlog.get_logger(__name__)

__all__ = ['AgentLogRepository']


def _filters(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    action_type: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Any]:
    """把可选筛选条件翻成 SQLAlchemy 表达式列表（与原 f-string 拼出来的条件一一对应）。"""
    conds: List[Any] = []
    if start_date:
        conds.append(AgentLog.timestamp >= cast(start_date, Date))
    if end_date:
        # 对齐原写法 "timestamp < (%s::date + interval '1 day')"
        conds.append(AgentLog.timestamp < cast(end_date, Date) + literal_column("interval '1 day'"))
    if action_type:
        conds.append(AgentLog.action_type == action_type)
    if status:
        conds.append(AgentLog.status == status)
    return conds


class AgentLogRepository(BaseORMRepository[AgentLog]):
    """Agent 操作日志仓储"""

    model = AgentLog

    def count_logs(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """按筛选条件统计日志条数。

        Raises:
            SQLAlchemyError: 原路由没有吞异常（交给 handle_api_error → 500），
                此处保持一致——回滚后原样上抛，不静默返回 0。
        """
        try:
            stmt = select(func.count()).select_from(AgentLog)
            conds = _filters(start_date, end_date, action_type, status)
            if conds:
                stmt = stmt.where(*conds)
            return int(self.session.execute(stmt).scalar() or 0)
        except SQLAlchemyError:
            self._safe_rollback()
            raise

    def list_logs(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """按筛选条件取明细（timestamp DESC），返回原始列值的 dict 列表。

        Raises:
            SQLAlchemyError: 同 count_logs，不静默降级为空列表。
        """
        try:
            stmt = (select(
                AgentLog.id,
                AgentLog.timestamp,
                AgentLog.action_type,
                AgentLog.symbol,
                AgentLog.details,
                AgentLog.result,
                AgentLog.status,
                AgentLog.duration_ms,
                AgentLog.created_at,
            )
                .select_from(AgentLog)
                .order_by(AgentLog.timestamp.desc())
                .limit(limit)
                .offset(offset))
            conds = _filters(start_date, end_date, action_type, status)
            if conds:
                stmt = stmt.where(*conds)
            rows = self.session.execute(stmt).mappings().all()
            return [dict(r) for r in rows]
        except SQLAlchemyError:
            self._safe_rollback()
            raise
