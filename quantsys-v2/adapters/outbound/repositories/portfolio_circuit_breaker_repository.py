"""组合熔断状态仓储（quant.portfolio_circuit_breaker）。

2026-09-14（w-32314d00，REQ-24e15d B4-b）：原先读写内联在
application/services/portfolio_breaker_service.py（db_cursor + 一段带 CASE/COALESCE 的 UPSERT）。
本仓储**逐表达式照搬**原 SQL 的 upsert 语义（见 upsert_status 注释），不重新发明。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func, null
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import PortfolioCircuitBreaker

logger = logging.getLogger(__name__)

__all__ = ['PortfolioCircuitBreakerRepository']

_FIELDS = ('account_name', 'active', 'triggered_at', 'triggered_drawdown',
           'actions_taken', 'unblock_condition', 'note', 'updated_at')


class PortfolioCircuitBreakerRepository(BaseORMRepository[PortfolioCircuitBreaker]):
    """熔断状态读写。"""

    model = PortfolioCircuitBreaker

    def get_status(self, account_name: str) -> Optional[Dict[str, Any]]:
        """读某账户的熔断状态；无记录返回 None。

        日期转 ISO 字符串、triggered_drawdown 转 float —— 与调用方原有输出形状一致
        （numeric 列不转 float 会让 JSON 序列化炸）。
        """
        try:
            row = (
                self.session.query(PortfolioCircuitBreaker)
                .filter(PortfolioCircuitBreaker.account_name == account_name)
                .first()
            )
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error reading circuit breaker status: {e}")
            raise
        if not row:
            return None
        out = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        for k in ('triggered_at', 'updated_at'):
            if out.get(k) is not None:
                out[k] = out[k].isoformat()
        if out.get('triggered_drawdown') is not None:
            out['triggered_drawdown'] = float(out['triggered_drawdown'])
        return out

    def upsert_status(
        self,
        account_name: str,
        active: bool,
        triggered_drawdown: Optional[float] = None,
        actions_taken: Optional[List] = None,
        unblock_condition: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """写入/更新熔断状态。**逐表达式照搬原 SQL**：

        · triggered_at：INSERT 时 = CASE WHEN active THEN NOW() ELSE NULL；
          CONFLICT 时 = CASE WHEN EXCLUDED.active THEN NOW() ELSE 旧值 END
          （即"解除熔断不抹掉上次触发时间"）
        · triggered_drawdown / actions_taken / unblock_condition：COALESCE(新, 旧)
          （即"传 None 不清空既有值"）
        · note：**无条件覆盖**（包括用 NULL 覆盖）
        · updated_at 恒为 NOW()
        """
        stmt = pg_insert(PortfolioCircuitBreaker).values(
            account_name=account_name,
            active=active,
            triggered_at=func.now() if active else None,
            triggered_drawdown=triggered_drawdown,
            # ⚠️ 关键：JSONB 列上直接传 Python None，SQLAlchemy 会渲染成 **JSON null**
            # （字面量 'null'::jsonb）而不是 SQL NULL —— 于是
            # COALESCE(EXCLUDED.actions_taken, 旧值) = 'null'::jsonb，
            # "解除熔断不清空减仓记录"的语义被静默破坏（实测：actions_taken 被清成 None）。
            # 用 sqlalchemy.null() 显式表达 SQL NULL。**实测对照**：同一段逻辑用原生 SQL
            # 传 NULL 时旧值被正确保留（['a'] 未丢），证明确实是 ORM 层的渲染差异。
            actions_taken=null() if actions_taken is None else actions_taken,
            unblock_condition=unblock_condition,
            note=note,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['account_name'],
            set_={
                'active': stmt.excluded.active,
                'triggered_at': case(
                    (stmt.excluded.active.is_(True), func.now()),
                    else_=PortfolioCircuitBreaker.triggered_at,
                ),
                'triggered_drawdown': func.coalesce(
                    stmt.excluded.triggered_drawdown, PortfolioCircuitBreaker.triggered_drawdown),
                'actions_taken': func.coalesce(
                    stmt.excluded.actions_taken, PortfolioCircuitBreaker.actions_taken),
                'unblock_condition': func.coalesce(
                    stmt.excluded.unblock_condition, PortfolioCircuitBreaker.unblock_condition),
                'note': stmt.excluded.note,
                'updated_at': func.now(),
            },
        )
        self.session.execute(stmt)
        self.session.commit()
