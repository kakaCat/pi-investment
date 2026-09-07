"""
Backtest 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from infrastructure.persistence.orm.models import BacktestResult
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class BacktestAsyncRepository(AsyncBaseORMRepository[BacktestResult]):
    """异步回测Repository"""

    model = BacktestResult

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_backtest(self, backtest_id: int) -> Optional[Dict[str, Any]]:
        """获取回测详情

        Args:
            backtest_id: 回测ID

        Returns:
            回测字典或None
        """
        try:
            backtest = await self.get_by_id(backtest_id)
            if not backtest:
                return None

            return self._backtest_to_dict(backtest)

        except Exception as e:
            logger.error(f"Error getting backtest {backtest_id}: {e}")
            return None

    async def list_backtests(
        self,
        strategy_name: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """列出回测结果

        Args:
            strategy_name: 策略名称过滤（可选）
            symbol: 股票代码过滤（可选）
            limit: 返回数量

        Returns:
            回测结果列表
        """
        try:
            stmt = select(BacktestResult)

            if strategy_name:
                stmt = stmt.where(BacktestResult.strategy_name == strategy_name)
            if symbol:
                stmt = stmt.where(BacktestResult.symbol == symbol)

            stmt = stmt.order_by(desc(BacktestResult.created_at)).limit(limit)

            result = await self.session.execute(stmt)
            backtests = result.scalars().all()

            return [self._backtest_to_dict(b) for b in backtests]

        except Exception as e:
            logger.error(f"Error listing backtests: {e}")
            return []

    async def create_backtest(self, backtest_data: Dict[str, Any]) -> Optional[int]:
        """创建回测结果

        Args:
            backtest_data: 回测数据

        Returns:
            回测ID或None
        """
        try:
            backtest = await self.create(backtest_data)
            return backtest.id if backtest else None

        except Exception as e:
            logger.error(f"Error creating backtest: {e}")
            return None

    async def get_best_backtests(
        self,
        strategy_name: Optional[str] = None,
        min_sharpe_ratio: float = 1.0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取最佳回测结果（按Sharpe比率排序）

        Args:
            strategy_name: 策略名称过滤（可选）
            min_sharpe_ratio: 最小Sharpe比率
            limit: 返回数量

        Returns:
            回测结果列表
        """
        try:
            stmt = select(BacktestResult).where(
                BacktestResult.sharpe_ratio >= min_sharpe_ratio
            )

            if strategy_name:
                stmt = stmt.where(BacktestResult.strategy_name == strategy_name)

            stmt = stmt.order_by(desc(BacktestResult.sharpe_ratio)).limit(limit)

            result = await self.session.execute(stmt)
            backtests = result.scalars().all()

            return [self._backtest_to_dict(b) for b in backtests]

        except Exception as e:
            logger.error(f"Error getting best backtests: {e}")
            return []

    async def get_recent_backtests(
        self,
        strategy_name: Optional[str] = None,
        days: int = 30,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取最近的回测结果

        Args:
            strategy_name: 策略名称过滤（可选）
            days: 最近N天
            limit: 返回数量

        Returns:
            回测结果列表
        """
        try:
            from datetime import datetime, timedelta

            cutoff_date = datetime.now() - timedelta(days=days)

            stmt = select(BacktestResult).where(
                BacktestResult.created_at >= cutoff_date
            )

            if strategy_name:
                stmt = stmt.where(BacktestResult.strategy_name == strategy_name)

            stmt = stmt.order_by(desc(BacktestResult.created_at)).limit(limit)

            result = await self.session.execute(stmt)
            backtests = result.scalars().all()

            return [self._backtest_to_dict(b) for b in backtests]

        except Exception as e:
            logger.error(f"Error getting recent backtests: {e}")
            return []

    async def delete_backtest(self, backtest_id: int) -> bool:
        """删除回测结果

        Args:
            backtest_id: 回测ID

        Returns:
            是否成功
        """
        try:
            return await self.delete_by_id(backtest_id)

        except Exception as e:
            logger.error(f"Error deleting backtest {backtest_id}: {e}")
            return False

    def _backtest_to_dict(self, backtest: BacktestResult) -> Dict[str, Any]:
        """将BacktestResult对象转换为字典"""
        return {
            'id': backtest.id,
            'strategy_name': backtest.strategy_name,
            'symbol': backtest.symbol,
            'parameters': backtest.parameters,
            'start_date': backtest.start_date.isoformat() if backtest.start_date else None,
            'end_date': backtest.end_date.isoformat() if backtest.end_date else None,
            'initial_capital': backtest.initial_capital,
            'final_capital': backtest.final_capital,
            'total_return': backtest.total_return,
            'annual_return': backtest.annual_return,
            'sharpe_ratio': backtest.sharpe_ratio,
            'max_drawdown': backtest.max_drawdown,
            'win_rate': backtest.win_rate,
            'trade_count': backtest.trade_count,
            'created_at': backtest.created_at.isoformat() if backtest.created_at else None,
        }


__all__ = ['BacktestAsyncRepository']
