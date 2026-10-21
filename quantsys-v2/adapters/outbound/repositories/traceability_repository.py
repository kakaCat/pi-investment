"""
Traceability ORM Repository - 操作可追溯仓储

修复记录：2026-07-19 重建
  - 原 stub 表名错误（traceabilities）且未实现抽象方法 log_operation
  - 实际表 quant.operation_audit（见迁移 add_operation_audit_table.sql）
"""
from qs_kernel.infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Text
from sqlalchemy.exc import SQLAlchemyError
from qs_kernel.infrastructure.persistence.orm.base import Base
from qs_kernel.domain.ports import ITraceabilityRepository
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
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


class MLPrediction(Base):
    """quant.ml_predictions — ML 预测留痕（/api/ml/predict 每次调用的可追溯记录）

    2026-10-19 补建：_save_ml_predictions 调用的 save_ml_prediction 此前在全仓
    零定义，AttributeError 被 best-effort except 吞掉，导致该表自建表以来一直 0 行。
    """

    __tablename__ = 'ml_predictions'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    execution_id = Column(String(64))
    symbol = Column(String(20), nullable=False)
    prediction_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    model_type = Column(String(50))
    model_version = Column(String(50))
    feature_count = Column(Integer)
    prediction = Column(Integer)
    confidence = Column(String(20))
    prob_down = Column(Float)
    prob_up = Column(Float)


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
            self._safe_rollback()
            logger.error(f"Error logging operation: {e}")
            return -1

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing: {e}")
            return []

    def save_ml_prediction(self, record: Dict[str, Any]) -> int:
        """记录一条 ML 预测留痕到 quant.ml_predictions，返回记录ID（失败返回 -1）

        2026-10-19 补：此前本方法不存在，_save_ml_predictions 的 AttributeError
        被 best-effort except 吞掉，ml_predictions 表因此一直 0 行。
        """
        try:
            prediction_time = record.get('prediction_time')
            if isinstance(prediction_time, str):
                try:
                    prediction_time = datetime.fromisoformat(
                        prediction_time.replace('Z', '+00:00'))
                except ValueError:
                    prediction_time = None
            row = MLPrediction(
                execution_id=record.get('execution_id'),
                symbol=record.get('symbol', ''),
                prediction_time=prediction_time or datetime.now(timezone.utc),
                model_type=record.get('model_type'),
                model_version=record.get('model_version'),
                feature_count=record.get('feature_count', 0),
                prediction=record.get('prediction'),
                confidence=record.get('confidence'),
                prob_down=record.get('prob_down'),
                prob_up=record.get('prob_up'),
            )
            self.session.add(row)
            self.session.commit()
            return row.id
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error saving ml_prediction: {e}")
            return -1


__all__ = ['TraceabilityORMRepository', 'OperationAudit', 'MLPrediction']
