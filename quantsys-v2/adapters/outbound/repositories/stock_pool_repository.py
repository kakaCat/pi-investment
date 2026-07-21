"""
Stock Pool ORM Repository - 完全迁移版本

迁移状态：✅ 已完成ORM迁移
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, Text, BigInteger, JSON, Boolean, DateTime
from infrastructure.persistence.orm.base import Base
from domain.ports import IStockPoolRepository
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)

class StockPool(Base):
    __tablename__ = 'stock_pools'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    pool_type = Column(String(10), nullable=False)
    description = Column(Text)
    symbols = Column(Text)
    filter_template = Column(JSON)
    refresh_interval = Column(String(20))
    last_refreshed_at = Column(DateTime)
    last_validation = Column(JSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    members = Column(JSON)
    scan_enabled = Column(Boolean, default=True)
    last_signal_scan = Column(JSON)

class StockPoolORMRepository(BaseORMRepository[StockPool], IStockPoolRepository):
    """ORM Repository for stock_pools"""
    model = StockPool

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing: {e}")
            return []

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有股票池（兼容旧接口）"""
        try:
            pools = self.session.query(self.model).all()
            return [{
                'id': pool.id,
                'name': pool.name,
                'pool_type': pool.pool_type,
                'description': pool.description,
                'symbols': pool.symbols if isinstance(pool.symbols, list) else [],
                'filter_template': pool.filter_template,
                'refresh_interval': pool.refresh_interval,
                'last_refreshed_at': pool.last_refreshed_at.isoformat() if pool.last_refreshed_at else None,
                'last_validation': pool.last_validation,
                'created_at': pool.created_at.isoformat() if pool.created_at else None,
                'updated_at': pool.updated_at.isoformat() if pool.updated_at else None,
                'members': pool.members if pool.members else [],
                'scan_enabled': pool.scan_enabled,
                'last_signal_scan': pool.last_signal_scan,
            } for pool in pools]
        except Exception as e:
            logger.error(f"Error getting all pools: {e}")
            return []

    def get_pool(self, pool_id: int) -> Optional[Dict[str, Any]]:
        """获取股票池（IStockPoolRepository接口实现）"""
        try:
            pool = self.get_by_id(pool_id)
            if not pool:
                return None
            return {
                'id': pool.id,
                'name': pool.name,
                'pool_type': pool.pool_type,
                'description': pool.description,
                'symbols': pool.symbols if isinstance(pool.symbols, list) else [],
                'filter_template': pool.filter_template,
                'refresh_interval': pool.refresh_interval,
                'last_refreshed_at': pool.last_refreshed_at.isoformat() if pool.last_refreshed_at else None,
                'last_validation': pool.last_validation,
                'created_at': pool.created_at.isoformat() if pool.created_at else None,
                'updated_at': pool.updated_at.isoformat() if pool.updated_at else None,
                'members': pool.members if pool.members else [],
                'scan_enabled': pool.scan_enabled,
                'last_signal_scan': pool.last_signal_scan,
            }
        except Exception as e:
            logger.error(f"Error getting pool {pool_id}: {e}")
            return None

    def update_signal_scan(self, pool_id: int, scan_result: Dict[str, Any]) -> bool:
        """更新股票池的信号扫描结果"""
        try:
            pool = self.get_by_id(pool_id)
            if not pool:
                logger.error(f"Pool {pool_id} not found")
                return False

            # 更新扫描结果和扫描时间
            from datetime import datetime
            pool.last_signal_scan = {
                **scan_result,
                'scanned_at': datetime.now().isoformat()
            }

            self.session.commit()
            logger.info(f"Updated signal scan for pool {pool_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating signal scan for pool {pool_id}: {e}")
            self.session.rollback()
            return False

__all__ = ['StockPoolORMRepository']
