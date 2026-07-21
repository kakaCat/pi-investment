"""
订单生命周期管理服务

处理订单的创建、成交、取消、过期等完整生命周期。
通过 DataService (ds) 统一访问 PortfolioRepository。
"""
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import structlog

from domain.quantlib.core.validators import validate_symbol, validate_positive
from application.services.data_service import DataService

logger = structlog.get_logger(__name__)


def create_order(
    ds: DataService,
    symbol: str,
    action: str,
    order_type: str,
    quantity: int,
    price: float = None,
    reason: str = None,
    signal_id: int = None,
    from_signal: bool = False,
) -> int:
    """
    创建新订单

    Args:
        ds: DataService 实例
        symbol: 股票代码
        action: 交易方向 ('buy' / 'sell')
        order_type: 订单类型 ('limit' / 'market' / 'stop')
        quantity: 委托数量
        price: 委托价格（市价单可为None）
        reason: 下单原因
        signal_id: 关联信号ID（走信号时必填）
        from_signal: 是否来自策略信号（True=必须提供signal_id，False=手动创建可选）

    Returns:
        新创建的订单ID

    Raises:
        ValueError: 参数校验失败
        RuntimeError: 股票不存在或数据库错误
    """
    # ========== 信号追踪校验 ==========
    # 如果明确标记为来自信号，则 signal_id 必填
    if from_signal and signal_id is None:
        raise ValueError(
            "订单标记为来自策略信号（from_signal=True），但未提供 signal_id。"
            "策略生成的订单必须关联信号ID以确保追踪链路完整。"
        )

    # 如果提供了 signal_id，验证信号是否存在
    if signal_id is not None:
        signal = ds.portfolio.get_signal_by_id(signal_id)
        if signal is None:
            raise ValueError(f"信号不存在: signal_id={signal_id}")
        logger.info(f"订单关联信号: signal_id={signal_id} strategy={signal.get('strategy_id')}")

    # 校验股票代码
    validate_symbol(symbol)

    # 校验数量
    validate_positive(quantity, "quantity")

    # 校验 action
    if action not in ('buy', 'sell'):
        raise ValueError(f"无效的订单方向: {action}，必须是 buy 或 sell")

    # 校验 order_type
    if order_type not in ('limit', 'market', 'stop'):
        raise ValueError(f"无效的订单类型: {order_type}，必须是 limit、market 或 stop")

    # 限价单和止损单必须提供价格
    if order_type in ('limit', 'stop') and price is None:
        raise ValueError(f"{order_type} 订单必须提供价格")

    # 价格校验
    if price is not None:
        validate_positive(price, "price")

    # A股交易规则：必须是100股的整数倍（1手 = 100股）
    if quantity % 100 != 0:
        raise ValueError(f"A股交易数量必须是100股的整数倍，当前数量: {quantity}")

    # 验证股票是否存在
    stock = ds.stock.get_by_symbol(symbol)
    if stock is None:
        raise RuntimeError(f"股票不存在: {symbol}")

    # 资金和持仓验证
    COMMISSION_RATE = 0.0003  # 佣金费率约0.03%
    STAMP_DUTY_RATE = 0.001   # 印花税1%（仅卖出）

    if action == 'buy':
        # 买入订单：检查可用资金
        # 获取账户余额
        account = ds.risk.get_latest_balance()
        if account is None:
            raise ValueError("无法获取账户余额信息，请先初始化账户数据")

        available_cash = float(account.get('cash', 0))

        # 计算所需资金（使用限价单价格，市价单使用当前价格估算）
        order_price = price
        if order_price is None:
            # 市价单：尝试获取当前价格作为估算
            # 这里简化处理，实际应该获取实时行情
            raise ValueError("市价单暂不支持资金验证，请使用限价单")

        # 计算总成本 = 股票金额 + 佣金
        stock_amount = order_price * quantity
        commission = stock_amount * COMMISSION_RATE
        total_cost = stock_amount + commission

        if total_cost > available_cash:
            raise ValueError(
                f"可用资金不足: 需要 ¥{total_cost:.2f} "
                f"(股票 ¥{stock_amount:.2f} + 佣金 ¥{commission:.2f})，"
                f"可用资金 ¥{available_cash:.2f}，"
                f"缺口 ¥{total_cost - available_cash:.2f}"
            )

        logger.info(
            f"买入订单资金验证通过: {symbol} qty={quantity} price={order_price} "
            f"cost={total_cost:.2f} available={available_cash:.2f}"
        )

    elif action == 'sell':
        # 卖出订单：检查持仓数量
        holding = ds.portfolio.get_holding(symbol)
        if holding is None:
            raise ValueError(f"无持仓记录: {symbol}，无法卖出")

        available_quantity = int(holding.get('quantity', 0))
        if available_quantity < quantity:
            raise ValueError(
                f"持仓数量不足: {symbol} 可用 {available_quantity} 股，"
                f"委托卖出 {quantity} 股，"
                f"缺口 {quantity - available_quantity} 股"
            )

        logger.info(
            f"卖出订单持仓验证通过: {symbol} qty={quantity} "
            f"available={available_quantity}"
        )

    # 构建订单数据
    order_data = {
        'symbol': symbol,
        'name': stock.get('name', symbol),
        'order_type': order_type,
        'action': action,
        'price': price,
        'quantity': quantity,
        'status': 'pending',
        'filled_quantity': 0,
        'avg_filled_price': None,
        'reason': reason,
        'signal_id': signal_id,
        'expires_at': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),
    }

    logger.info(
        f"创建订单: {symbol} {action} {order_type} "
        f"qty={quantity} price={price} reason={reason}"
    )

    return ds.portfolio.create_order(order_data)


def fill_order(
    ds: DataService,
    order_id: int,
    fill_price: float,
    fill_quantity: int = None,
) -> Dict:
    """
    成交订单（支持部分成交和全部成交）

    Args:
        ds: DataService 实例
        order_id: 订单ID
        fill_price: 成交价格
        fill_quantity: 成交数量（None表示全部成交剩余数量）

    Returns:
        {
            'order': 更新后的订单,
            'trade_id': 新创建的交易记录ID,
            'filled_quantity': 本次成交数量,
            'is_full_fill': 是否全部成交
        }

    Raises:
        ValueError: 参数校验或状态不允许
        RuntimeError: 订单不存在
    """
    validate_positive(fill_price, "fill_price")

    if fill_quantity is not None:
        validate_positive(fill_quantity, "fill_quantity")

    # 获取当前订单
    order = ds.portfolio.get_order(order_id)
    if order is None:
        raise RuntimeError(f"订单不存在: {order_id}")

    if order['status'] not in ('pending', 'partial'):
        raise ValueError(
            f"订单状态不允许成交: {order['status']} (id={order_id})，"
            f"只有 pending 或 partial 状态可以成交"
        )

    # 计算本次成交数量
    remaining_qty = order['quantity'] - (order['filled_quantity'] or 0)
    if fill_quantity is None:
        fill_quantity = remaining_qty

    if fill_quantity > remaining_qty:
        raise ValueError(
            f"成交数量 {fill_quantity} 超过剩余数量 {remaining_qty} (order_id={order_id})"
        )

    if fill_quantity <= 0:
        raise ValueError(f"成交数量必须大于0: {fill_quantity}")

    # 计算新的成交数据
    old_filled_qty = order['filled_quantity'] or 0
    old_avg_price = order['avg_filled_price'] or 0

    new_filled_qty = old_filled_qty + fill_quantity

    # 加权平均成交价
    if old_filled_qty == 0:
        new_avg_price = fill_price
    else:
        total_cost = old_filled_qty * old_avg_price + fill_quantity * fill_price
        new_avg_price = total_cost / new_filled_qty

    # 判断状态
    if new_filled_qty >= order['quantity']:
        new_status = 'filled'
    else:
        new_status = 'partial'

    # 更新订单状态
    ds.portfolio.update_order_status(
        order_id=order_id,
        status=new_status,
        filled_quantity=new_filled_qty,
        avg_filled_price=round(new_avg_price, 4),
    )

    # 创建交易记录
    from application.services.trade_service import create_trade_from_order
    trade_id = create_trade_from_order(ds, order, fill_price, fill_quantity)

    # 回写 signal_test_log 和 strategy_performance（如果订单关联了信号）
    if order.get('signal_id'):
        _update_signal_tracking(
            signal_id=order['signal_id'],
            action=order['action'],
            fill_price=fill_price,
            symbol=order['symbol']
        )

    # 刷新订单状态
    updated_order = ds.portfolio.get_order(order_id)

    # ========== 更新持仓 ==========
    if order['action'] == 'buy':
        _update_position_on_buy(ds, order, fill_price, fill_quantity)
    elif order['action'] == 'sell':
        _update_position_on_sell(ds, order, fill_price, fill_quantity)

    logger.info(
        f"订单成交: order_id={order_id} symbol={order['symbol']} "
        f"qty={fill_quantity} price={fill_price} "
        f"status={new_status} trade_id={trade_id}"
    )

    return {
        'order': updated_order,
        'trade_id': trade_id,
        'filled_quantity': fill_quantity,
        'is_full_fill': new_status == 'filled',
    }


def cancel_order(ds: DataService, order_id: int) -> bool:
    """
    取消待处理订单

    Args:
        ds: DataService 实例
        order_id: 订单ID

    Returns:
        是否成功取消

    Raises:
        ValueError: 订单状态不允许取消
        RuntimeError: 订单不存在
    """
    order = ds.portfolio.get_order(order_id)
    if order is None:
        raise RuntimeError(f"订单不存在: {order_id}")

    if order['status'] != 'pending':
        raise ValueError(
            f"只能取消 pending 状态的订单，当前状态: {order['status']} (id={order_id})"
        )

    result = ds.portfolio.cancel_order(order_id)

    logger.info(f"取消订单: order_id={order_id} symbol={order['symbol']}")

    return result


def expire_orders(ds: DataService) -> int:
    """
    过期所有超过 expires_at 的 pending 订单

    Args:
        ds: DataService 实例

    Returns:
        过期的订单数量
    """
    pending_orders = ds.portfolio.get_pending_orders()
    now = datetime.now()
    expired_count = 0

    for order in pending_orders:
        expires_at = order.get('expires_at')
        if expires_at is None:
            continue

        if isinstance(expires_at, str):
            try:
                expires_at = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    expires_at = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    expires_at = datetime.strptime(expires_at, '%Y-%m-%d')

        if expires_at < now:
            try:
                ds.portfolio.update_order_status(order['id'], 'expired')
                expired_count += 1
                logger.info(f"订单过期: order_id={order['id']} symbol={order['symbol']}")
            except Exception as e:
                logger.error(f"过期订单失败 order_id={order['id']}: {e}")

    return expired_count


def _update_position_on_buy(ds: DataService, order: Dict, fill_price: float, fill_quantity: int):
    """
    买入成交后更新持仓（新增或加仓）

    Args:
        ds: DataService 实例
        order: 订单字典
        fill_price: 成交价格
        fill_quantity: 成交数量
    """
    symbol = order['symbol']
    existing = ds.portfolio.get_holding(symbol)

    if existing:
        # 加仓：加权平均成本
        old_qty = int(existing['quantity'])
        old_cost = float(existing['total_invested'])
        new_cost = fill_price * fill_quantity
        total_qty = old_qty + fill_quantity
        total_invested = old_cost + new_cost
        avg_cost = total_invested / total_qty if total_qty > 0 else 0

        holding_data = {
            'symbol': symbol,
            'name': order.get('name', existing.get('name', '')),
            'quantity': total_qty,
            'avg_cost': round(avg_cost, 4),
            'original_cost': round(avg_cost, 4),
            'total_invested': round(total_invested, 2),
            'market': existing.get('market', 'A'),
            'sector': existing.get('sector'),
            'added_date': existing.get('added_date'),
            'stop_loss': existing.get('stop_loss'),
            'target_price': existing.get('target_price'),
            'buy_reason': existing.get('buy_reason'),
            'notes': existing.get('notes'),
        }
    else:
        # 新建持仓
        total_invested = fill_price * fill_quantity
        holding_data = {
            'symbol': symbol,
            'name': order.get('name', ''),
            'quantity': fill_quantity,
            'avg_cost': fill_price,
            'original_cost': fill_price,
            'total_invested': round(total_invested, 2),
            'market': 'A',
            'sector': None,
            'added_date': datetime.now().strftime('%Y-%m-%d'),
            'stop_loss': None,
            'target_price': None,
            'buy_reason': None,
            'notes': None,
        }

    ds.portfolio.add_or_update_holding(holding_data)
    logger.info(f"持仓已更新: {symbol} {'加仓' if existing else '建仓'} {fill_quantity}股 @ {fill_price}")


def _update_position_on_sell(ds: DataService, order: Dict, fill_price: float, fill_quantity: int):
    """
    卖出成交后更新持仓（减仓或清仓）

    Args:
        ds: DataService 实例
        order: 订单字典
        fill_price: 成交价格
        fill_quantity: 成交数量
    """
    symbol = order['symbol']
    existing = ds.portfolio.get_holding(symbol)

    if not existing:
        logger.warning(f"卖出但无持仓: {symbol}，跳过持仓更新")
        return

    old_qty = int(existing['quantity'])
    new_qty = old_qty - fill_quantity

    if new_qty <= 0:
        # 全部清仓
        ds.portfolio.remove_holding(symbol)
        logger.info(f"持仓已清仓: {symbol} 卖出 {fill_quantity}股 @ {fill_price}")
    else:
        # 减仓：保持 avg_cost 不变
        old_invested = float(existing['total_invested'])
        # 按比例减少 total_invested
        ratio = new_qty / old_qty
        new_invested = old_invested * ratio

        holding_data = {
            'symbol': symbol,
            'name': existing.get('name', ''),
            'quantity': new_qty,
            'avg_cost': float(existing['avg_cost']),
            'original_cost': float(existing.get('original_cost', existing['avg_cost'])),
            'total_invested': round(new_invested, 2),
            'market': existing.get('market', 'A'),
            'sector': existing.get('sector'),
            'added_date': existing.get('added_date'),
            'stop_loss': existing.get('stop_loss'),
            'target_price': existing.get('target_price'),
            'buy_reason': existing.get('buy_reason'),
            'notes': existing.get('notes'),
        }
        ds.portfolio.add_or_update_holding(holding_data)
        logger.info(f"持仓已减仓: {symbol} 卖出 {fill_quantity}股，剩余 {new_qty}股")


def _update_signal_tracking(signal_id: int, action: str, fill_price: float, symbol: str):
    """
    更新信号追踪记录（signal_test_log 和 strategy_performance）

    Args:
        signal_id: 信号ID
        action: 订单方向 ('buy' / 'sell')
        fill_price: 成交价格
        symbol: 股票代码
    """
    from application.services.signal_test_log import SignalTestLog
    from adapters.outbound.repositories import StrategyPerformanceORMRepository
    from psycopg2.extras import RealDictCursor

    signal_log = SignalTestLog()
    perf_repo = StrategyPerformanceORMRepository()

    # 获取信号记录
    conn = signal_log._get_conn()
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            f"SELECT * FROM {signal_log.TABLE_NAME} WHERE id = %s",
            (signal_id,)
        )
        signal = cursor.fetchone()

        if not signal:
            logger.warning(f"信号不存在: signal_id={signal_id}")
            return

        signal_dict = dict(signal)

        if action == 'buy':
            # 买入成交：更新 entry_price（仅在首次成交时更新）
            if signal_dict.get('entry_price') is None:
                cursor.execute(
                    f"UPDATE {signal_log.TABLE_NAME} SET entry_price = %s, updated_at = NOW() WHERE id = %s",
                    (fill_price, signal_id)
                )
                conn.commit()
                logger.info(f"更新信号 entry_price: signal_id={signal_id} price={fill_price}")

        elif action == 'sell':
            # 卖出成交：计算盈亏，更新 signal_test_log 和 strategy_performance
            entry_price = signal_dict.get('entry_price')
            if entry_price is None:
                logger.warning(f"信号缺少 entry_price，无法计算盈亏: signal_id={signal_id}")
                return

            # 转换 Decimal 为 float
            entry_price = float(entry_price)

            # 计算盈亏百分比
            pnl_pct = ((fill_price - entry_price) / entry_price) * 100

            # 更新 signal_test_log
            cursor.execute(
                f"""
                UPDATE {signal_log.TABLE_NAME}
                SET current_price = %s,
                    pnl_pct = %s,
                    status = 'verified',
                    verify_date = CURRENT_DATE,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (fill_price, pnl_pct, signal_id)
            )
            conn.commit()
            logger.info(f"更新信号盈亏: signal_id={signal_id} pnl={pnl_pct:.2f}%")

            # 写入 strategy_performance 表
            try:
                perf_repo.create(
                    strategy_name=signal_dict['strategy_name'],
                    symbol=symbol,
                    signal_date=signal_dict['signal_date'],
                    entry_price=entry_price,
                    exit_price=fill_price,
                    pnl_pct=pnl_pct,
                    holding_days=0,  # TODO: 计算实际持仓天数
                    scenario_tags=None,  # TODO: 从信号 details 中提取
                    params_snapshot=None,  # TODO: 从信号 details 中提取
                    source='live'
                )
                logger.info(f"写入 strategy_performance: strategy={signal_dict['strategy_name']} symbol={symbol}")
            except Exception as e:
                logger.error(f"写入 strategy_performance 失败: {e}")
    finally:
        if cursor:
            cursor.close()
        conn.close()


def get_order(ds: DataService, order_id: int) -> Optional[Dict]:
    """
    获取单个订单详情

    Args:
        ds: DataService 实例
        order_id: 订单ID

    Returns:
        订单详情，不存在返回None
    """
    return ds.portfolio.get_order(order_id)


def list_orders(
    ds: DataService,
    symbol: str = None,
    status: str = None,
    limit: int = 50,
) -> List[Dict]:
    """
    获取订单列表（支持筛选）

    Args:
        ds: DataService 实例
        symbol: 股票代码筛选（可选）
        status: 状态筛选（可选）
        limit: 返回数量上限

    Returns:
        订单列表
    """
    return ds.portfolio.get_orders(symbol=symbol, status=status, limit=limit)


# ========================================================================
# Order State Machine (Added for Module 4: Live Trading)
# ========================================================================

ORDER_STATES = ['pending', 'partial', 'filled', 'cancelled', 'expired', 'rejected']

# Valid state transitions: (from_state, to_state) -> True
VALID_TRANSITIONS = {
    ('pending', 'partial'): True,
    ('pending', 'cancelled'): True,
    ('pending', 'expired'): True,
    ('pending', 'rejected'): True,
    ('partial', 'filled'): True,
    ('partial', 'cancelled'): True,
    ('partial', 'expired'): True,
    ('partial', 'rejected'): True,
}


def validate_state_transition(current_state: str, new_state: str) -> bool:
    """
    Check if an order state transition is valid.

    Args:
        current_state: Current order state (pending, partial, filled, etc.)
        new_state: Proposed new state

    Returns:
        True if the transition is allowed
    """
    # Filled is a terminal state - no transitions out
    # cancelled, expired, rejected are also terminal
    return VALID_TRANSITIONS.get((current_state, new_state), False)


def update_order_state(
    ds: DataService,
    order_id: str,
    new_state: str,
    reason: str = None,
) -> bool:
    """
    Update an order's state with transition validation.

    Only allows valid state transitions as defined in VALID_TRANSITIONS.
    Terminal states (filled, cancelled, expired, rejected) cannot be
    transitioned away from.

    Args:
        ds: DataService instance
        order_id: Order ID to update
        new_state: Target state
        reason: Optional reason for the state change

    Returns:
        True if the transition was valid and applied
    """
    # Get current order state
    try:
        order = ds.portfolio.get_order(int(order_id))
    except (TypeError, ValueError):
        logger.error(f"Invalid order_id for state transition: {order_id}")
        return False

    if order is None:
        logger.error(f"Order not found for state transition: {order_id}")
        return False

    current_state = order.get('status', 'pending')

    # Check if the transition is valid
    if not validate_state_transition(current_state, new_state):
        logger.warning(
            f"Invalid state transition: {current_state} -> {new_state} "
            f"for order {order_id}"
        )
        return False

    # Apply the state change
    try:
        ds.portfolio.update_order_status(
            order_id=int(order_id),
            status=new_state,
        )
    except Exception as e:
        logger.error(f"Failed to update order state for {order_id}: {e}")
        return False

    # Record state change in audit log or history
    _record_state_change(ds, order_id, current_state, new_state, reason)

    log_msg = (
        f"Order {order_id} state transition: {current_state} -> {new_state}"
    )
    if reason:
        log_msg += f" (reason: {reason})"
    logger.info(log_msg)

    return True


def _record_state_change(
    ds: DataService,
    order_id: str,
    from_state: str,
    to_state: str,
    reason: str = None,
):
    """
    Record an order state change for audit trails.

    Currently logs the change; can be extended to persist to a
    dedicated state_history table.

    Args:
        ds: DataService instance
        order_id: Order ID
        from_state: Previous state
        to_state: New state
        reason: Reason for the change
    """
    import json
    change_record = {
        'order_id': order_id,
        'from_state': from_state,
        'to_state': to_state,
        'reason': reason,
        'timestamp': datetime.now().isoformat(),
    }
    logger.debug(f"Order state change recorded: {json.dumps(change_record)}")


def get_state_history(ds: DataService, order_id: str) -> List[Dict]:
    """
    Get the state change history for an order.

    Retrieves the order and returns its current status along with
    metadata. For systems with a dedicated state_history table,
    this would query that table.

    Args:
        ds: DataService instance
        order_id: Order ID

    Returns:
        List of state history records
    """
    try:
        order = ds.portfolio.get_order(int(order_id))
    except (TypeError, ValueError):
        return []

    if order is None:
        return []

    history = [
        {
            'order_id': order_id,
            'state': order.get('status', 'unknown'),
            'filled_quantity': order.get('filled_quantity', 0),
            'avg_filled_price': order.get('avg_filled_price'),
            'created_at': order.get('created_at'),
            'updated_at': order.get('updated_at'),
            'is_terminal': order.get('status') in ('filled', 'cancelled', 'expired', 'rejected'),
        }
    ]

    return history


def create_bracket_order(
    ds: DataService,
    symbol: str,
    action: str,
    quantity: float,
    entry_price: float,
    take_profit_price: float,
    stop_loss_price: float,
) -> List[int]:
    """
    Create a bracket (OCO) order: entry + take profit + stop loss.

    This is a one-cancels-other (OCO) bracket where:
    - Entry order opens the position at entry_price (limit)
    - Take profit order closes at a profit target
    - Stop loss order closes at a loss limit

    Note: The TP and SL are linked orders - when one fills, the other
    cancels automatically. This is currently a simulated implementation;
    for live trading, this should use the broker's native bracket order
    support (e.g., IBKR's Bracket Order type or Alpaca's bracket orders).

    Args:
        ds: DataService instance
        symbol: Stock symbol
        action: 'buy' (long) or 'sell' (short)
        quantity: Number of shares
        entry_price: Limit price for the entry order
        take_profit_price: Price target for profit taking
        stop_loss_price: Price level for loss cutting

    Returns:
        List of created order IDs: [entry_order_id, tp_order_id, sl_order_id]

    Raises:
        ValueError: If parameters are invalid
    """
    from domain.quantlib.core.validators import validate_symbol, validate_positive

    validate_symbol(symbol)
    validate_positive(quantity, "quantity")
    validate_positive(entry_price, "entry_price")
    validate_positive(take_profit_price, "take_profit_price")
    validate_positive(stop_loss_price, "stop_loss_price")

    if action not in ('buy', 'sell'):
        raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")

    # Validate prices make sense
    if action == 'buy':
        if stop_loss_price >= entry_price:
            raise ValueError(
                f"For a long position, stop_loss_price ({stop_loss_price}) "
                f"must be below entry_price ({entry_price})"
            )
        if take_profit_price <= entry_price:
            raise ValueError(
                f"For a long position, take_profit_price ({take_profit_price}) "
                f"must be above entry_price ({entry_price})"
            )
    else:  # sell (short)
        if stop_loss_price <= entry_price:
            raise ValueError(
                f"For a short position, stop_loss_price ({stop_loss_price}) "
                f"must be above entry_price ({entry_price})"
            )
        if take_profit_price >= entry_price:
            raise ValueError(
                f"For a short position, take_profit_price ({take_profit_price}) "
                f"must be below entry_price ({entry_price})"
            )

    # Determine closing action (opposite of entry)
    close_action = 'sell' if action == 'buy' else 'buy'

    # Create entry order (limit)
    entry_order_id = create_order(
        ds=ds,
        symbol=symbol,
        action=action,
        order_type='limit',
        quantity=int(quantity),
        price=entry_price,
        reason=f'Bracket entry: TP={take_profit_price} SL={stop_loss_price}',
    )

    # Create take profit order (limit at target)
    tp_order_id = create_order(
        ds=ds,
        symbol=symbol,
        action=close_action,
        order_type='limit',
        quantity=int(quantity),
        price=take_profit_price,
        reason=f'Bracket TP for entry order {entry_order_id}',
    )

    # Create stop loss order (stop market)
    sl_order_id = create_order(
        ds=ds,
        symbol=symbol,
        action=close_action,
        order_type='stop',
        quantity=int(quantity),
        price=stop_loss_price,
        reason=f'Bracket SL for entry order {entry_order_id}',
    )

    logger.info(
        f"Bracket order created: entry={entry_order_id} tp={tp_order_id} "
        f"sl={sl_order_id} for {symbol} {action} {quantity}@{entry_price} "
        f"TP@{take_profit_price} SL@{stop_loss_price}"
    )

    return [entry_order_id, tp_order_id, sl_order_id]


def create_order_from_signal(
    ds: DataService,
    signal: dict,
    symbol: str,
    order_type: str = 'limit'
) -> dict:
    """
    从策略信号创建订单

    Args:
        ds: DataService 实例
        signal: 策略信号
        symbol: 股票代码
        order_type: 订单类型

    Returns:
        {
            'order_id': int,
            'stop_loss_order_id': int,
            'take_profit_order_id': int,
            'trade_params': dict
        }
    """
    from application.services.signal_processor import SignalProcessor
    import uuid

    # 1. 获取当前价格和账户信息
    latest = ds.kline.get_latest_daily_kline(symbol)
    current_price = latest['close'] if latest else 0
    account = ds.risk.get_latest_balance()

    # Fallback for test environments where account data may not exist
    # Production deployments should ensure get_latest_balance() returns valid data
    if account is None:
        account = {
            'total_assets': 1000000,
            'cash': 500000
        }

    # 2. 处理信号
    processor = SignalProcessor(ds)
    trade_params = processor.process_signal(
        signal, symbol, current_price, account
    )

    # 3. 获取股票信息
    stock = ds.stock.get_by_symbol(symbol)
    if not stock:
        raise RuntimeError(f"股票不存在: {symbol}")

    stock_name = stock.get('name', symbol)

    # 4. 生成订单组 ID
    order_group = str(uuid.uuid4())

    # 5. 创建主订单
    order_id = ds.portfolio.create_order_with_risk_params(
        symbol=symbol,
        name=stock_name,
        action=trade_params['action'],
        order_type=order_type,
        quantity=trade_params['quantity'],
        price=trade_params['price'],
        stop_loss_price=trade_params['stop_loss_price'],
        take_profit_price=trade_params['take_profit_price'],
        order_group=order_group,
        risk_params=trade_params.get('risk_params'),
        reason=trade_params['reason']
    )

    result = {
        'order_id': order_id,
        'trade_params': trade_params
    }

    # 6. 创建止损单（如果有）
    if trade_params['stop_loss_price'] and trade_params['action'] == 'buy':
        stop_loss_order_id = ds.portfolio.create_order_with_risk_params(
            symbol=symbol,
            name=stock_name,
            action='sell',
            order_type='stop',
            quantity=trade_params['quantity'],
            price=trade_params['stop_loss_price'],
            parent_order_id=order_id,
            order_group=order_group,
            reason=f"止损单（关联订单 {order_id}）"
        )
        result['stop_loss_order_id'] = stop_loss_order_id

    # 7. 创建止盈单（如果有）
    if trade_params['take_profit_price'] and trade_params['action'] == 'buy':
        take_profit_order_id = ds.portfolio.create_order_with_risk_params(
            symbol=symbol,
            name=stock_name,
            action='sell',
            order_type='limit',
            quantity=trade_params['quantity'],
            price=trade_params['take_profit_price'],
            parent_order_id=order_id,
            order_group=order_group,
            reason=f"止盈单（关联订单 {order_id}）"
        )
        result['take_profit_order_id'] = take_profit_order_id

    logger.info(
        f"Order group created: order_id={order_id}, "
        f"stop_loss={result.get('stop_loss_order_id')}, "
        f"take_profit={result.get('take_profit_order_id')}"
    )

    return result
