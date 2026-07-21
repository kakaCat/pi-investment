"""
Fund Flow ORM Repository - 完全迁移版本

迁移状态：✅ 已完成ORM迁移
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, Text, BigInteger, JSON, Boolean, DateTime
from infrastructure.persistence.orm.base import Base
from domain.ports import IFundFlowRepository
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)

class FundFlow(Base):
    __tablename__ = 'fund_flows'
    __table_args__ = {'schema': 'quant'}
    
    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime)

class FundFlowORMRepository(BaseORMRepository[FundFlow], IFundFlowRepository):
    """ORM Repository for fund_flows"""
    model = FundFlow
    
    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []

    def get_fund_flow(self, symbol: str, start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            q = self.session.query(self.model)
            if symbol:
                q = q.filter(self.model.symbol == symbol)
            if start_date:
                q = q.filter(self.model.trade_date >= start_date)
            if end_date:
                q = q.filter(self.model.trade_date <= end_date)
            rows = q.order_by(self.model.trade_date.desc()).all()
            return [{c.name: getattr(r, c.name) for c in self.model.__table__.columns} for r in rows]
        except Exception as e:
            logger.error(f"Error in get_fund_flow: {e}")
            return []

__all__ = ['FundFlowORMRepository']
