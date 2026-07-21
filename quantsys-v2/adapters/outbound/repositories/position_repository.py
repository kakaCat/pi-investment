"""
Position ORM Repository - 持仓仓储

修复记录：2026-07-19 重建
  - 原 stub 未实现抽象方法 get_positions，无法实例化
  - 实际表 quant.positions（uuid 主键，account_id 区分组合）
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import IPositionRepository
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class Position(Base):
    __tablename__ = 'positions'
    __table_args__ = {'schema': 'quant'}

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    account_id = Column(Text, nullable=False, default='default')
    symbol = Column(Text, nullable=False)
    quantity = Column(Integer, nullable=False)
    cost_basis = Column(Float, nullable=False)
    current_price = Column(Float)
    market_value = Column(Float)
    unrealized_pnl = Column(Float)
    unrealized_pnl_pct = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    entry_date = Column(Date, nullable=False)
    entry_reason = Column(Text)
    entry_log_id = Column(PG_UUID(as_uuid=True))
    status = Column(Text, nullable=False, default='open')
    updated_at = Column(DateTime(timezone=True))
    name = Column(Text)
    market = Column(Text)
    sector = Column(Text)


class PositionORMRepository(BaseORMRepository[Position], IPositionRepository):
    """ORM Repository for positions"""
    model = Position

    # ---------- 接口方法 ----------

    def get_positions(self, portfolio_name: str = 'default',
                      trade_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取指定账户的持仓列表（默认当前持仓 status='open'）"""
        try:
            rows = (self.session.query(self.model)
                    .filter(self.model.account_id == portfolio_name,
                            self.model.status == 'open')
                    .all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            logger.error(f"Error getting positions for {portfolio_name}: {e}")
            return []

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []

    @staticmethod
    def _to_dict(r: Position) -> Dict[str, Any]:
        return {
            'id': str(r.id),
            'account_id': r.account_id,
            'symbol': r.symbol,
            'name': r.name,
            'quantity': r.quantity,
            'cost_basis': r.cost_basis,
            'current_price': r.current_price,
            'market_value': r.market_value,
            'unrealized_pnl': r.unrealized_pnl,
            'unrealized_pnl_pct': r.unrealized_pnl_pct,
            'stop_loss': r.stop_loss,
            'take_profit': r.take_profit,
            'entry_date': r.entry_date.isoformat() if r.entry_date else None,
            'entry_reason': r.entry_reason,
            'status': r.status,
            'market': r.market,
            'sector': r.sector,
            'updated_at': r.updated_at.isoformat(sep=' ') if r.updated_at else None,
        }


__all__ = ['PositionORMRepository', 'Position']
