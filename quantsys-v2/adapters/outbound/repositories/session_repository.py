"""Agent 会话仓储（quant.agent_sessions / quant.agent_session_events）。

2026-09-14（w-32314d00，REQ-24e15d B3）：此前这两张表的全部读写都在
application/services/session_service.py 里以 db_cursor + 裸 SQL 实现（13 处，
其中一处还是 f-string 拼列名做计数器自增）。本仓储把数据访问收口，
服务层只保留编排、统计口径与文案生成。

事务语义（刻意保留原样）：ingest 走**单事务** —— 整批成功才提交，
中途抛错整体回滚（调用方用 repo.commit()/repo.rollback() 收口）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Numeric, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import AgentSession, AgentSessionEvent
from infrastructure.persistence.orm.models.agent_session import SESSION_COUNTER_COLUMNS

logger = logging.getLogger(__name__)

__all__ = ['AgentSessionRepository', 'SESSION_COUNTER_COLUMNS']


class AgentSessionRepository(BaseORMRepository[AgentSession]):
    """会话与事件的读写。"""

    model = AgentSession

    # ---------------- 摄入 ----------------

    def upsert_session(
        self,
        session_key: str,
        channel: str,
        peer_id: str,
        agent_id: str,
        last_active_at,
    ) -> None:
        """确保会话行存在；已存在时只把 last_active_at 取**较大值**。

        等价于原 SQL 的
        ON CONFLICT (session_key) DO UPDATE SET last_active_at = GREATEST(...)
        —— 乱序投递不会让 last_active_at 倒退。
        """
        stmt = pg_insert(AgentSession).values(
            session_key=session_key,
            channel=channel,
            peer_id=peer_id,
            agent_id=agent_id,
            last_active_at=last_active_at,
            # started_at / status 是 NOT NULL 且无默认值：首次插入必须给值。
            # 原 SQL 没写这两列 —— 依赖的是建表时的 DEFAULT（bootstrap 里定义的），
            # 这里显式带上更稳妥，且不影响"已存在时不覆盖"（DO UPDATE 只改 last_active_at）。
            started_at=last_active_at,
            status='active',
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['session_key'],
            set_={
                'last_active_at': func.greatest(
                    AgentSession.last_active_at, stmt.excluded.last_active_at
                ),
            },
        )
        self.session.execute(stmt)

    def insert_event(
        self,
        session_key: str,
        seq: int,
        event_type: str,
        payload: Dict[str, Any],
        created_at,
    ) -> bool:
        """插入事件；**重复 (session_key, seq) 返回 False**（幂等，不抛错）。

        等价于原 SQL 的 ON CONFLICT (session_key, seq) DO NOTHING RETURNING id，
        返回是否有行被真正写入。
        """
        stmt = pg_insert(AgentSessionEvent).values(
            session_key=session_key,
            seq=seq,
            event_type=event_type,
            payload=payload,
            created_at=created_at,
        ).on_conflict_do_nothing(index_elements=['session_key', 'seq']).returning(
            AgentSessionEvent.id)
        return self.session.execute(stmt).fetchone() is not None

    def increment_counter(self, session_key: str, column: str) -> None:
        """会话计数器自增（列名走白名单）。

        Raises:
            ValueError: 列名不在 SESSION_COUNTER_COLUMNS 内
        """
        if column not in SESSION_COUNTER_COLUMNS:
            raise ValueError(
                f'会话计数器列名不在白名单: {column!r}（允许：{sorted(SESSION_COUNTER_COLUMNS)}）')
        attr = getattr(AgentSession, column)
        # 用列对象 + 表达式自增（不拼 SQL 文本）
        self.session.query(AgentSession).filter(
            AgentSession.session_key == session_key
        ).update({attr: attr + 1}, synchronize_session=False)

    # ---------------- 查询 ----------------

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        # 用 row._mapping 而不是 dict(row)：SQLAlchemy 2.x 的多列 Row 不是
        # "键值对序列"，直接 dict(row) 会报
        # "cannot convert dictionary update sequence element #0 to a sequence"（实测踩到）。
        d = dict(row._mapping)
        for k, v in list(d.items()):
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        return d

    def list_sessions(self, channel: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            q = self.session.query(AgentSession)
            if channel:
                q = q.filter(AgentSession.channel == channel)
            rows = q.order_by(AgentSession.last_active_at.desc()).limit(limit).all()
            return [self._orm_to_dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing sessions: {e}")
            return []

    @staticmethod
    def _orm_to_dict(obj) -> Dict[str, Any]:
        d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        for k, v in list(d.items()):
            if hasattr(v, 'isoformat'):
                d[k] = v.isoformat()
        return d

    def get_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        try:
            obj = (
                self.session.query(AgentSession)
                .filter(AgentSession.session_key == session_key)
                .first()
            )
            return self._orm_to_dict(obj) if obj else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting session {session_key}: {e}")
            return None

    def list_events(
        self,
        session_key: str,
        event_type: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        try:
            q = self.session.query(
                AgentSessionEvent.seq,
                AgentSessionEvent.event_type,
                AgentSessionEvent.payload,
                AgentSessionEvent.created_at,
            ).filter(AgentSessionEvent.session_key == session_key)
            if event_type:
                q = q.filter(AgentSessionEvent.event_type == event_type)
            rows = q.order_by(AgentSessionEvent.seq.asc()).limit(limit).offset(offset).all()
            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing events for {session_key}: {e}")
            return []

    def get_tool_call_stats(self, session_key: str) -> Dict[str, Any]:
        """工具调用聚合：成功数 / 总数 / 平均耗时 / 最大耗时。

        等价于原 SQL（COUNT(*) FILTER (WHERE payload->>'success')::boolean 等）。
        """
        try:
            row = (
                self.session.query(
                    func.count().filter(
                        AgentSessionEvent.payload['success'].astext.cast(Boolean)
                    ).label('ok'),
                    func.count().label('total'),
                    func.coalesce(func.avg(
                        AgentSessionEvent.payload['durationMs'].astext.cast(Numeric)
                    ), 0).label('avg_ms'),
                    func.coalesce(func.max(
                        AgentSessionEvent.payload['durationMs'].astext.cast(Numeric)
                    ), 0).label('max_ms'),
                )
                .filter(AgentSessionEvent.session_key == session_key)
                .filter(AgentSessionEvent.event_type == 'tool_call')
                .one()
            )
            return {
                'ok': int(row.ok or 0),
                'total': int(row.total or 0),
                'avg_ms': float(row.avg_ms or 0),
                'max_ms': float(row.max_ms or 0),
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting tool call stats for {session_key}: {e}")
            return {'ok': 0, 'total': 0, 'avg_ms': 0.0, 'max_ms': 0.0}

    def get_top_errors(self, session_key: str, limit: int = 5) -> List[Dict[str, Any]]:
        """最高频错误（payload->>'message' 分组计数）。"""
        try:
            msg = AgentSessionEvent.payload['message'].astext
            rows = (
                self.session.query(msg.label('message'), func.count().label('cnt'))
                .filter(AgentSessionEvent.session_key == session_key)
                .filter(AgentSessionEvent.event_type == 'error')
                .group_by(msg)
                .order_by(func.count().desc())
                .limit(limit)
                .all()
            )
            return [{'message': r.message, 'cnt': int(r.cnt)} for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting top errors for {session_key}: {e}")
            return []

    def list_decisions(self, session_key: str, limit: int = 20) -> List[Dict[str, Any]]:
        """该会话关联的决策（agent_decisions.session_key，按 created_at 倒序）。

        复用既有 AgentDecision 模型（agent_intelligence_repository）而不是另写 SQL：
        同一张表在同一进程里有两个模型定义，迟早会漂移。
        """
        try:
            from adapters.outbound.repositories.agent_intelligence_repository import AgentDecision

            rows = (
                self.session.query(
                    AgentDecision.decision_id,
                    AgentDecision.decision_type,
                    AgentDecision.reasoning,
                    AgentDecision.evaluation_status,
                    AgentDecision.success,
                )
                .filter(AgentDecision.session_key == session_key)
                .order_by(AgentDecision.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.warning(f"查询关联决策失败（不影响诊断）: {e}")
            return []

    def get_ai_diagnosis(self, session_key: str):
        """取缓存的 AI 诊断；返回 (analysis, generated_at) 或 None。"""
        try:
            row = (
                self.session.query(AgentSession.ai_diagnosis, AgentSession.ai_diagnosis_at)
                .filter(AgentSession.session_key == session_key)
                .first()
            )
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error reading ai_diagnosis for {session_key}: {e}")
            return None
        if not row or not row[0]:
            return None
        return row[0].get('analysis', ''), row[1]

    def save_ai_diagnosis(self, session_key: str, analysis: str, generated_at) -> None:
        """写入 AI 诊断缓存（ai_diagnosis jsonb + ai_diagnosis_at）。"""
        self.session.query(AgentSession).filter(
            AgentSession.session_key == session_key
        ).update(
            {'ai_diagnosis': {'analysis': analysis}, 'ai_diagnosis_at': generated_at},
            synchronize_session=False,
        )
