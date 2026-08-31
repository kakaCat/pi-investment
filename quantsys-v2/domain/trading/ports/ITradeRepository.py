# domain/trading/ports/ITradeRepository.py
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from domain.trading.models.trade import Trade

class ITradeRepository(ABC):
    """成交记录仓储接口"""
    
    @abstractmethod
    def create_trade(self, trade: Trade) -> int:
        """创建成交记录，返回交易ID"""
        pass
    
    @abstractmethod
    def get_trade(self, trade_id: int) -> Optional[Trade]:
        """获取成交记录"""
        pass
    
    @abstractmethod
    def get_trades_by_order(self, order_id: int) -> List[Trade]:
        """按订单获取成交记录"""
        pass
    
    @abstractmethod
    def get_trades_by_symbol(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Trade]:
        """按股票获取成交记录"""
        pass
    
    @abstractmethod
    def get_trade_stats(
        self,
        account_name: Optional[str] = None,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """获取交易统计"""
        pass
