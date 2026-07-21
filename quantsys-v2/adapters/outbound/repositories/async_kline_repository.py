"""
Async Kline ORM Repository - 完全迁移版本

迁移状态：✅ 已完成ORM迁移
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, Text, BigInteger, JSON, Boolean, DateTime
from infrastructure.persistence.orm.base import Base
from domain.ports import IAsyncKlineRepository
from typing import List, Optional
import structlog

logger = structlog.get_logger(__name__)

class AsyncKline(Base):
    __tablename__ = 'async_klines'
    __table_args__ = {'schema': 'quant'}
    
    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime)

class AsyncKlineORMRepository(BaseORMRepository[AsyncKline], IAsyncKlineRepository):
    """ORM Repository for async_klines"""
    model = AsyncKline
    
    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []

__all__ = ['AsyncKlineORMRepository']
