# domain/legacy/legacy_order_adapter.py
"""
Legacy Order Adapter - 适配旧的 order_service.py 到新的 OrderService

提供向后兼容，允许旧代码逐步迁移到新的领域服务。
"""
from typing import Optional, Dict, List
import structlog

from domain.trading.services.order_service import OrderService
from domain.trading.models.order import OrderSide, OrderType

logger = structlog.get_logger(__name__)


class LegacyOrderAdapter:
    """旧版订单接口适配器
    
    将旧的函数式接口适配到新的 OrderService 类接口。
    """
    
    def __init__(self, order_service: OrderService):
        self.order_service = order_service
    
    def create_order(
        self,
        symbol: str,
        action: str,
        order_type: str,
        quantity: int,
        price: float = None,
        reason: str = None,
        signal_id: int = None,
        account_name: str = None,
    ) -> int:
        """创建订单（兼容旧接口）
        
        Args:
            symbol: 股票代码
            action: 'buy' or 'sell'
            order_type: 'limit', 'market', or 'stop'
            quantity: 数量
            price: 价格
            reason: 原因
            signal_id: 信号ID
            account_name: 账户名称
            
        Returns:
            订单ID
        """
        # 转换参数
        order_side = OrderSide.BUY if action == 'buy' else OrderSide.SELL
        order_type_enum = OrderType(order_type)
        
        # 获取股票名称（需要从 stock_repo 获取）
        # TODO: 注入 stock_repo
        name = symbol  # 临时使用 symbol 作为 name
        
        order = self.order_service.create_order(
            account_name=account_name or "default",
            symbol=symbol,
            name=name,
            action=order_side,
            order_type=order_type_enum,
            quantity=quantity,
            price=price,
            reason=reason,
            signal_id=signal_id,
        )
        
        return order.id
    
    def fill_order(
        self,
        order_id: int,
        fill_price: float,
        fill_quantity: int = None,
    ) -> Dict:
        """成交订单（兼容旧接口）
        
        Returns:
            {
                'order': 更新后的订单,
                'trade_id': 成交记录ID,
                'filled_quantity': 成交数量,
                'is_full_fill': 是否全部成交,
            }
        """
        trade = self.order_service.fill_order(
            order_id=order_id,
            fill_price=fill_price,
            fill_quantity=fill_quantity,
        )
        
        order = self.order_service.get_order(order_id)
        
        return {
            'order': order.__dict__ if order else None,
            'trade_id': trade.id,
            'filled_quantity': trade.shares,
            'is_full_fill': order.status.value == 'filled' if order else False,
        }
    
    def cancel_order(self, order_id: int) -> bool:
        """取消订单（兼容旧接口）"""
        return self.order_service.cancel_order(order_id)
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """获取订单（兼容旧接口）"""
        order = self.order_service.get_order(order_id)
        return order.__dict__ if order else None
    
    def list_orders(
        self,
        symbol: str = None,
        status: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        """获取订单列表（兼容旧接口）"""
        from domain.trading.models.order import OrderStatus
        
        status_enum = OrderStatus(status) if status else None
        orders = self.order_service.list_orders(
            symbol=symbol,
            status=status_enum,
            limit=limit,
        )
        return [o.__dict__ for o in orders]
