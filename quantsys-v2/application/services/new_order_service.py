# application/services/new_order_service.py
"""
新订单服务 - 迁移过渡层

替代旧的 order_service.py，提供相同的公共接口。

迁移策略：
  Phase 1 (当前): 作为薄包装器，委托给旧服务以保持向后兼容
  Phase 2: 逐步将旧服务逻辑迁移到领域层
  Phase 3: 完全替换旧服务
"""
from typing import Optional, Dict, List
import structlog

from application.services import order_service as _order_service

logger = structlog.get_logger(__name__)


def create_order(
    symbol: str,
    action: str,
    order_type: str,
    quantity: int,
    price: float = None,
    reason: str = None,
    signal_id: int = None,
    from_signal: bool = False,
    account_name: str = None,
) -> int:
    return _order_service.create_order(
        symbol=symbol,
        action=action,
        order_type=order_type,
        quantity=quantity,
        price=price,
        reason=reason,
        signal_id=signal_id,
        from_signal=from_signal,
        account_name=account_name,
    )


def fill_order(
    order_id: int,
    fill_price: float,
    fill_quantity: int = None,
) -> Dict:
    return _order_service.fill_order(
        order_id=order_id,
        fill_price=fill_price,
        fill_quantity=fill_quantity,
    )


def cancel_order(order_id: int) -> bool:
    return _order_service.cancel_order(order_id=order_id)


def get_order(order_id: int) -> Optional[Dict]:
    return _order_service.get_order(order_id=order_id)


def list_orders(
    symbol: str = None,
    status: str = None,
    limit: int = 50,
) -> List[Dict]:
    return _order_service.list_orders(
        symbol=symbol,
        status=status,
        limit=limit,
    )


def expire_orders() -> int:
    return _order_service.expire_orders()


def create_order_from_signal(
    signal: dict,
    symbol: str,
    order_type: str = 'limit',
) -> dict:
    return _order_service.create_order_from_signal(
        signal=signal,
        symbol=symbol,
        order_type=order_type,
    )


ORDER_STATES = _order_service.ORDER_STATES


def validate_state_transition(current_state: str, new_state: str) -> bool:
    return _order_service.validate_state_transition(current_state, new_state)


def _update_signal_tracking(signal_id: int, action: str, fill_price: float, symbol: str, perf_repo=None):
    return _order_service._update_signal_tracking(signal_id, action, fill_price, symbol, perf_repo)
