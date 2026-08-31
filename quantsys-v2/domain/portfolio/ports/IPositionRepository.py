# domain/portfolio/ports/IPositionRepository.py
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.portfolio.models.position import Position

class IPositionRepository(ABC):
    """持仓仓储接口"""
    
    @abstractmethod
    def get_position(
        self,
        account_name: str,
        symbol: str,
    ) -> Optional[Position]:
        """获取单只股票持仓"""
        pass
    
    @abstractmethod
    def get_all_positions(self, account_name: str) -> List[Position]:
        """获取账户所有持仓"""
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def delete_position(
        self,
        account_name: str,
        symbol: str,
    ) -> bool:
        """删除持仓（清仓时）"""
        pass
