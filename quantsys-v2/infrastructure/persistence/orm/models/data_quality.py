"""K 线数据质量审计表（public.kline_data_quality）。

建立背景（2026-09-14，w-32314d00，REQ-24e15d t4/B2）：
    这张表此前**没有 ORM 模型**——建表 DDL 写在
    `adapters/outbound/repositories/models/kline_data_quality.py` 的字符串常量里，
    写入在 `application/services/data_quality_service.py`（手写 INSERT），
    读取在 `infrastructure/jobs/data_quality_check_job.py`（text() 查当天 D 级数量）。

⚠️ schema 是 **public** 而不是 quant（实测 information_schema：表在 public），
   这一点必须显式声明，否则 SQLAlchemy 会去 quant.* 找表并报 UndefinedTable。
"""
from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..base import Base

__all__ = ['KlineDataQuality']


class KlineDataQuality(Base):
    """K 线质量检查结果（每次检查一行）

    对应数据库表：public.kline_data_quality
    """
    __tablename__ = 'kline_data_quality'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    period = Column(String(20), nullable=False)
    start_date = Column(String(10), nullable=True)
    end_date = Column(String(10), nullable=True)
    limit_count = Column(Integer, nullable=True)

    original_count = Column(Integer, nullable=False)
    cleaned_count = Column(Integer, nullable=False)
    removed_count = Column(Integer, default=0)
    fixed_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)

    errors_json = Column(JSONB, nullable=True)
    warnings_json = Column(JSONB, nullable=True)
    cleaning_operations_json = Column(JSONB, nullable=True)

    completeness_score = Column(Float, nullable=False)
    consistency_score = Column(Float, nullable=False)
    accuracy_score = Column(Float, nullable=False)
    overall_score = Column(Float, nullable=False)

    grade = Column(String(10), nullable=False)
    duration_ms = Column(Integer, nullable=True)
    # 注意：真实列是 timestamp **without** time zone（其余表多是 with time zone）
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    def __repr__(self):
        return f"<KlineDataQuality(symbol='{self.symbol}', grade='{self.grade}', score={self.overall_score})>"
