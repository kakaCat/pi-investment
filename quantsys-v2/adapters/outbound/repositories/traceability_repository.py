"""
Traceability ORM Repository - 操作可追溯仓储

修复记录：2026-07-19 重建
  - 原 stub 表名错误（traceabilities）且未实现抽象方法 log_operation
  - 实际表 quant.operation_audit（见迁移 add_operation_audit_table.sql）
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import ITraceabilityRepository
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class OperationAudit(Base):
    __tablename__ = 'operation_audit'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    operation_type = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(String(100))
    actor = Column(String(100), default='agent')
    detail = Column(JSON)
    result = Column(String(20))
    error_message = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class TraceabilityORMRepository(BaseORMRepository[OperationAudit], ITraceabilityRepository):
    """ORM Repository for operation_audit"""
    model = OperationAudit

    # ---------- 接口方法 ----------

    def log_operation(self, operation: Dict[str, Any]) -> int:
        """记录操作审计日志，返回记录ID（失败返回 -1）"""
        try:
            row = self.model(
                operation_type=operation.get('operation_type', 'unknown'),
                entity_type=operation.get('entity_type'),
                entity_id=str(operation.get('entity_id')) if operation.get('entity_id') is not None else None,
                actor=operation.get('actor', 'agent'),
                detail=operation.get('detail') or operation.get('details'),
                result=operation.get('result'),
                error_message=operation.get('error_message'),
            )
            created = self.create(row)
            return created.id if created else -1
        except Exception as e:
            logger.error(f"Error logging operation: {e}")
            return -1

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []


__all__ = ['TraceabilityORMRepository', 'OperationAudit']
