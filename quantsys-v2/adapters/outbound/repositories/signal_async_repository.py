"""
Signal 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from infrastructure.persistence.orm.models import Signal
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import date
import structlog

logger = structlog.get_logger(__name__)


class SignalAsyncRepository(AsyncBaseORMRepository[Signal]):
    """异步信号Repository"""

    model = Signal

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_signals(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        signal_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取信号列表

        Args:
            symbol: 股票代码（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            signal_type: 信号类型（可选），即action字段
            status: 信号状态（可选）
            limit: 返回数量

        Returns:
            信号字典列表
        """
        try:
            stmt = select(Signal)

            if symbol:
                stmt = stmt.where(Signal.symbol == symbol)
            if start_date:
                stmt = stmt.where(Signal.signal_date >= start_date)
            if end_date:
                stmt = stmt.where(Signal.signal_date <= end_date)
            if signal_type:
                stmt = stmt.where(Signal.action == signal_type)
            if status:
                stmt = stmt.where(Signal.status == status)

            stmt = stmt.order_by(desc(Signal.signal_date)).limit(limit)

            result = await self.session.execute(stmt)
            signals = result.scalars().all()

            return [self._signal_to_dict(s) for s in signals]

        except Exception as e:
            logger.error(f"Error getting signals: {e}")
            return []

    async def create_signal(self, signal_data: Dict[str, Any]) -> Optional[int]:
        """创建信号

        Args:
            signal_data: 信号数据字典

        Returns:
            信号ID或None
        """
        try:
            signal = await self.create(signal_data)
            return signal.id if signal else None

        except Exception as e:
            logger.error(f"Error creating signal: {e}")
            return None

    async def update_signal_status(
        self,
        signal_id: int,
        status: str,
        error_description: Optional[str] = None
    ) -> bool:
        """更新信号状态

        Args:
            signal_id: 信号ID
            status: 新状态
            error_description: 错误描述（可选）

        Returns:
            是否成功
        """
        try:
            update_data = {'status': status}
            if error_description:
                update_data['error_description'] = error_description

            return await self.update_by_id(signal_id, update_data)

        except Exception as e:
            logger.error(f"Error updating signal status: {e}")
            return False

    async def get_pending_signals(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待处理的信号

        Args:
            limit: 返回数量

        Returns:
            待处理信号列表
        """
        return await self.get_signals(status='pending', limit=limit)

    async def get_signals_by_strategy(
        self,
        strategy_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """按策略查询信号

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            信号列表
        """
        try:
            stmt = select(Signal).where(Signal.strategy_id == strategy_id)

            if start_date:
                stmt = stmt.where(Signal.signal_date >= start_date)
            if end_date:
                stmt = stmt.where(Signal.signal_date <= end_date)

            stmt = stmt.order_by(desc(Signal.signal_date))

            result = await self.session.execute(stmt)
            signals = result.scalars().all()

            return [self._signal_to_dict(s) for s in signals]

        except Exception as e:
            logger.error(f"Error getting signals by strategy: {e}")
            return []

    async def count_by_status(self, status: str) -> int:
        """统计某状态的信号数量

        Args:
            status: 信号状态

        Returns:
            数量
        """
        return await self.count(status=status)

    def _signal_to_dict(self, signal: Signal) -> Dict[str, Any]:
        """将Signal对象转换为字典"""
        return {
            'id': signal.id,
            'symbol': signal.symbol,
            'signal_date': signal.signal_date.isoformat() if signal.signal_date else None,
            'action': signal.action,
            'action_type': signal.action_type,
            'strategy_id': signal.strategy_id,
            'name': signal.name,
            'price': signal.price,
            'confidence': signal.confidence,
            'reason': signal.reason,
            'status': signal.status,
            'indicators': signal.indicators,
            'created_at': signal.created_at.isoformat() if signal.created_at else None,
            'updated_at': signal.updated_at.isoformat() if signal.updated_at else None,
            'reject_reason': signal.reject_reason,
            'error_description': signal.error_description,
        }


__all__ = ['SignalAsyncRepository']
