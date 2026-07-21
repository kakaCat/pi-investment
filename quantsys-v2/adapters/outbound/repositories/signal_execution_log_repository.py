"""
Signal Execution Log ORM Repository - 完全迁移版本

迁移状态：✅ 已完成ORM迁移
修复记录：2026-07-19 补全 ORM 模型字段与业务方法
  - 原 stub 未实现抽象方法 log_execution，导致类无法实例化（API 500）
  - 补齐 create_execution_log / update_execution_log / get_logs_by_date_range
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Date
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import ISignalExecutionLogRepository
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import structlog

logger = structlog.get_logger(__name__)


class SignalExecutionLog(Base):
    __tablename__ = 'signal_execution_logs'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    execution_date = Column(Date, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration_ms = Column(Integer)
    strategies_run = Column(Integer, default=0)
    signals_generated = Column(Integer, default=0)
    signals_approved = Column(Integer, default=0)
    signals_rejected = Column(Integer, default=0)
    orders_created = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    execution_details = Column(JSON)
    status = Column(String(20), default='running')
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class SignalExecutionLogORMRepository(BaseORMRepository[SignalExecutionLog], ISignalExecutionLogRepository):
    """ORM Repository for signal_execution_logs"""
    model = SignalExecutionLog

    # 允许通过 update_execution_log 更新的字段
    _UPDATABLE_FIELDS = {
        'execution_date', 'start_time', 'end_time', 'duration_ms',
        'strategies_run', 'signals_generated', 'signals_approved',
        'signals_rejected', 'orders_created', 'errors_count',
        'execution_details', 'status', 'error_message',
    }

    # ---------- 接口方法 ----------

    def log_execution(self, execution: Dict[str, Any]) -> int:
        """接口方法（ISignalExecutionLogRepository）：记录执行日志，返回日志ID"""
        return self.create_execution_log(execution)

    # ---------- 业务方法 ----------

    def create_execution_log(self, data: Dict[str, Any]) -> int:
        """创建执行日志，返回日志ID（失败返回 -1）"""
        try:
            log = self.model(
                execution_date=self._parse_date(data.get('execution_date')) or date.today(),
                start_time=self._parse_datetime(data.get('start_time')) or datetime.now(),
                end_time=self._parse_datetime(data.get('end_time')),
                duration_ms=data.get('duration_ms'),
                strategies_run=data.get('strategies_run', 0),
                signals_generated=data.get('signals_generated', 0),
                signals_approved=data.get('signals_approved', 0),
                signals_rejected=data.get('signals_rejected', 0),
                orders_created=data.get('orders_created', 0),
                errors_count=data.get('errors_count', 0),
                execution_details=data.get('execution_details'),
                status=data.get('status', 'running'),
                error_message=data.get('error_message'),
            )
            created = self.create(log)
            if created is None:
                return -1
            return created.id
        except Exception as e:
            logger.error(f"Error creating execution log: {e}")
            return -1

    def update_execution_log(self, log_id: int, data: Dict[str, Any]) -> bool:
        """更新执行日志，成功返回 True"""
        try:
            log = self.session.query(self.model).get(log_id)
            if log is None:
                logger.warning(f"Execution log not found: {log_id}")
                return False

            for key, value in data.items():
                if key not in self._UPDATABLE_FIELDS:
                    continue
                if key == 'execution_date':
                    value = self._parse_date(value)
                elif key in ('start_time', 'end_time'):
                    value = self._parse_datetime(value)
                setattr(log, key, value)

            self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error updating execution log {log_id}: {e}")
            self.session.rollback()
            return False

    def get_log(self, log_id: int) -> Optional[Dict[str, Any]]:
        """按ID查询单条日志"""
        try:
            log = self.session.query(self.model).get(log_id)
            return self._to_dict(log) if log else None
        except SQLAlchemyError as e:
            logger.error(f"Error getting execution log {log_id}: {e}")
            return None

    def get_logs_by_date_range(self, start_date: Any, end_date: Any) -> List[Dict[str, Any]]:
        """按日期范围查询执行日志（按日期倒序），返回字典列表"""
        try:
            start = self._parse_date(start_date)
            end = self._parse_date(end_date)
            query = self.session.query(self.model)
            if start:
                query = query.filter(self.model.execution_date >= start)
            if end:
                query = query.filter(self.model.execution_date <= end)
            rows = query.order_by(self.model.execution_date.desc(),
                                  self.model.id.desc()).all()
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            logger.error(f"Error querying execution logs: {e}")
            return []

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []

    # ---------- 工具方法 ----------

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None or isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return datetime.strptime(value.strip()[:10], '%Y-%m-%d').date()
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            value = value.strip()
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
                try:
                    return datetime.strptime(value[:19], fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _to_dict(log: SignalExecutionLog) -> Dict[str, Any]:
        return {
            'id': log.id,
            'execution_date': log.execution_date.isoformat() if log.execution_date else None,
            'start_time': log.start_time.isoformat(sep=' ') if log.start_time else None,
            'end_time': log.end_time.isoformat(sep=' ') if log.end_time else None,
            'duration_ms': log.duration_ms,
            'strategies_run': log.strategies_run or 0,
            'signals_generated': log.signals_generated or 0,
            'signals_approved': log.signals_approved or 0,
            'signals_rejected': log.signals_rejected or 0,
            'orders_created': log.orders_created or 0,
            'errors_count': log.errors_count or 0,
            'execution_details': log.execution_details,
            'status': log.status,
            'error_message': log.error_message,
            'created_at': log.created_at.isoformat(sep=' ') if log.created_at else None,
        }


# 兼容旧命名（tests 等仍引用 SignalExecutionLogRepository）
SignalExecutionLogRepository = SignalExecutionLogORMRepository

__all__ = ['SignalExecutionLogORMRepository', 'SignalExecutionLogRepository']
