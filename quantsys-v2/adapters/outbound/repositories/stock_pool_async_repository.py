"""
Stock Pool 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, Text, BigInteger, JSON, Boolean, DateTime, select, ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class StockPool(Base):
    """股票池ORM模型 - 匹配实际数据库表结构"""
    __tablename__ = 'stock_pools'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    pool_type = Column(String(10), nullable=False)  # 'static', 'dynamic'
    description = Column(Text)
    symbols = Column(ARRAY(Text))  # text[] 数组
    filter_template = Column(JSON)  # jsonb
    refresh_interval = Column(String(20))  # 'daily', 'weekly'
    last_refreshed_at = Column(DateTime)
    last_validation = Column(JSON)  # jsonb
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    members = Column(JSON)  # jsonb - 成员列表
    scan_enabled = Column(Boolean, default=True)
    last_signal_scan = Column(JSON)  # jsonb


class StockPoolAsyncRepository(AsyncBaseORMRepository[StockPool]):
    """异步股票池Repository"""

    model = StockPool

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_pool(self, pool_id: int) -> Optional[Dict[str, Any]]:
        """获取股票池详情

        Args:
            pool_id: 股票池ID

        Returns:
            股票池字典或None
        """
        try:
            pool = await self.get_by_id(pool_id)
            if not pool:
                return None

            return {
                'id': pool.id,
                'name': pool.name,
                'pool_type': pool.pool_type,
                'description': pool.description,
                'symbols': pool.symbols,
                'filter_template': pool.filter_template,
                'refresh_interval': pool.refresh_interval,
                'last_refreshed_at': pool.last_refreshed_at.isoformat() if pool.last_refreshed_at else None,
                'last_validation': pool.last_validation,
                'created_at': pool.created_at.isoformat() if pool.created_at else None,
                'updated_at': pool.updated_at.isoformat() if pool.updated_at else None,
                'members': pool.members,
                'member_count': len(pool.members) if pool.members else 0,
                'scan_enabled': pool.scan_enabled,
                'last_signal_scan': pool.last_signal_scan,
            }
        except Exception as e:
            logger.error(f"Error getting pool {pool_id}: {e}")
            return None

    async def list_pools(
        self,
        pool_type: Optional[str] = None,
        scan_enabled: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出股票池

        Args:
            pool_type: 池子类型过滤（可选）
            scan_enabled: 扫描启用状态过滤（可选）
            limit: 返回数量
            offset: 偏移量

        Returns:
            股票池字典列表
        """
        try:
            conditions = {}
            if pool_type:
                conditions['pool_type'] = pool_type
            if scan_enabled is not None:
                conditions['scan_enabled'] = scan_enabled

            if conditions:
                pools = await self.find_by_condition(**conditions)
            else:
                pools = await self.list_all(limit=limit, offset=offset)

            return [
                {
                    'id': pool.id,
                    'name': pool.name,
                    'pool_type': pool.pool_type,
                    'description': pool.description,
                    'member_count': len(pool.members) if pool.members else 0,
                    'scan_enabled': pool.scan_enabled,
                    'created_at': pool.created_at.isoformat() if pool.created_at else None,
                    'last_refreshed_at': pool.last_refreshed_at.isoformat() if pool.last_refreshed_at else None,
                }
                for pool in pools
            ]
        except Exception as e:
            logger.error(f"Error listing pools: {e}")
            return []

    async def create_pool(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建股票池

        Args:
            data: 股票池数据

        Returns:
            创建的股票池字典或None
        """
        try:
            pool = await self.create(data)
            if not pool:
                return None

            return {
                'id': pool.id,
                'name': pool.name,
                'pool_type': pool.pool_type,
                'description': pool.description,
                'status': pool.status,
                'created_at': pool.created_at.isoformat() if pool.created_at else None,
            }
        except Exception as e:
            logger.error(f"Error creating pool: {e}")
            return None

    async def update_pool(self, pool_id: int, data: Dict[str, Any]) -> bool:
        """更新股票池

        Args:
            pool_id: 股票池ID
            data: 更新数据

        Returns:
            是否成功
        """
        try:
            # 添加updated_at
            from datetime import datetime
            data['updated_at'] = datetime.now()

            return await self.update_by_id(pool_id, data)
        except Exception as e:
            logger.error(f"Error updating pool {pool_id}: {e}")
            return False

    async def delete_pool(self, pool_id: int) -> bool:
        """删除股票池

        Args:
            pool_id: 股票池ID

        Returns:
            是否成功
        """
        try:
            return await self.delete_by_id(pool_id)
        except Exception as e:
            logger.error(f"Error deleting pool {pool_id}: {e}")
            return False

    async def find_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称查找股票池

        Args:
            name: 池子名称

        Returns:
            股票池字典或None
        """
        try:
            pool = await self.find_one_by_condition(name=name)
            if not pool:
                return None

            return await self.get_pool(pool.id)
        except Exception as e:
            logger.error(f"Error finding pool by name {name}: {e}")
            return None

    async def count_by_type(self, pool_type: str) -> int:
        """统计某类型的池子数量

        Args:
            pool_type: 池子类型

        Returns:
            数量
        """
        try:
            return await self.count(pool_type=pool_type)
        except Exception as e:
            logger.error(f"Error counting pools by type {pool_type}: {e}")
            return 0

    async def get_enabled_pools(self) -> List[Dict[str, Any]]:
        """获取所有启用扫描的股票池

        Returns:
            启用扫描的股票池列表
        """
        try:
            return await self.list_pools(scan_enabled=True)
        except Exception as e:
            logger.error(f"Error getting enabled pools: {e}")
            return []


__all__ = ['StockPoolAsyncRepository', 'StockPool']
