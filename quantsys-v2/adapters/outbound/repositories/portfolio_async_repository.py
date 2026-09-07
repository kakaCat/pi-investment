"""
Portfolio 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from infrastructure.persistence.orm.models import PortfolioHolding
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class PortfolioAsyncRepository(AsyncBaseORMRepository[PortfolioHolding]):
    """异步持仓Repository"""

    model = PortfolioHolding

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_holding(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取持仓详情

        Args:
            symbol: 股票代码

        Returns:
            持仓字典或None
        """
        try:
            holding = await self.find_one_by_condition(symbol=symbol)
            if not holding:
                return None

            return self._holding_to_dict(holding)

        except Exception as e:
            logger.error(f"Error getting holding {symbol}: {e}")
            return None

    async def list_holdings(
        self,
        market: Optional[str] = None,
        sector: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """列出持仓

        Args:
            market: 市场过滤（可选）
            sector: 板块过滤（可选）
            limit: 返回数量

        Returns:
            持仓列表
        """
        try:
            conditions = {}
            if market:
                conditions['market'] = market
            if sector:
                conditions['sector'] = sector

            if conditions:
                holdings = await self.find_by_condition(**conditions)
            else:
                holdings = await self.list_all(limit=limit)

            return [self._holding_to_dict(h) for h in holdings]

        except Exception as e:
            logger.error(f"Error listing holdings: {e}")
            return []

    async def create_holding(self, holding_data: Dict[str, Any]) -> Optional[int]:
        """创建持仓

        Args:
            holding_data: 持仓数据

        Returns:
            持仓ID或None
        """
        try:
            holding = await self.create(holding_data)
            return holding.id if holding else None

        except Exception as e:
            logger.error(f"Error creating holding: {e}")
            return None

    async def update_holding(self, symbol: str, updates: Dict[str, Any]) -> bool:
        """更新持仓

        Args:
            symbol: 股票代码
            updates: 更新数据

        Returns:
            是否成功
        """
        try:
            holding = await self.find_one_by_condition(symbol=symbol)
            if not holding:
                return False

            return await self.update_by_id(holding.id, updates)

        except Exception as e:
            logger.error(f"Error updating holding {symbol}: {e}")
            return False

    async def delete_holding(self, symbol: str) -> bool:
        """删除持仓

        Args:
            symbol: 股票代码

        Returns:
            是否成功
        """
        try:
            holding = await self.find_one_by_condition(symbol=symbol)
            if not holding:
                return False

            return await self.delete_by_id(holding.id)

        except Exception as e:
            logger.error(f"Error deleting holding {symbol}: {e}")
            return False

    async def get_all_holdings(self) -> List[Dict[str, Any]]:
        """获取所有持仓

        Returns:
            所有持仓列表
        """
        return await self.list_holdings(limit=1000)

    async def count_holdings(self) -> int:
        """统计持仓数量

        Returns:
            持仓数量
        """
        return await self.count()

    def _holding_to_dict(self, holding: PortfolioHolding) -> Dict[str, Any]:
        """将PortfolioHolding对象转换为字典"""
        return {
            'id': holding.id,
            'symbol': holding.symbol,
            'name': holding.name,
            'market': holding.market,
            'sector': holding.sector,
            'quantity': holding.quantity,
            'available_quantity': holding.available_quantity,
            'cost_price': holding.cost_price,
            'current_price': holding.current_price,
            'market_value': holding.market_value,
            'profit_loss': holding.profit_loss,
            'profit_loss_ratio': holding.profit_loss_ratio,
            'added_date': holding.added_date.isoformat() if holding.added_date else None,
            'updated_at': holding.updated_at.isoformat() if holding.updated_at else None,
        }


__all__ = ['PortfolioAsyncRepository']
