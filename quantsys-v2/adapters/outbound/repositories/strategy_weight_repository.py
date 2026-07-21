"""
Strategy Weight ORM Repository - 策略权重仓储

修复记录：2026-07-19 重建
  - 原 stub 表名错误（strategy_weights）且未实现抽象方法 get_weights
  - 实际表 quant.strategy_weight_config（strategy_type + market_style → static_weight）
  - 补齐 get_static_weight / get_weights
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import IStrategyWeightRepository
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class StrategyWeightConfig(Base):
    __tablename__ = 'strategy_weight_config'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    strategy_type = Column(String(50), nullable=False)
    market_style = Column(String(50), nullable=False)
    static_weight = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.now)


class StrategyWeightORMRepository(BaseORMRepository[StrategyWeightConfig], IStrategyWeightRepository):
    """ORM Repository for strategy_weight_config"""
    model = StrategyWeightConfig

    # ---------- 接口方法 ----------

    def get_weights(self, portfolio_name: str,
                    trade_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """接口方法：获取权重配置列表（当前实现返回全部启用配置）"""
        try:
            rows = (self.session.query(self.model)
                    .filter(self.model.is_active.is_(True))
                    .all())
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            logger.error(f"Error getting weights: {e}")
            return []

    # ---------- 业务方法 ----------

    def get_static_weight(self, strategy_type: str, market_style: str) -> Optional[float]:
        """查询指定策略类型 + 市场风格下的静态权重"""
        try:
            row = (self.session.query(self.model)
                   .filter_by(strategy_type=strategy_type,
                              market_style=market_style,
                              is_active=True)
                   .first())
            return float(row.static_weight) if row else None
        except SQLAlchemyError as e:
            logger.error(f"Error getting static weight for {strategy_type}/{market_style}: {e}")
            return None

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []

    @staticmethod
    def _to_dict(r: StrategyWeightConfig) -> Dict[str, Any]:
        return {
            'id': r.id,
            'strategy_type': r.strategy_type,
            'market_style': r.market_style,
            'static_weight': float(r.static_weight) if r.static_weight is not None else None,
            'is_active': r.is_active,
            'updated_at': r.updated_at.isoformat(sep=' ') if r.updated_at else None,
        }


__all__ = ['StrategyWeightORMRepository', 'StrategyWeightConfig']
