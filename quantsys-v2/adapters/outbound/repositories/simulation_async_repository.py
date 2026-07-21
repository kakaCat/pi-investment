"""
Simulation 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from infrastructure.persistence.orm.models import SimulationAccount, SimulationPosition, SimulationTrade
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class SimulationAccountAsyncRepository(AsyncBaseORMRepository[SimulationAccount]):
    """异步模拟账户Repository"""

    model = SimulationAccount

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_account(self, account_name: str = 'default') -> Optional[Dict[str, Any]]:
        """获取账户信息

        Args:
            account_name: 账户名称

        Returns:
            账户字典或None
        """
        try:
            account = await self.find_one_by_condition(account_name=account_name)
            if not account:
                return None

            return self._account_to_dict(account)

        except Exception as e:
            logger.error(f"Error getting account {account_name}: {e}")
            return None

    async def create_account(self, account_data: Dict[str, Any]) -> Optional[int]:
        """创建账户

        Args:
            account_data: 账户数据

        Returns:
            账户ID或None
        """
        try:
            account = await self.create(account_data)
            return account.id if account else None

        except Exception as e:
            logger.error(f"Error creating account: {e}")
            return None

    async def update_account(
        self,
        account_name: str,
        updates: Dict[str, Any]
    ) -> bool:
        """更新账户

        Args:
            account_name: 账户名称
            updates: 更新数据

        Returns:
            是否成功
        """
        try:
            account = await self.find_one_by_condition(account_name=account_name)
            if not account:
                return False

            return await self.update_by_id(account.id, updates)

        except Exception as e:
            logger.error(f"Error updating account {account_name}: {e}")
            return False

    def _account_to_dict(self, account: SimulationAccount) -> Dict[str, Any]:
        """将SimulationAccount对象转换为字典"""
        return {
            'id': account.id,
            'account_name': account.account_name,
            'cash': float(account.cash) if account.cash else 0,
            'total_value': float(account.total_value) if account.total_value else 0,
            'peak_value': float(account.peak_value) if account.peak_value else 0,
            'cumulative_return': float(account.cumulative_return) if account.cumulative_return else 0,
            'max_drawdown': float(account.max_drawdown) if account.max_drawdown else 0,
            'last_rebalance_date': account.last_rebalance_date.isoformat() if account.last_rebalance_date else None,
            'created_at': account.created_at.isoformat() if account.created_at else None,
            'updated_at': account.updated_at.isoformat() if account.updated_at else None,
        }


class SimulationPositionAsyncRepository(AsyncBaseORMRepository[SimulationPosition]):
    """异步模拟持仓Repository"""

    model = SimulationPosition

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_positions(
        self,
        account_name: str = 'default'
    ) -> List[Dict[str, Any]]:
        """获取持仓列表

        Args:
            account_name: 账户名称

        Returns:
            持仓列表
        """
        try:
            positions = await self.find_by_condition(account_name=account_name)
            return [self._position_to_dict(p) for p in positions]

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def get_position(
        self,
        account_name: str,
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """获取单个持仓

        Args:
            account_name: 账户名称
            symbol: 股票代码

        Returns:
            持仓字典或None
        """
        try:
            position = await self.find_one_by_condition(
                account_name=account_name,
                symbol=symbol
            )
            if not position:
                return None

            return self._position_to_dict(position)

        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None

    def _position_to_dict(self, position: SimulationPosition) -> Dict[str, Any]:
        """将SimulationPosition对象转换为字典"""
        return {
            'id': position.id,
            'account_name': position.account_name,
            'symbol': position.symbol,
            'quantity': position.quantity,
            'cost_price': float(position.cost_price) if position.cost_price else 0,
            'current_price': float(position.current_price) if position.current_price else 0,
            'market_value': float(position.market_value) if position.market_value else 0,
            'profit_loss': float(position.profit_loss) if position.profit_loss else 0,
            'profit_loss_ratio': float(position.profit_loss_ratio) if position.profit_loss_ratio else 0,
            'updated_at': position.updated_at.isoformat() if position.updated_at else None,
        }


class SimulationTradeAsyncRepository(AsyncBaseORMRepository[SimulationTrade]):
    """异步模拟交易Repository"""

    model = SimulationTrade

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_trades(
        self,
        account_name: str = 'default',
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取交易记录

        Args:
            account_name: 账户名称
            symbol: 股票代码（可选）
            limit: 返回数量

        Returns:
            交易记录列表
        """
        try:
            stmt = select(SimulationTrade).where(
                SimulationTrade.account_name == account_name
            )

            if symbol:
                stmt = stmt.where(SimulationTrade.symbol == symbol)

            stmt = stmt.order_by(desc(SimulationTrade.trade_date)).limit(limit)

            result = await self.session.execute(stmt)
            trades = result.scalars().all()

            return [self._trade_to_dict(t) for t in trades]

        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return []

    async def create_trade(self, trade_data: Dict[str, Any]) -> Optional[int]:
        """创建交易记录

        Args:
            trade_data: 交易数据

        Returns:
            交易ID或None
        """
        try:
            trade = await self.create(trade_data)
            return trade.id if trade else None

        except Exception as e:
            logger.error(f"Error creating trade: {e}")
            return None

    def _trade_to_dict(self, trade: SimulationTrade) -> Dict[str, Any]:
        """将SimulationTrade对象转换为字典"""
        return {
            'id': trade.id,
            'account_name': trade.account_name,
            'trade_date': trade.trade_date.isoformat() if trade.trade_date else None,
            'symbol': trade.symbol,
            'action': trade.action,
            'quantity': trade.quantity,
            'price': float(trade.price) if trade.price else 0,
            'amount': float(trade.amount) if trade.amount else 0,
            'commission': float(trade.commission) if trade.commission else 0,
            'notes': trade.notes,
            'created_at': trade.created_at.isoformat() if trade.created_at else None,
        }


__all__ = [
    'SimulationAccountAsyncRepository',
    'SimulationPositionAsyncRepository',
    'SimulationTradeAsyncRepository'
]
