"""
SignalExecution 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from infrastructure.persistence.orm.models import SignalExecution
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class SignalExecutionAsyncRepository(AsyncBaseORMRepository[SignalExecution]):
    """异步信号执行Repository"""

    model = SignalExecution

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_executions_by_signal(
        self,
        signal_id: int
    ) -> List[Dict[str, Any]]:
        """查询信号的所有执行记录

        Args:
            signal_id: 信号ID

        Returns:
            执行记录列表
        """
        try:
            executions = await self.find_by_condition(signal_id=signal_id)
            return [self._execution_to_dict(e) for e in executions]

        except Exception as e:
            logger.error(f"Error getting executions by signal: {e}")
            return []

    async def get_executions(
        self,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取执行记录

        Args:
            status: 状态过滤（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回数量

        Returns:
            执行记录列表
        """
        try:
            stmt = select(SignalExecution)

            if status:
                stmt = stmt.where(SignalExecution.status == status)
            if start_date:
                stmt = stmt.where(SignalExecution.executed_at >= start_date)
            if end_date:
                stmt = stmt.where(SignalExecution.executed_at <= end_date)

            stmt = stmt.order_by(desc(SignalExecution.executed_at)).limit(limit)

            result = await self.session.execute(stmt)
            executions = result.scalars().all()

            return [self._execution_to_dict(e) for e in executions]

        except Exception as e:
            logger.error(f"Error getting executions: {e}")
            return []

    async def create_execution(
        self,
        execution_data: Dict[str, Any]
    ) -> Optional[int]:
        """创建执行记录

        Args:
            execution_data: 执行数据

        Returns:
            执行ID或None
        """
        try:
            execution = await self.create(execution_data)
            return execution.id if execution else None

        except Exception as e:
            logger.error(f"Error creating execution: {e}")
            return None

    async def update_execution_status(
        self,
        execution_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """更新执行状态

        Args:
            execution_id: 执行ID
            status: 新状态
            error_message: 错误消息（可选）

        Returns:
            是否成功
        """
        try:
            update_data = {'status': status}
            if error_message:
                update_data['error_message'] = error_message

            return await self.update_by_id(execution_id, update_data)

        except Exception as e:
            logger.error(f"Error updating execution status: {e}")
            return False

    async def get_pending_executions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待执行记录

        Args:
            limit: 返回数量

        Returns:
            待执行记录列表
        """
        return await self.get_executions(status='pending', limit=limit)

    def _execution_to_dict(self, execution: SignalExecution) -> Dict[str, Any]:
        """将SignalExecution对象转换为字典"""
        return {
            'id': execution.id,
            'signal_id': execution.signal_id,
            'executed_at': execution.executed_at.isoformat() if execution.executed_at else None,
            'status': execution.status,
            'execution_price': execution.execution_price,
            'execution_quantity': execution.execution_quantity,
            'commission': execution.commission,
            'error_message': execution.error_message,
            'created_at': execution.created_at.isoformat() if execution.created_at else None,
        }


__all__ = ['SignalExecutionAsyncRepository']
