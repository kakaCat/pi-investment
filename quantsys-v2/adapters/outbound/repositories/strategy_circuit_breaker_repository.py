"""
Strategy Circuit Breaker ORM Repository - 策略熔断器仓储

修复记录：2026-07-19 重建
  - 原 stub 表名错误（strategy_circuit_breakers）且未实现抽象方法 check_circuit_breaker
  - 实际表 quant.strategy_circuit_breaker（主键 strategy_name）
  - 补齐 get_state / save_state / get_all_states
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, JSON
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.persistence.orm.base import Base
from domain.ports import IStrategyCircuitBreakerRepository
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class StrategyCircuitBreakerState(Base):
    __tablename__ = 'strategy_circuit_breaker'
    __table_args__ = {'schema': 'quant'}

    strategy_name = Column(String(255), primary_key=True)
    status = Column(String(20), nullable=False, default='active')
    consecutive_losses = Column(Integer, nullable=False, default=0)
    consecutive_wins = Column(Integer, nullable=False, default=0)
    rolling_win_rate = Column(Numeric(5, 4))
    recent_trades = Column(JSON)
    reason = Column(Text)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class StrategyCircuitBreakerORMRepository(BaseORMRepository[StrategyCircuitBreakerState], IStrategyCircuitBreakerRepository):
    """ORM Repository for strategy_circuit_breaker"""
    model = StrategyCircuitBreakerState

    # ---------- 接口方法 ----------

    def check_circuit_breaker(self, strategy_id: int) -> bool:
        """接口方法：检查策略是否触发熔断（True = 可交易，False = 已熔断）"""
        state = self.get_state(str(strategy_id))
        if not state:
            return True
        return state.get('status') not in ('suspended', 'stopped')

    # ---------- 业务方法 ----------

    def get_state(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """获取策略熔断状态"""
        try:
            row = self.session.query(self.model).get(strategy_name)
            return self._to_dict(row) if row else None
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error getting circuit breaker state for {strategy_name}: {e}")
            return None

    def save_state(self, state: Dict[str, Any]) -> bool:
        """保存（插入或更新）策略熔断状态"""
        try:
            strategy_name = state.get('strategy_name')
            if not strategy_name:
                logger.error("save_state: missing strategy_name")
                return False

            row = self.session.query(self.model).get(strategy_name)
            if row is None:
                row = self.model(strategy_name=strategy_name)
                self.session.add(row)

            status = state.get('status')
            # 兼容枚举（CircuitBreakerState 是 str Enum）
            row.status = getattr(status, 'value', status) or 'active'
            row.consecutive_losses = state.get('consecutive_losses', 0)
            row.consecutive_wins = state.get('consecutive_wins', 0)
            row.rolling_win_rate = state.get('rolling_win_rate')
            row.recent_trades = state.get('recent_trades')
            row.reason = state.get('reason')
            row.updated_at = datetime.now()

            self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error saving circuit breaker state: {e}")
            self.session.rollback()
            return False

    def get_all_states(self) -> List[Dict[str, Any]]:
        """获取所有策略的熔断状态"""
        try:
            rows = self.session.query(self.model).all()
            return [self._to_dict(r) for r in rows]
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error listing circuit breaker states: {e}")
            return []

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing: {e}")
            return []

    @staticmethod
    def _to_dict(r: StrategyCircuitBreakerState) -> Dict[str, Any]:
        return {
            'strategy_name': r.strategy_name,
            'status': r.status,
            'consecutive_losses': r.consecutive_losses,
            'consecutive_wins': r.consecutive_wins,
            'rolling_win_rate': float(r.rolling_win_rate) if r.rolling_win_rate is not None else None,
            'recent_trades': r.recent_trades or [],
            'reason': r.reason,
            'updated_at': r.updated_at,
            'created_at': r.created_at.isoformat(sep=' ') if r.created_at else None,
        }


__all__ = ['StrategyCircuitBreakerORMRepository', 'StrategyCircuitBreakerState']
