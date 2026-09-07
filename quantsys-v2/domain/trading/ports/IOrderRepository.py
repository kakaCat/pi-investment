# domain/trading/ports/IOrderRepository.py
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.trading.models.order import Order, OrderStatus

class IOrderRepository(ABC):
    """订单仓储接口 - 定义订单数据访问契约"""
    
    @abstractmethod
    def get_order(self, order_id: int) -> Optional[Order]:
        """获取订单"""
        pass
    
    @abstractmethod
    def get_orders(
        self,
        account_name: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
    ) -> List[Order]:
        """获取订单列表"""
        pass
    
    @abstractmethod
    def get_pending_orders(self, account_name: Optional[str] = None) -> List[Order]:
        """获取待处理订单"""
        pass
    
    @abstractmethod
    def create_order(self, order: Order) -> int:
        """创建订单，返回订单ID"""
        pass
    
    @abstractmethod
    def update_order_status(
        self,
        order_id: int,
        status: OrderStatus,
        filled_quantity: Optional[int] = None,
        avg_filled_price: Optional[float] = None,
    ) -> bool:
        """更新订单状态"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: int) -> bool:
        """取消订单"""
        pass
