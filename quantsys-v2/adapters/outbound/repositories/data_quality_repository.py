"""
Data Quality ORM Repository - 数据质量仓储

修复记录：2026-07-19 重建
  - 原 stub 表名错误（data_qualities）且未实现抽象方法 log_quality_issue
  - 实际表 quant.data_quality_records（见迁移 add_data_quality_records_table.sql）
  - 补齐 get_quality_records / get_daily_stats / get_quality_summary / save_quality_record
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON, Text, func
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import IDataQualityRepository
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
import structlog

logger = structlog.get_logger(__name__)


class DataQualityRecord(Base):
    __tablename__ = 'data_quality_records'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20))
    period = Column(String(20), default='daily')
    check_date = Column(Date, nullable=False, default=date.today)
    start_date = Column(Date)
    end_date = Column(Date)

    original_count = Column(Integer)
    cleaned_count = Column(Integer)
    removed_count = Column(Integer)
    fixed_count = Column(Integer)
    error_count = Column(Integer)
    warning_count = Column(Integer)

    errors = Column(JSON)
    warnings = Column(JSON)
    cleaning_operations = Column(JSON)

    completeness_score = Column(Float)
    consistency_score = Column(Float)
    accuracy_score = Column(Float)
    overall_score = Column(Float)
    grade = Column(String(20))

    duration_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)


def _compute_grade(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score >= 95:
        return 'A+'
    if score >= 90:
        return 'A'
    if score >= 80:
        return 'B'
    if score >= 70:
        return 'C'
    return 'D'


class DataQualityORMRepository(BaseORMRepository[DataQualityRecord], IDataQualityRepository):
    """ORM Repository for data_quality_records"""
    model = DataQualityRecord

    # ---------- 接口方法 ----------

    def log_quality_issue(self, issue: Dict[str, Any]) -> int:
        """接口方法：记录数据质量问题，返回记录ID"""
        return self.save_quality_record(issue)

    # ---------- 业务方法 ----------

    def save_quality_record(self, data: Dict[str, Any]) -> int:
        """保存质量记录，返回记录ID（失败返回 -1）"""
        try:
            record = self.model(
                symbol=data.get('symbol'),
                period=data.get('period', 'daily'),
                check_date=self._parse_date(data.get('check_date')) or date.today(),
                start_date=self._parse_date(data.get('start_date')),
                end_date=self._parse_date(data.get('end_date')),
                original_count=data.get('original_count'),
                cleaned_count=data.get('cleaned_count'),
                removed_count=data.get('removed_count'),
                fixed_count=data.get('fixed_count'),
                error_count=data.get('error_count'),
                warning_count=data.get('warning_count'),
                errors=data.get('errors'),
                warnings=data.get('warnings'),
                cleaning_operations=data.get('cleaning_operations'),
                completeness_score=data.get('completeness_score'),
                consistency_score=data.get('consistency_score'),
                accuracy_score=data.get('accuracy_score'),
                overall_score=data.get('overall_score'),
                grade=data.get('grade') or _compute_grade(data.get('overall_score')),
                duration_ms=data.get('duration_ms'),
            )
            created = self.create(record)
            return created.id if created else -1
        except Exception as e:
            logger.error(f"Error saving quality record: {e}")
            return -1

    def get_quality_records(self, symbol: Optional[str] = None,
                            start_date: Optional[Any] = None,
                            end_date: Optional[Any] = None,
                            min_score: Optional[float] = None,
                            max_score: Optional[float] = None,
                            grade: Optional[str] = None,
                            limit: int = 100,
                            offset: int = 0) -> List[Dict[str, Any]]:
        """按条件查询质量记录（按检查日期倒序）"""
        try:
            query = self.session.query(self.model)
            if symbol:
                query = query.filter(self.model.symbol == symbol)
            start = self._parse_date(start_date)
            if start:
                query = query.filter(self.model.check_date >= start)
            end = self._parse_date(end_date)
            if end:
                query = query.filter(self.model.check_date <= end)
            if min_score is not None:
                query = query.filter(self.model.overall_score >= min_score)
            if max_score is not None:
                query = query.filter(self.model.overall_score <= max_score)
            if grade:
                query = query.filter(self.model.grade == grade)

            rows = (query.order_by(self.model.check_date.desc(), self.model.id.desc())
                    .offset(offset).limit(limit).all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            logger.error(f"Error querying quality records: {e}")
            return []

    def get_daily_stats(self, symbol: Optional[str] = None,
                        start_date: Optional[Any] = None,
                        end_date: Optional[Any] = None,
                        limit: int = 30) -> List[Dict[str, Any]]:
        """按日聚合质量统计"""
        try:
            query = self.session.query(
                self.model.check_date.label('check_date'),
                func.count(self.model.id).label('total_checks'),
                func.avg(self.model.overall_score).label('avg_score'),
                func.min(self.model.overall_score).label('min_score'),
                func.max(self.model.overall_score).label('max_score'),
                func.sum(self.model.error_count).label('total_errors'),
                func.sum(self.model.warning_count).label('total_warnings'),
            ).group_by(self.model.check_date)

            if symbol:
                query = query.filter(self.model.symbol == symbol)
            start = self._parse_date(start_date)
            if start:
                query = query.filter(self.model.check_date >= start)
            end = self._parse_date(end_date)
            if end:
                query = query.filter(self.model.check_date <= end)

            rows = (query.order_by(self.model.check_date.desc())
                    .limit(limit).all())
            return [{
                'check_date': r.check_date.isoformat() if r.check_date else None,
                'total_checks': r.total_checks,
                'avg_score': round(float(r.avg_score), 2) if r.avg_score is not None else None,
                'min_score': r.min_score,
                'max_score': r.max_score,
                'total_errors': r.total_errors or 0,
                'total_warnings': r.total_warnings or 0,
            } for r in rows]
        except SQLAlchemyError as e:
            logger.error(f"Error querying daily stats: {e}")
            return []

    def get_quality_summary(self, days: int = 7) -> Dict[str, Any]:
        """近N天质量概要"""
        try:
            since = date.today() - timedelta(days=days)
            base = self.session.query(self.model).filter(self.model.check_date >= since)

            total = base.count()
            avg_score = base.with_entities(func.avg(self.model.overall_score)).scalar()
            total_errors = base.with_entities(func.sum(self.model.error_count)).scalar() or 0
            total_warnings = base.with_entities(func.sum(self.model.warning_count)).scalar() or 0

            grade_rows = (base.with_entities(self.model.grade, func.count(self.model.id))
                          .group_by(self.model.grade).all())
            grade_dist = {g: c for g, c in grade_rows if g}

            worst_rows = (base.filter(self.model.overall_score.isnot(None))
                          .order_by(self.model.overall_score.asc())
                          .limit(5).all())

            return {
                'period_days': days,
                'since': since.isoformat(),
                'total_checks': total,
                'avg_score': round(float(avg_score), 2) if avg_score is not None else None,
                'total_errors': total_errors,
                'total_warnings': total_warnings,
                'grade_distribution': grade_dist,
                'worst_records': [self._to_dict(r) for r in worst_rows],
            }
        except SQLAlchemyError as e:
            logger.error(f"Error building quality summary: {e}")
            return {'period_days': days, 'total_checks': 0, 'error': str(e)}

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
            try:
                return datetime.strptime(value.strip()[:10], '%Y-%m-%d').date()
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_dict(r: DataQualityRecord) -> Dict[str, Any]:
        return {
            'id': r.id,
            'symbol': r.symbol,
            'period': r.period,
            'check_date': r.check_date.isoformat() if r.check_date else None,
            'start_date': r.start_date.isoformat() if r.start_date else None,
            'end_date': r.end_date.isoformat() if r.end_date else None,
            'original_count': r.original_count,
            'cleaned_count': r.cleaned_count,
            'removed_count': r.removed_count,
            'fixed_count': r.fixed_count,
            'error_count': r.error_count,
            'warning_count': r.warning_count,
            'errors': r.errors,
            'warnings': r.warnings,
            'cleaning_operations': r.cleaning_operations,
            'completeness_score': r.completeness_score,
            'consistency_score': r.consistency_score,
            'accuracy_score': r.accuracy_score,
            'overall_score': r.overall_score,
            'grade': r.grade,
            'duration_ms': r.duration_ms,
            'created_at': r.created_at.isoformat(sep=' ') if r.created_at else None,
        }


__all__ = ['DataQualityORMRepository', 'DataQualityRecord']
