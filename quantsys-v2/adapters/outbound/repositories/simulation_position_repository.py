# adapters/outbound/repositories/simulation_position_repository.py
"""
SimulationPositionRepository - 适配 SimulationORMRepository 到 IPositionRepository 接口
"""
from typing import Optional, List
import structlog

from domain.portfolio.models.position import Position
from domain.portfolio.ports.IPositionRepository import IPositionRepository
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

logger = structlog.get_logger(__name__)


class SimulationPositionRepository(IPositionRepository):
    """基于 SimulationORMRepository 的 IPositionRepository 实现"""
    
    def __init__(self, sim_repo: Optional[SimulationORMRepository] = None):
        self.sim_repo = sim_repo or SimulationORMRepository()
    
    def get_position(
        self,
        account_name: str,
        symbol: str,
    ) -> Optional[Position]:
        """获取单只股票持仓"""
        orm_position = self.sim_repo.get_position(account_name, symbol)
        if not orm_position:
            return None
        
        return Position(
            account_name=orm_position.account_name,
            symbol=orm_position.symbol,
            shares_total=int(orm_position.shares_total or 0),
            shares_available=int(orm_position.shares_available or 0),
            avg_cost=float(orm_position.avg_cost or 0),
            current_price=float(orm_position.current_price or 0),
            market_value=float(orm_position.market_value or 0),
            unrealized_pnl=float(orm_position.unrealized_pnl or 0),
            unrealized_pnl_rate=float(orm_position.unrealized_pnl_rate or 0),
            created_at=orm_position.created_at,
            updated_at=orm_position.updated_at,
        )
    
    def get_all_positions(self, account_name: str) -> List[Position]:
        """获取账户所有持仓"""
        orm_positions = self.sim_repo.get_all_positions(account_name)
        return [
            Position(
                account_name=p.account_name,
                symbol=p.symbol,
                shares_total=int(p.shares_total or 0),
                shares_available=int(p.shares_available or 0),
                avg_cost=float(p.avg_cost or 0),
                current_price=float(p.current_price or 0),
                market_value=float(p.market_value or 0),
                unrealized_pnl=float(p.unrealized_pnl or 0),
                unrealized_pnl_rate=float(p.unrealized_pnl_rate or 0),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in orm_positions
        ]
    
    def upsert_position(
        self,
        account_name: str,
        symbol: str,
        shares_total: int,
        avg_cost: float,
        shares_available: int,
        current_price: float,
    ) -> bool:
        """创建或更新持仓"""
        return self.sim_repo.upsert_position(
            account_name=account_name,
            symbol=symbol,
            shares_total=shares_total,
            avg_cost=avg_cost,
            shares_available=shares_available,
            current_price=current_price,
            commit=True,
        )
    
    def delete_position(
        self,
        account_name: str,
        symbol: str,
    ) -> bool:
        """删除持仓（清仓时）"""
        return self.sim_repo.delete_position(
            account_name=account_name,
            symbol=symbol,
            commit=True,
        )
