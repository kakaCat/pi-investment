"""
Strategy 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from sqlalchemy import Column, BigInteger, String, Text, JSON, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class Strategy(Base):
    """策略ORM模型"""
    __tablename__ = 'strategies'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    strategy_name = Column(String(100))
    strategy_type = Column(String(50))
    description = Column(Text)
    parameters = Column(JSON)


class StrategyAsyncRepository(AsyncBaseORMRepository[Strategy]):
    """异步策略Repository"""

    model = Strategy

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_strategy(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """获取策略详情

        Args:
            strategy_id: 策略ID

        Returns:
            策略字典或None
        """
        try:
            strategy = await self.get_by_id(strategy_id)
            if not strategy:
                return None

            return self._strategy_to_dict(strategy)

        except Exception as e:
            logger.error(f"Error getting strategy {strategy_id}: {e}")
            return None

    async def list_strategies(
        self,
        strategy_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """列出策略

        Args:
            strategy_type: 策略类型过滤（可选）
            limit: 返回数量

        Returns:
            策略列表
        """
        try:
            if strategy_type:
                strategies = await self.find_by_condition(strategy_type=strategy_type)
            else:
                strategies = await self.list_all(limit=limit)

            return [self._strategy_to_dict(s) for s in strategies]

        except Exception as e:
            logger.error(f"Error listing strategies: {e}")
            return []

    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称查找策略

        Args:
            name: 策略名称

        Returns:
            策略字典或None
        """
        try:
            strategy = await self.find_one_by_condition(strategy_name=name)
            if not strategy:
                return None

            return self._strategy_to_dict(strategy)

        except Exception as e:
            logger.error(f"Error finding strategy by name {name}: {e}")
            return None

    async def create_strategy(self, strategy_data: Dict[str, Any]) -> Optional[int]:
        """创建策略

        Args:
            strategy_data: 策略数据

        Returns:
            策略ID或None
        """
        try:
            strategy = await self.create(strategy_data)
            return strategy.id if strategy else None

        except Exception as e:
            logger.error(f"Error creating strategy: {e}")
            return None

    async def update_strategy(self, strategy_id: int, updates: Dict[str, Any]) -> bool:
        """更新策略

        Args:
            strategy_id: 策略ID
            updates: 更新数据

        Returns:
            是否成功
        """
        try:
            return await self.update_by_id(strategy_id, updates)

        except Exception as e:
            logger.error(f"Error updating strategy {strategy_id}: {e}")
            return False

    async def delete_strategy(self, strategy_id: int) -> bool:
        """删除策略

        Args:
            strategy_id: 策略ID

        Returns:
            是否成功
        """
        try:
            return await self.delete_by_id(strategy_id)

        except Exception as e:
            logger.error(f"Error deleting strategy {strategy_id}: {e}")
            return False

    def _strategy_to_dict(self, strategy: Strategy) -> Dict[str, Any]:
        """将Strategy对象转换为字典"""
        return {
            'id': strategy.id,
            'strategy_name': strategy.strategy_name,
            'strategy_type': strategy.strategy_type,
            'description': strategy.description,
            'parameters': strategy.parameters,
        }


__all__ = ['StrategyAsyncRepository', 'Strategy']
