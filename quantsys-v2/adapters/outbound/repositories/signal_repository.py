"""
交易信号ORM Repository

使用SQLAlchemy ORM重构的信号数据访问层

支持：
1. 信号查询（按日期/股票/策略）
2. 信号创建和更新
3. 信号统计
4. 状态管理

迁移状态：✅ 已完成ORM迁移

DDD架构：
- 实现 domain.ports.ISignalRepository 接口
- 符合依赖倒置原则
"""
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import structlog

from sqlalchemy import and_, or_, func, desc
from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import Signal, SignalExecution
from domain.ports import ISignalRepository

logger = structlog.get_logger(__name__)

__all__ = ['SignalORMRepository']


class SignalORMRepository(BaseORMRepository[Signal], ISignalRepository):
    """交易信号ORM Repository

    示例用法：
        repo = SignalORMRepository()

        # 查询单个信号
        signal = repo.get_signal(123)

        # 按日期查询
        signals = repo.get_signals_by_date('2026-06-26', action='BUY')

        # 按股票查询
        signals = repo.get_signals_by_symbol('000001', '2026-01-01', '2026-06-30')

        # 更新状态
        repo.update_signal_status(123, 'executed')
    """

    model = Signal

    # ==================== ISignalRepository接口实现 ====================

    def get_signals(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        signal_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取信号列表（ISignalRepository接口实现）

        Args:
            symbol: 股票代码（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            signal_type: 信号类型（可选），即action字段

        Returns:
            信号字典列表
        """
        try:
            query = self.session.query(Signal)

            if symbol:
                query = query.filter(Signal.symbol == symbol)
            if start_date:
                query = query.filter(Signal.signal_date >= start_date)
            if end_date:
                query = query.filter(Signal.signal_date <= end_date)
            if signal_type:
                query = query.filter(Signal.action == signal_type)

            signals = query.order_by(Signal.signal_date.desc()).all()
            return [self._signal_to_dict(s) for s in signals]

        except Exception as e:
            logger.error(f"Error getting signals: {e}")
            return []

    def create_signal(self, signal_data: Dict[str, Any]) -> int:
        """创建信号（ISignalRepository接口实现）

        契约（2026-08-04 修复——旧实现传 volume=/metadata= 两个模型不存在
        的字段，每条创建都 TypeError 被吞返回 0）：
        - 必填：signal_date, symbol, name, action, strategy_id
        - action_type 缺省时按 action 推导：buy→1, sell→2
        - 唯一键 (symbol, signal_date, strategy_id) 冲突 → 返回 0（幂等跳过）

        Returns:
            信号ID；冲突或失败返回 0
        """
        try:
            action = signal_data.get('action')
            action_type = signal_data.get('action_type')
            if action_type is None and action:
                action_type = {'buy': 1, 'sell': 2}.get(str(action).lower(), 0)

            # 幂等：唯一键 (symbol, signal_date, strategy_id) 已存在则跳过
            existing = (
                self.session.query(Signal.id)
                .filter(
                    Signal.symbol == signal_data.get('symbol'),
                    Signal.signal_date == signal_data.get('signal_date'),
                    Signal.strategy_id == str(signal_data.get('strategy_id')),
                )
                .first()
            )
            if existing:
                logger.debug(
                    f"Signal already exists: {signal_data.get('symbol')} "
                    f"{signal_data.get('signal_date')} {signal_data.get('strategy_id')}")
                return 0

            signal = Signal(
                symbol=signal_data.get('symbol'),
                signal_date=signal_data.get('signal_date'),
                name=signal_data.get('name') or '',
                action=action,
                action_type=action_type,
                strategy_id=str(signal_data.get('strategy_id')),
                price=signal_data.get('price'),
                confidence=signal_data.get('confidence'),
                reason=signal_data.get('reason'),
                indicators=signal_data.get('indicators'),
                status=signal_data.get('status', 'pending'),
            )
            created = self.create(signal)
            return created.id if created else 0

        except Exception as e:
            logger.error(f"Error creating signal: {e}")
            self.session.rollback()
            return 0

    def _signal_to_dict(self, signal: Signal) -> Dict[str, Any]:
        """将Signal对象转换为字典"""
        return {
            'id': signal.id,
            'symbol': signal.symbol,
            'signal_date': signal.signal_date.isoformat() if signal.signal_date else None,
            'action': signal.action,
            'strategy_id': signal.strategy_id,
            'price': signal.price,
            'volume': signal.volume,
            'confidence': signal.confidence,
            'reason': signal.reason,
            'status': signal.status,
            'metadata': signal.metadata,
            'created_at': signal.created_at.isoformat() if signal.created_at else None,
            'updated_at': signal.updated_at.isoformat() if signal.updated_at else None,
        }

    # ==================== 查询方法 ====================

    def get_signal(self, signal_id: int) -> Optional[Signal]:
        """根据ID查询信号

        Args:
            signal_id: 信号ID

        Returns:
            Signal对象，不存在返回None
        """
        return self.get_by_id(signal_id)

    def get_signals_by_date(
        self,
        signal_date: str,
        action: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Signal]:
        """查询指定日期的信号

        Args:
            signal_date: 信号日期 (YYYY-MM-DD)
            action: 操作类型筛选 (BUY/SELL/HOLD)
            status: 状态筛选 (pending/executed/rejected/expired)

        Returns:
            Signal对象列表
        """
        try:
            query = self.session.query(Signal).filter(
                Signal.signal_date == signal_date
            )

            if action:
                query = query.filter(Signal.action == action)
            if status:
                query = query.filter(Signal.status == status)

            return query.order_by(Signal.created_at.desc()).all()

        except Exception as e:
            logger.error(f"Error getting signals by date {signal_date}: {e}")
            return []

    def get_signals_by_date_range(
        self,
        start_date: str,
        end_date: str,
        action: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Signal]:
        """查询日期范围内的信号

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            action: 操作类型筛选
            status: 状态筛选

        Returns:
            Signal对象列表
        """
        try:
            query = self.session.query(Signal).filter(
                Signal.signal_date >= start_date,
                Signal.signal_date <= end_date
            )

            if action:
                query = query.filter(Signal.action == action)
            if status:
                query = query.filter(Signal.status == status)

            query = query.order_by(
                Signal.signal_date.desc(),
                Signal.created_at.desc()
            )

            if limit:
                query = query.limit(limit)

            return query.all()

        except Exception as e:
            logger.error(f"Error getting signals by date range: {e}")
            return []

    def get_signals_by_symbol(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        action: Optional[str] = None
    ) -> List[Signal]:
        """查询指定股票的信号

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            action: 操作类型筛选

        Returns:
            Signal对象列表
        """
        try:
            query = self.session.query(Signal).filter(
                Signal.symbol == symbol,
                Signal.signal_date >= start_date,
                Signal.signal_date <= end_date
            )

            if action:
                query = query.filter(Signal.action == action)

            return query.order_by(Signal.signal_date.desc()).all()

        except Exception as e:
            logger.error(f"Error getting signals for {symbol}: {e}")
            return []

    def get_signals_by_strategy(
        self,
        strategy_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Signal]:
        """查询指定策略的信号

        Args:
            strategy_id: 策略ID
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回数量限制

        Returns:
            Signal对象列表
        """
        try:
            query = self.session.query(Signal).filter(
                Signal.strategy_id == strategy_id
            )

            if start_date:
                query = query.filter(Signal.signal_date >= start_date)
            if end_date:
                query = query.filter(Signal.signal_date <= end_date)

            return query.order_by(
                Signal.signal_date.desc()
            ).limit(limit).all()

        except Exception as e:
            logger.error(f"Error getting signals for strategy {strategy_id}: {e}")
            return []

    def get_pending_signals(
        self,
        signal_date: Optional[str] = None
    ) -> List[Signal]:
        """查询待处理信号

        Args:
            signal_date: 指定日期（可选），None表示所有

        Returns:
            Signal对象列表
        """
        try:
            query = self.session.query(Signal).filter(
                Signal.status == 'pending'
            )

            if signal_date:
                query = query.filter(Signal.signal_date == signal_date)

            return query.order_by(Signal.created_at.desc()).all()

        except Exception as e:
            logger.error(f"Error getting pending signals: {e}")
            return []

    def get_latest_signal_by_symbol(
        self,
        symbol: str,
        strategy_id: Optional[str] = None
    ) -> Optional[Signal]:
        """获取股票的最新信号

        Args:
            symbol: 股票代码
            strategy_id: 策略ID（可选）

        Returns:
            Signal对象
        """
        try:
            query = self.session.query(Signal).filter(
                Signal.symbol == symbol
            )

            if strategy_id:
                query = query.filter(Signal.strategy_id == strategy_id)

            return query.order_by(Signal.signal_date.desc()).first()

        except Exception as e:
            logger.error(f"Error getting latest signal for {symbol}: {e}")
            return None

    # ==================== 创建和更新 ====================

    def batch_create_signals(self, signals: List[Signal]) -> bool:
        """批量创建信号

        Args:
            signals: Signal对象列表

        Returns:
            成功返回True
        """
        return self.create_batch(signals, commit=True)

    def update_signal_status(
        self,
        signal_id: int,
        status: str,
        reject_reason: Optional[str] = None,
        error_description: Optional[str] = None
    ) -> bool:
        """更新信号状态

        Args:
            signal_id: 信号ID
            status: 新状态 (pending/executed/rejected/expired)
            reject_reason: 拒绝原因（可选）
            error_description: 错误描述（可选）

        Returns:
            成功返回True
        """
        try:
            signal = self.get_by_id(signal_id)
            if not signal:
                logger.warning(f"Signal {signal_id} not found")
                return False

            signal.status = status
            if reject_reason:
                signal.reject_reason = reject_reason
            if error_description:
                signal.error_description = error_description

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error updating signal status: {e}")
            self.session.rollback()
            return False

    def update_signal(
        self,
        signal_id: int,
        **kwargs
    ) -> bool:
        """更新信号字段

        Args:
            signal_id: 信号ID
            **kwargs: 要更新的字段

        Returns:
            成功返回True
        """
        try:
            signal = self.get_by_id(signal_id)
            if not signal:
                return False

            for key, value in kwargs.items():
                if hasattr(signal, key):
                    setattr(signal, key, value)

            self.session.commit()
            return True

        except Exception as e:
            logger.error(f"Error updating signal {signal_id}: {e}")
            self.session.rollback()
            return False

    # ==================== 统计方法 ====================

    def count_signals_by_date(
        self,
        signal_date: str,
        action: Optional[str] = None
    ) -> int:
        """统计指定日期的信号数量

        Args:
            signal_date: 信号日期
            action: 操作类型筛选

        Returns:
            信号数量
        """
        try:
            query = self.session.query(Signal).filter(
                Signal.signal_date == signal_date
            )

            if action:
                query = query.filter(Signal.action == action)

            return query.count()

        except Exception as e:
            logger.error(f"Error counting signals: {e}")
            return 0

    def count_by_status(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, int]:
        """统计各状态的信号数量

        Args:
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            {status: count} 字典
        """
        try:
            query = self.session.query(
                Signal.status,
                func.count(Signal.id)
            )

            if start_date:
                query = query.filter(Signal.signal_date >= start_date)
            if end_date:
                query = query.filter(Signal.signal_date <= end_date)

            result = query.group_by(Signal.status).all()

            return {status: count for status, count in result}

        except Exception as e:
            logger.error(f"Error counting by status: {e}")
            return {}

    def get_signal_stats_by_strategy(
        self,
        strategy_id: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """获取策略的信号统计

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计信息字典
        """
        try:
            signals = self.get_signals_by_strategy(
                strategy_id,
                start_date,
                end_date,
                limit=10000
            )

            total = len(signals)
            buy_count = sum(1 for s in signals if s.action == 'BUY')
            sell_count = sum(1 for s in signals if s.action == 'SELL')
            hold_count = sum(1 for s in signals if s.action == 'HOLD')

            status_counts = {}
            for signal in signals:
                status_counts[signal.status] = status_counts.get(signal.status, 0) + 1

            return {
                'strategy_id': strategy_id,
                'total': total,
                'buy': buy_count,
                'sell': sell_count,
                'hold': hold_count,
                'status': status_counts
            }

        except Exception as e:
            logger.error(f"Error getting signal stats: {e}")
            return {}

    # ==================== 删除方法 ====================

    def delete_signals_by_date(self, signal_date: str) -> int:
        """删除指定日期的信号

        Args:
            signal_date: 信号日期

        Returns:
            删除的数量
        """
        try:
            count = self.session.query(Signal).filter(
                Signal.signal_date == signal_date
            ).delete()

            self.session.commit()
            return count

        except Exception as e:
            logger.error(f"Error deleting signals by date: {e}")
            self.session.rollback()
            return 0

    def get_latest_signals(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最新的信号列表

        Args:
            limit: 返回数量限制，默认10条

        Returns:
            最新信号列表，按创建时间降序排列
        """
        try:
            signals = self.session.query(Signal).order_by(
                Signal.created_at.desc()
            ).limit(limit).all()

            return [self._signal_to_dict(s) for s in signals]

        except Exception as e:
            logger.error(f"Error getting latest signals: {e}", exc_info=True)
            return []
