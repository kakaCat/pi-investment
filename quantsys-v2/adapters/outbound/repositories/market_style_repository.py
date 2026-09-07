"""
Market Style ORM Repository - 市场风格仓储

修复记录：2026-07-19 重建
  - 原 stub 未实现抽象方法 get_market_style，无法实例化
  - 实际表 quant.market_style_state
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import IMarketStyleRepository
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import structlog

logger = structlog.get_logger(__name__)


class MarketStyleState(Base):
    __tablename__ = 'market_style_state'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    trade_date = Column(Date, nullable=False, unique=True)
    style = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    metrics = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)


class MarketStyleORMRepository(BaseORMRepository[MarketStyleState], IMarketStyleRepository):
    """ORM Repository for market_style_state"""
    model = MarketStyleState

    # ---------- 接口方法 ----------

    def get_market_style(self, trade_date: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """获取指定日期的市场风格（默认最新一条）"""
        try:
            query = self.session.query(self.model)
            if trade_date:
                parsed = self._parse_date(trade_date)
                if parsed:
                    row = query.filter_by(trade_date=parsed).first()
                    return self._to_dict(row) if row else None
            row = query.order_by(self.model.trade_date.desc()).first()
            return self._to_dict(row) if row else None
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error getting market style: {e}")
            return None

    # ---------- 业务方法 ----------

    def save_market_style(self, trade_date: Any, style: str, confidence: float,
                          metrics: Optional[Dict] = None) -> bool:
        """保存市场风格记录（按 trade_date upsert）"""
        try:
            parsed = self._parse_date(trade_date)
            if not parsed:
                return False
            row = self.session.query(self.model).filter_by(trade_date=parsed).first()
            if row is None:
                row = self.model(trade_date=parsed)
                self.session.add(row)
            row.style = style
            row.confidence = confidence
            row.metrics = metrics
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error saving market style: {e}")
            self.session.rollback()
            return False

    def get_style_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        """获取市场风格历史（按日期倒序）"""
        try:
            rows = (self.session.query(self.model)
                    .order_by(self.model.trade_date.desc())
                    .limit(limit).all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error listing market style history: {e}")
            return []

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing: {e}")
            return []

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
    def _to_dict(r: MarketStyleState) -> Dict[str, Any]:
        return {
            'id': r.id,
            'trade_date': r.trade_date.isoformat() if r.trade_date else None,
            'style': r.style,
            'confidence': r.confidence,
            'metrics': r.metrics,
            'created_at': r.created_at.isoformat(sep=' ') if r.created_at else None,
        }


__all__ = ['MarketStyleORMRepository', 'MarketStyleState']
