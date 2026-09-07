# domain/trading/services/order_service.py
from typing import Optional, List
from datetime import datetime, timedelta
import structlog

from domain.accounts.services.account_service import AccountService
from domain.portfolio.services.position_service import PositionService
from domain.trading.models.order import Order, OrderSide, OrderType, OrderStatus
from domain.trading.models.trade import Trade
from domain.trading.ports.IOrderRepository import IOrderRepository

logger = structlog.get_logger(__name__)

# A股交易规则
COMMISSION_RATE = 0.00025      # 佣金万2.5
COMMISSION_MIN = 5.0           # 最低5元
STAMP_DUTY_RATE = 0.0005       # 印花税(卖出)
TRANSFER_FEE_RATE = 0.00001    # 过户费

# Valid state transitions
VALID_TRANSITIONS = {
    (OrderStatus.PENDING, OrderStatus.PARTIAL): True,
    (OrderStatus.PENDING, OrderStatus.CANCELLED): True,
    (OrderStatus.PENDING, OrderStatus.EXPIRED): True,
    (OrderStatus.PENDING, OrderStatus.REJECTED): True,
    (OrderStatus.PARTIAL, OrderStatus.FILLED): True,
    (OrderStatus.PARTIAL, OrderStatus.CANCELLED): True,
    (OrderStatus.PARTIAL, OrderStatus.EXPIRED): True,
    (OrderStatus.PARTIAL, OrderStatus.REJECTED): True,
}


class OrderService:
    """订单服务 - 管理订单生命周期"""

    def __init__(
        self,
        account_service: AccountService,
        position_service: PositionService,
        order_repo: IOrderRepository,
    ):
        self.account_service = account_service
        self.position_service = position_service
        self.order_repo = order_repo

    def _validate_status_transition(
        self,
        order_id: int,
        from_status: OrderStatus,
        to_status: OrderStatus,
    ) -> None:
        """校验订单状态转换的合法性

        Args:
            order_id: 订单ID（用于错误消息）
            from_status: 当前状态
            to_status: 目标状态

        Raises:
            ValueError: 如果状态转换不合法
        """
        if from_status == to_status:
            # 允许幂等操作
            return

        if (from_status, to_status) not in VALID_TRANSITIONS:
            raise ValueError(
                f"非法状态转换: 订单 {order_id} 从 {from_status.value} "
                f"到 {to_status.value} 的转换不被允许"
            )

        logger.debug(
            f"订单状态转换: order_id={order_id} "
            f"{from_status.value} → {to_status.value}"
        )
    
    def validate_order(
        self,
        account_name: str,
        symbol: str,
        action: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
    ) -> None:
        """校验订单参数"""
        # 基础校验
        if quantity <= 0:
            raise ValueError(f"委托数量必须大于0: {quantity}")
        
        if quantity % 100 != 0:
            raise ValueError(f"A股交易数量必须是100股的整数倍: {quantity}")
        
        if order_type in (OrderType.LIMIT, OrderType.STOP) and price is None:
            raise ValueError(f"{order_type.value} 订单必须提供价格")
        
        if price is not None and price <= 0:
            raise ValueError(f"价格必须大于0: {price}")
        
        # 买入校验：资金
        if action == OrderSide.BUY:
            if price is None:
                raise ValueError("买入订单必须使用限价单")
            
            # 计算总成本
            stock_amount = price * quantity
            commission = max(stock_amount * COMMISSION_RATE, COMMISSION_MIN)
            transfer_fee = stock_amount * TRANSFER_FEE_RATE
            total_cost = stock_amount + commission + transfer_fee
            
            if not self.account_service.validate_buy_balance(account_name, total_cost):
                raise ValueError(
                    f"可用资金不足: 需要 ¥{total_cost:,.2f}, "
                    f"请检查账户 {account_name}"
                )
        
        # 卖出校验：持仓
        elif action == OrderSide.SELL:
            available_shares = self.position_service.get_available_shares(account_name, symbol)
            if available_shares < quantity:
                raise ValueError(
                    f"可卖数量不足: {symbol} 可卖 {available_shares} 股, "
                    f"委托 {quantity} 股"
                )
    
    def create_order(
        self,
        account_name: str,
        symbol: str,
        name: str,
        action: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: float,
        reason: Optional[str] = None,
        signal_id: Optional[int] = None,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
    ) -> Order:
        """创建新订单"""
        # 校验订单
        self.validate_order(account_name, symbol, action, order_type, quantity, price)
        
        # 创建订单对象
        order = Order(
            account_name=account_name,
            symbol=symbol,
            name=name,
            action=action,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            reason=reason,
            signal_id=signal_id,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            expires_at=datetime.now() + timedelta(days=7),
        )
        
        # 保存订单
        order_id = self.order_repo.create_order(order)
        order.id = order_id
        
        logger.info(
            f"订单已创建: {account_name} {symbol} "
            f"{action.value} {order_type.value} "
            f"qty={quantity} price={price}"
        )
        
        return order

    def _validate_status_transition(
        self,
        order_id: int,
        current_status: OrderStatus,
        new_status: OrderStatus
    ) -> None:
        """校验订单状态转换是否合法

        Args:
            order_id: 订单ID
            current_status: 当前状态
            new_status: 目标状态

        Raises:
            ValueError: 状态转换不合法
        """
        transition = (current_status, new_status)
        if transition not in VALID_TRANSITIONS:
            raise ValueError(
                f"不允许的状态转换: {current_status.value} -> {new_status.value} "
                f"(order_id={order_id})"
            )

    def fill_order(
        self,
        order_id: int,
        fill_price: float,
        fill_quantity: Optional[int] = None,
    ) -> Trade:
        """成交订单
        
        Args:
            order_id: 订单ID
            fill_price: 成交价格
            fill_quantity: 成交数量（None表示全部成交）
        
        Returns:
            成交记录
        """
        # 获取订单
        order = self.order_repo.get_order(order_id)
        if not order:
            raise ValueError(f"订单不存在: {order_id}")

        # 校验状态
        if order.status not in (OrderStatus.PENDING, OrderStatus.PARTIAL):
            raise ValueError(
                f"订单状态不允许成交: {order.status.value} "
                f"(order_id={order_id})"
            )

        # 计算成交数量
        remaining_qty = order.quantity - order.filled_quantity
        if fill_quantity is None:
            fill_quantity = remaining_qty

        if fill_quantity > remaining_qty:
            raise ValueError(
                f"成交数量超过剩余数量: {fill_quantity} > {remaining_qty}"
            )

        # 计算加权平均成交价
        old_filled_qty = order.filled_quantity
        old_avg_price = order.avg_filled_price

        new_filled_qty = old_filled_qty + fill_quantity
        if old_filled_qty == 0:
            new_avg_price = fill_price
        else:
            total_cost = old_filled_qty * old_avg_price + fill_quantity * fill_price
            new_avg_price = total_cost / new_filled_qty

        # 判断新状态
        if new_filled_qty >= order.quantity:
            new_status = OrderStatus.FILLED
        else:
            new_status = OrderStatus.PARTIAL

        # 校验状态转换合法性
        self._validate_status_transition(order_id, order.status, new_status)

        # 更新订单状态
        self.order_repo.update_order_status(
            order_id=order_id,
            status=new_status,
            filled_quantity=new_filled_qty,
            avg_filled_price=round(new_avg_price, 4),
        )
        
        # 计算费用
        amount = fill_price * fill_quantity
        commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
        stamp_duty = amount * STAMP_DUTY_RATE if order.action == OrderSide.SELL else 0.0
        transfer_fee = amount * TRANSFER_FEE_RATE
        
        # 计算已实现盈亏（仅卖出时）
        realized_pnl = None
        realized_pnl_rate = None
        if order.action == OrderSide.SELL:
            position = self.position_service.get_position(
                order.account_name, order.symbol
            )
            if position:
                cost_basis = fill_quantity * position.avg_cost
                realized_pnl = round(
                    amount - cost_basis - commission - stamp_duty - transfer_fee, 2
                )
                realized_pnl_rate = round(realized_pnl / cost_basis, 4) if cost_basis else 0.0
        
        # 创建成交记录
        trade = Trade(
            account_name=order.account_name,
            order_id=order_id,
            symbol=order.symbol,
            name=order.name,
            action=order.action.value,
            shares=fill_quantity,
            price=order.price,
            filled_price=fill_price,
            amount=round(amount, 2),
            commission=round(commission, 2),
            stamp_duty=round(stamp_duty, 2),
            transfer_fee=round(transfer_fee, 2),
            realized_pnl=realized_pnl,
            realized_pnl_rate=realized_pnl_rate,
            reason=order.reason,
            trade_date=datetime.now().strftime('%Y-%m-%d'),
        )

        # 计算总费用
        total_fees = commission + stamp_duty + transfer_fee

        # 更新持仓（调用领域服务）
        if order.action == OrderSide.BUY:
            self.position_service.add_shares(
                account_name=order.account_name,
                symbol=order.symbol,
                shares=fill_quantity,
                cost=fill_price
            )
        else:  # SELL
            self.position_service.reduce_shares(
                account_name=order.account_name,
                symbol=order.symbol,
                shares=fill_quantity
            )

        # 更新账户资金（调用领域服务）
        if order.action == OrderSide.BUY:
            # 买入：扣减资金
            total_cost = amount + total_fees
            self.account_service.deduct_funds(
                account_name=order.account_name,
                amount=total_cost,
                reason=f"买入 {order.symbol} {fill_quantity}股"
            )
        else:  # SELL
            # 卖出：增加资金
            net_proceeds = amount - total_fees
            self.account_service.add_funds(
                account_name=order.account_name,
                amount=net_proceeds,
                reason=f"卖出 {order.symbol} {fill_quantity}股"
            )

        logger.info(
            f"订单已成交: order_id={order_id} "
            f"{order.symbol} {order.action.value} "
            f"qty={fill_quantity} price={fill_price} "
            f"fees={total_fees:.2f}"
        )

        return trade
    
    def cancel_order(self, order_id: int) -> bool:
        """取消订单"""
        order = self.order_repo.get_order(order_id)
        if not order:
            raise ValueError(f"订单不存在: {order_id}")

        # 校验状态转换合法性
        self._validate_status_transition(order_id, order.status, OrderStatus.CANCELLED)

        return self.order_repo.cancel_order(order_id)
    
    def expire_orders(self) -> int:
        """过期所有超过 expires_at 的 pending 订单"""
        pending_orders = self.order_repo.get_pending_orders()
        now = datetime.now()
        expired_count = 0

        for order in pending_orders:
            if order.expires_at and order.expires_at < now:
                try:
                    # 校验状态转换合法性
                    self._validate_status_transition(
                        order.id, order.status, OrderStatus.EXPIRED
                    )
                    self.order_repo.update_order_status(
                        order_id=order.id,
                        status=OrderStatus.EXPIRED,
                    )
                    expired_count += 1
                    logger.info(f"订单已过期: order_id={order.id}")
                except Exception as e:
                    logger.error(f"过期订单失败 order_id={order.id}: {e}")

        return expired_count
        
        return expired_count
    
    def get_order(self, order_id: int) -> Optional[Order]:
        """获取订单详情"""
        return self.order_repo.get_order(order_id)
    
    def list_orders(
        self,
        account_name: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
    ) -> List[Order]:
        """获取订单列表"""
        return self.order_repo.get_orders(
            account_name=account_name,
            symbol=symbol,
            status=status,
            limit=limit,
        )
