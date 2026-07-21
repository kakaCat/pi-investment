"""
信号执行ORM Repository

管理信号执行记录的创建、状态流转、平仓和统计

迁移状态：✅ 已完成ORM迁移
"""
from typing import List, Optional, Dict
from datetime import date, datetime
import structlog

from sqlalchemy import func, desc, and_
from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import SignalExecution
from domain.ports import ISignalExecutionRepository

logger = structlog.get_logger(__name__)

__all__ = ['SignalExecutionORMRepository']


class SignalExecutionORMRepository(BaseORMRepository[SignalExecution], ISignalExecutionRepository):
    """信号执行ORM Repository

    对应表：quant.signal_executions
    """

    model = SignalExecution
    STATUSES = ('pending', 'executed', 'cancelled', 'expired')

    # ==================== 查询方法 ====================

    def get_execution(self, execution_id: int) -> Optional[SignalExecution]:
        """根据ID查询执行记录

        Args:
            execution_id: 执行记录ID

        Returns:
            SignalExecution对象
        """
        return self.get_by_id(execution_id)

    def get_executions_by_signal(
        self,
        signal_id: int
    ) -> List[SignalExecution]:
        """查询信号的所有执行记录

        Args:
            signal_id: 信号ID

        Returns:
            SignalExecution列表
        """
        try:
            return self.session.query(SignalExecution).filter(
                SignalExecution.signal_id == signal_id
            ).order_by(SignalExecution.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting executions for signal {signal_id}: {e}")
            return []

    def get_executions_by_date(
        self,
        execution_date: str,
        status: Optional[str] = None
    ) -> List[SignalExecution]:
        """查询指定日期的执行记录

        Args:
            execution_date: 执行日期
            status: 状态筛选

        Returns:
            SignalExecution列表
        """
        try:
            query = self.session.query(SignalExecution).filter(
                SignalExecution.execution_date == execution_date
            )

            if status:
                if status not in self.STATUSES:
                    raise ValueError(f"Invalid status: {status}")
                query = query.filter(SignalExecution.status == status)

            return query.order_by(SignalExecution.created_at.desc()).all()

        except Exception as e:
            logger.error(f"Error getting executions by date: {e}")
            return []

    def get_pending_executions(self) -> List[SignalExecution]:
        """查询所有待执行的记录

        Returns:
            SignalExecution列表
        """
        try:
            return self.session.query(SignalExecution).filter(
                SignalExecution.status == 'pending'
            ).order_by(SignalExecution.created_at).all()
        except Exception as e:
            logger.error(f"Error getting pending executions: {e}")
            return []

    def get_all_executions(self, limit: int = 200) -> List[SignalExecution]:
        """获取所有执行记录（兼容方法名）

        Args:
            limit: 返回数量限制

        Returns:
            SignalExecution列表
        """
        try:
            return self.session.query(SignalExecution).order_by(
                SignalExecution.created_at.desc()
            ).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting all executions: {e}")
            return []

    # ==================== 创建和更新 ====================

    def create_execution(
        self,
        signal_id: int,
        execution_date: str,
        execution_price: float,
        quantity: int,
        commission: float = 0.0,
        status: str = 'pending'
    ) -> Optional[SignalExecution]:
        """创建执行记录

        Args:
            signal_id: 信号ID
            execution_date: 执行日期
            execution_price: 执行价格
            quantity: 数量
            commission: 佣金
            status: 状态

        Returns:
            创建的SignalExecution对象
        """
        try:
            execution = SignalExecution(
                signal_id=signal_id,
                execution_date=execution_date,
                execution_price=execution_price,
                quantity=quantity,
                commission=commission,
                status=status
            )
            return self.create(execution, commit=True)
        except Exception as e:
            logger.error(f"Error creating execution: {e}")
            return None

    def update_status(
        self,
        execution_id: int,
        status: str
    ) -> bool:
        """更新执行状态

        Args:
            execution_id: 执行记录ID
            status: 新状态

        Returns:
            成功返回True
        """
        if status not in self.STATUSES:
            raise ValueError(f"Invalid status: {status}")

        try:
            execution = self.get_by_id(execution_id)
            if not execution:
                return False

            execution.status = status
            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error updating execution status: {e}")
            self.session.rollback()
            return False

    def update_execution_status(
        self,
        execution_id: int,
        status: str
    ) -> bool:
        """更新执行状态（兼容方法名）

        Args:
            execution_id: 执行记录ID
            status: 新状态

        Returns:
            成功返回True
        """
        return self.update_status(execution_id, status)

    def cancel_execution(self, execution_id: int) -> bool:
        """取消执行记录（兼容方法名）

        Args:
            execution_id: 执行记录ID

        Returns:
            成功返回True
        """
        return self.update_status(execution_id, 'cancelled')

    def close_execution(
        self,
        execution_id: int,
        close_date: str,
        close_price: float,
        pnl: float
    ) -> bool:
        """平仓执行记录

        Args:
            execution_id: 执行记录ID
            close_date: 平仓日期
            close_price: 平仓价格
            pnl: 盈亏

        Returns:
            成功返回True
        """
        try:
            execution = self.get_by_id(execution_id)
            if not execution:
                return False

            execution.close_date = close_date
            execution.close_price = close_price
            execution.pnl = pnl
            execution.status = 'executed'

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error closing execution: {e}")
            self.session.rollback()
            return False

    # ==================== 统计方法 ====================

    def get_total_pnl(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> float:
        """计算总盈亏

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            总盈亏
        """
        try:
            query = self.session.query(
                func.sum(SignalExecution.pnl)
            ).filter(SignalExecution.pnl.isnot(None))

            if start_date:
                query = query.filter(SignalExecution.close_date >= start_date)
            if end_date:
                query = query.filter(SignalExecution.close_date <= end_date)

            result = query.scalar()
            return float(result or 0)

        except Exception as e:
            logger.error(f"Error calculating total pnl: {e}")
            return 0.0

    def get_win_rate(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> float:
        """计算胜率

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            胜率（0-1）
        """
        try:
            query = self.session.query(SignalExecution).filter(
                SignalExecution.pnl.isnot(None)
            )

            if start_date:
                query = query.filter(SignalExecution.close_date >= start_date)
            if end_date:
                query = query.filter(SignalExecution.close_date <= end_date)

            executions = query.all()
            if not executions:
                return 0.0

            winning = sum(1 for e in executions if e.pnl > 0)
            return winning / len(executions)

        except Exception as e:
            logger.error(f"Error calculating win rate: {e}")
            return 0.0

    def get_execution_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """获取执行统计信息

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计信息字典
        """
        try:
            query = self.session.query(SignalExecution)

            if start_date:
                query = query.filter(SignalExecution.execution_date >= start_date)
            if end_date:
                query = query.filter(SignalExecution.execution_date <= end_date)

            executions = query.all()
            closed = [e for e in executions if e.pnl is not None]

            total_pnl = sum(e.pnl for e in closed)
            winning = [e for e in closed if e.pnl > 0]
            losing = [e for e in closed if e.pnl <= 0]

            return {
                'total_executions': len(executions),
                'closed_executions': len(closed),
                'pending_executions': len([e for e in executions if e.status == 'pending']),
                'total_pnl': float(total_pnl),
                'win_rate': len(winning) / len(closed) if closed else 0.0,
                'avg_win': sum(e.pnl for e in winning) / len(winning) if winning else 0.0,
                'avg_loss': sum(e.pnl for e in losing) / len(losing) if losing else 0.0,
            }

        except Exception as e:
            logger.error(f"Error getting execution stats: {e}")
            return {}

    def get_daily_execution_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """获取每日执行统计

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            每日统计列表
        """
        try:
            query = self.session.query(
                SignalExecution.execution_date,
                func.count(SignalExecution.id).label('count'),
                func.sum(SignalExecution.pnl).label('total_pnl')
            ).filter(SignalExecution.execution_date.isnot(None))

            if start_date:
                query = query.filter(SignalExecution.execution_date >= start_date)
            if end_date:
                query = query.filter(SignalExecution.execution_date <= end_date)

            query = query.group_by(SignalExecution.execution_date).order_by(
                SignalExecution.execution_date.desc()
            )

            results = query.all()
            return [
                {
                    'date': str(r.execution_date),
                    'count': r.count,
                    'total_pnl': float(r.total_pnl or 0)
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"Error getting daily execution stats: {e}")
            return []
