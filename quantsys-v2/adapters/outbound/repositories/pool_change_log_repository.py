"""
Pool Change Log ORM Repository - 股票池变更日志仓储

2026-07-19 新建：DecisionService.record_pool_change 依赖此仓储，
原代码中从未存在（导致 decision_tracking 模块被禁用）。
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class PoolChangeLog(Base):
    __tablename__ = 'pool_change_log'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    pool_id = Column(Integer)
    changed_at = Column(DateTime, default=datetime.now)
    action = Column(String(20), nullable=False)
    symbol = Column(String(20))
    reason = Column(Text)
    triggered_by = Column(String(50))
    agent_decision_id = Column(String(50))
    context = Column(JSON)
    before_state = Column(JSON)
    after_state = Column(JSON)


class PoolChangeLogRepository(BaseORMRepository[PoolChangeLog]):
    """ORM Repository for pool_change_log"""
    model = PoolChangeLog

    def log_change(self, change_data: Dict[str, Any]) -> Dict[str, Any]:
        """记录池子变更，返回完整记录"""
        try:
            row = self.model(
                pool_id=change_data.get('pool_id'),
                action=change_data.get('action', 'unknown'),
                symbol=change_data.get('symbol'),
                reason=change_data.get('reason'),
                triggered_by=change_data.get('triggered_by', 'agent'),
                agent_decision_id=change_data.get('agent_decision_id'),
                context=change_data.get('context'),
                before_state=change_data.get('before_state'),
                after_state=change_data.get('after_state'),
            )
            created = self.create(row)
            if created is None:
                raise RuntimeError("创建池子变更日志失败")
            return self._to_dict(created)
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error logging pool change: {e}")
            raise

    def get_pool_history(self, pool_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """查询指定池子的变更历史（按时间倒序）"""
        try:
            rows = (self.session.query(self.model)
                    .filter_by(pool_id=pool_id)
                    .order_by(self.model.changed_at.desc())
                    .limit(limit).all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error getting pool history for {pool_id}: {e}")
            return []

    def get_recent_changes(self, limit: int = 20) -> List[Dict[str, Any]]:
        """查询最近的变更（按时间倒序）"""
        try:
            rows = (self.session.query(self.model)
                    .order_by(self.model.changed_at.desc())
                    .limit(limit).all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error getting recent pool changes: {e}")
            return []

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing: {e}")
            return []

    @staticmethod
    def _to_dict(r: PoolChangeLog) -> Dict[str, Any]:
        return {
            'id': r.id,
            'pool_id': r.pool_id,
            'changed_at': r.changed_at.isoformat(sep=' ') if r.changed_at else None,
            'action': r.action,
            'symbol': r.symbol,
            'reason': r.reason,
            'triggered_by': r.triggered_by,
            'agent_decision_id': r.agent_decision_id,
            'context': r.context,
            'before_state': r.before_state,
            'after_state': r.after_state,
        }


__all__ = ['PoolChangeLogRepository', 'PoolChangeLog']
