"""
Risk Config ORM Repository - 完全迁移版本

迁移状态：✅ 已完成ORM迁移
修复记录：2026-07-19 修正表名（risk_configs → risk_config）并补全业务方法
  - 原 stub 未实现抽象方法 get_risk_config，导致类无法实例化（API 500）
  - 补齐 get_config / update_config（signal_execution 路由与风控服务依赖）
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime, JSON
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import IRiskConfigRepository
from typing import Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class RiskConfig(Base):
    __tablename__ = 'risk_config'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    config_name = Column(String(100), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)

    max_single_order_percent = Column(Numeric(5, 2), default=20.00)
    max_daily_trade_amount = Column(Numeric(15, 2))
    min_cash_reserve_percent = Column(Numeric(5, 2), default=10.00)

    max_position_percent = Column(Numeric(5, 2), default=30.00)
    max_sector_percent = Column(Numeric(5, 2), default=40.00)
    max_total_position_percent = Column(Numeric(5, 2), default=95.00)

    max_daily_trades = Column(Integer, default=50)
    max_single_stock_trades = Column(Integer, default=5)

    require_stop_loss = Column(Boolean, default=True)
    min_stop_loss_percent = Column(Numeric(5, 2), default=3.00)
    max_stop_loss_percent = Column(Numeric(5, 2), default=15.00)

    config_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RiskConfigORMRepository(BaseORMRepository[RiskConfig], IRiskConfigRepository):
    """ORM Repository for risk_config"""
    model = RiskConfig

    # 允许通过 update_config 更新的字段
    _UPDATABLE_FIELDS = {
        'is_active',
        'max_single_order_percent', 'max_daily_trade_amount', 'min_cash_reserve_percent',
        'max_position_percent', 'max_sector_percent', 'max_total_position_percent',
        'max_daily_trades', 'max_single_stock_trades',
        'require_stop_loss', 'min_stop_loss_percent', 'max_stop_loss_percent',
        'config_data',
    }

    # ---------- 接口方法 ----------

    def get_risk_config(self, config_type: str) -> Optional[Dict[str, Any]]:
        """接口方法（IRiskConfigRepository）：按配置类型查询风控配置"""
        return self.get_config(config_type)

    # ---------- 业务方法 ----------

    def get_config(self, config_name: str = 'default') -> Optional[Dict[str, Any]]:
        """按名称查询风控配置，返回字典（不存在或已停用返回 None）。

        is_active 过滤是旧契约（停用配置视为不存在，风控服务走兜底）；
        ORM 迁移时丢失该过滤会导致停用配置照样生效——2026-08-04 恢复。
        """
        try:
            row = (self.session.query(self.model)
                   .filter_by(config_name=config_name, is_active=True)
                   .first())
            return self._to_dict(row) if row else None
        except SQLAlchemyError as e:
            logger.error(f"Error getting risk config '{config_name}': {e}")
            return None

    def update_config(self, config_name: str, data: Dict[str, Any]) -> bool:
        """更新风控配置，成功返回 True"""
        try:
            row = (self.session.query(self.model)
                   .filter_by(config_name=config_name)
                   .first())
            if row is None:
                logger.warning(f"Risk config not found: {config_name}")
                return False

            for key, value in data.items():
                if key in self._UPDATABLE_FIELDS:
                    setattr(row, key, value)
            row.updated_at = datetime.now()

            self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error updating risk config '{config_name}': {e}")
            self.session.rollback()
            return False

    def list_all(self, limit: int = 100) -> list:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []

    # ---------- 工具方法 ----------

    @staticmethod
    def _to_dict(row: RiskConfig) -> Dict[str, Any]:
        def f(v):
            """Numeric → float，保持 JSON 可序列化"""
            return float(v) if v is not None else None

        return {
            'id': row.id,
            'config_name': row.config_name,
            'is_active': row.is_active,
            'max_single_order_percent': f(row.max_single_order_percent),
            'max_daily_trade_amount': f(row.max_daily_trade_amount),
            'min_cash_reserve_percent': f(row.min_cash_reserve_percent),
            'max_position_percent': f(row.max_position_percent),
            'max_sector_percent': f(row.max_sector_percent),
            'max_total_position_percent': f(row.max_total_position_percent),
            'max_daily_trades': row.max_daily_trades,
            'max_single_stock_trades': row.max_single_stock_trades,
            'require_stop_loss': row.require_stop_loss,
            'min_stop_loss_percent': f(row.min_stop_loss_percent),
            'max_stop_loss_percent': f(row.max_stop_loss_percent),
            'config_data': row.config_data,
            'created_at': row.created_at.isoformat(sep=' ') if row.created_at else None,
            'updated_at': row.updated_at.isoformat(sep=' ') if row.updated_at else None,
        }


__all__ = ['RiskConfigORMRepository']
