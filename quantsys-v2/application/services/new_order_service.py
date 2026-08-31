# application/services/new_order_service.py
"""
新订单服务 - 使用领域服务实现

替代旧的 order_service.py，提供相同的公共接口但使用新的领域层。
"""
from typing import Optional, Dict, List
import structlog

from domain.service_factory import domain_service_factory
from domain.trading.models.order import OrderSide, OrderType, OrderStatus

logger = structlog.get_logger(__name__)


def create_order(
    symbol: str,
    action: str,
    order_type: str,
    quantity: int,
    price: float = None,
    reason: str = None,
    signal_id: int = None,
    account_name: str = None,
) -> int:
    """创建新订单
    
    这是新的实现，使用领域服务。
    """
    # 转换参数
    order_side = OrderSide.BUY if action == 'buy' else OrderSide.SELL
    order_type_enum = OrderType(order_type)
    
    # 获取股票名称
    # TODO: 从 stock_repo 获取
    name = symbol
    
    order = domain_service_factory.order_service.create_order(
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
    order_id: int,
    fill_price: float,
    fill_quantity: int = None,
) -> Dict:
    """成交订单"""
    trade = domain_service_factory.order_service.fill_order(
        order_id=order_id,
        fill_price=fill_price,
        fill_quantity=fill_quantity,
    )
    
    order = domain_service_factory.order_service.get_order(order_id)
    
    return {
        'order': order.__dict__ if order else None,
        'trade_id': trade.id,
        'filled_quantity': trade.shares,
        'is_full_fill': order.status == OrderStatus.FILLED if order else False,
    }


def cancel_order(order_id: int) -> bool:
    """取消订单"""
    return domain_service_factory.order_service.cancel_order(order_id)


def get_order(order_id: int) -> Optional[Dict]:
    """获取订单"""
    order = domain_service_factory.order_service.get_order(order_id)
    return order.__dict__ if order else None


def list_orders(
    symbol: str = None,
    status: str = None,
    limit: int = 50,
) -> List[Dict]:
    """获取订单列表"""
    status_enum = OrderStatus(status) if status else None
    orders = domain_service_factory.order_service.list_orders(
        symbol=symbol,
        status=status_enum,
        limit=limit,
    )
    return [o.__dict__ for o in orders]
