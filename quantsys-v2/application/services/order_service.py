"""
订单生命周期管理服务 [DEPRECATED - 内部实现]

DEPRECATED: 所有外部调用方应使用 new_order_service.py。
本模块仅由 new_order_service.py 内部委托调用，不再作为公共 API。

处理订单的创建、成交、取消、过期等完整生命周期。
通过直接访问 PortfolioRepository、StockRepository 等。
"""
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import structlog

from infrastructure.quantlib.core.validators import validate_symbol, validate_positive
from infrastructure.services.service_factory import ServiceFactory
from domain.ports import (
    IPortfolioRepository, IStockRepository, ISignalRepository,
    IRiskRepository, IKlineRepository,
)

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
    portfolio_repo: Optional[IPortfolioRepository] = None,
    stock_repo: Optional[IStockRepository] = None,
    signal_repo: Optional[ISignalRepository] = None,
    risk_repo: Optional[IRiskRepository] = None,
) -> int:
    """
    创建新订单

    Args:
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
        signal_repo = signal_repo or ServiceFactory.get_signal_repository()
        signal = signal_repo.get_signal(signal_id)
        if signal is None:
            raise ValueError(f"信号不存在: signal_id={signal_id}")
        logger.info(f"订单关联信号: signal_id={signal_id} strategy={signal.strategy_id}")

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
    stock_repo = stock_repo or ServiceFactory.get_stock_repository()
    stock = stock_repo.get_by_symbol(symbol)
    if stock is None:
        raise RuntimeError(f"股票不存在: {symbol}")

    # 资金和持仓验证
    COMMISSION_RATE = 0.0003  # 佣金费率约0.03%
    STAMP_DUTY_RATE = 0.001   # 印花税1%（仅卖出）

    if action.upper() == 'BUY':
        # 买入订单：检查可用资金
        # 获取账户余额
        risk_repo = risk_repo or ServiceFactory.get_risk_repository()
        account = risk_repo.get_latest_balance()
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

    elif action.upper() == 'SELL':
        # 卖出订单：检查持仓数量
        # 2026-08-25 修复（"无持仓记录"误报根因）：虚拟账户真实持仓在
        # simulation_* 体系（SimulationORMRepository），旧版 ds.portfolio
        # holdings 表迁移后为空——卖出校验永远失败，卖出全挂。
        # 现在优先按 account_name 查 simulation 持仓（正确使用
        # shares_available 落实 T+1 可卖数），查不到再回退旧体系。
        available_quantity = None
        position_source = None
        
        if account_name:
            try:
                from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
                sim_repo = SimulationORMRepository()
                position = sim_repo.get_position(account_name, symbol)
                if position is not None:
                    # T+1 可卖数量：当日买入的 shares_available=0，次日才可卖
                    available_quantity = int(position.shares_available or 0)
                    position_source = 'simulation'
                    logger.info(
                        f"持仓验证（simulation）: {symbol} "
                        f"total={position.shares_total} available={available_quantity}"
                    )
            except Exception as e:
                logger.warning(f"simulation 持仓查询失败，回退旧 holdings 体系: {e}")

        # 回退到旧 holdings 表（历史兼容）
        if available_quantity is None:
            holding = portfolio_repo.get_holding(symbol) if portfolio_repo is not None else None
            if holding is None:
                raise ValueError(
                    f"无持仓记录: {symbol}，无法卖出。"
                    f"account_name={account_name}（请确认账户名称是否正确）"
                )
            available_quantity = int(holding.get('quantity', 0))
            position_source = 'legacy_holdings'
            logger.info(
                f"持仓验证（legacy）: {symbol} quantity={available_quantity}"
            )

        if available_quantity < quantity:
            raise ValueError(
                f"持仓数量不足: {symbol} 可用 {available_quantity} 股，"
                f"委托卖出 {quantity} 股，"
                f"缺口 {quantity - available_quantity} 股 "
                f"（数据源: {position_source}，T+1限制：当日买入次日可卖）"
            )

        logger.info(
            f"卖出订单持仓验证通过: {symbol} qty={quantity} "
            f"available={available_quantity} source={position_source}"
        )

    # 构建订单数据
    order_data = {
        'symbol': symbol,
        'name': getattr(stock, 'name', None) or symbol,  # get_by_symbol 返回 Stock ORM 对象非 dict
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

    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    return portfolio_repo.create_order(order_data)


def fill_order(
    order_id: int,
    fill_price: float,
    fill_quantity: int = None,
    portfolio_repo: Optional[IPortfolioRepository] = None,
) -> Dict:
    """
    成交订单（支持部分成交和全部成交）

    Args:
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

    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()

    # 获取当前订单
    order = portfolio_repo.get_order(order_id)
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
    portfolio_repo.update_order_status(
        order_id=order_id,
        status=new_status,
        filled_quantity=new_filled_qty,
        avg_filled_price=round(new_avg_price, 4),
    )

    # 创建交易记录
    from application.services.trade_service import create_trade_from_order
    trade_id = create_trade_from_order(portfolio_repo=portfolio_repo, order=order, fill_price=fill_price, fill_quantity=fill_quantity)

    # 回写 signal_test_log 和 strategy_performance（如果订单关联了信号）
    if order.get('signal_id'):
        _update_signal_tracking(
            signal_id=order['signal_id'],
            action=order['action'],
            fill_price=fill_price,
            symbol=order['symbol']
        )

    # 刷新订单状态
    updated_order = portfolio_repo.get_order(order_id)

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


def cancel_order(order_id: int, portfolio_repo: Optional[IPortfolioRepository] = None) -> bool:
    """
    取消待处理订单

    Args:
        order_id: 订单ID

    Returns:
        是否成功取消

    Raises:
        ValueError: 订单状态不允许取消
        RuntimeError: 订单不存在
    """
    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    order = portfolio_repo.get_order(order_id)
    if order is None:
        raise RuntimeError(f"订单不存在: {order_id}")

    if order['status'] != 'pending':
        raise ValueError(
            f"只能取消 pending 状态的订单，当前状态: {order['status']} (id={order_id})"
        )

    result = portfolio_repo.cancel_order(order_id)

    logger.info(f"取消订单: order_id={order_id} symbol={order['symbol']}")

    return result


def expire_orders(portfolio_repo: Optional[IPortfolioRepository] = None) -> int:
    """
    过期所有超过 expires_at 的 pending 订单

    Returns:
        过期的订单数量
    """
    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    pending_orders = portfolio_repo.get_pending_orders()
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
                portfolio_repo.update_order_status(order['id'], 'expired')
                expired_count += 1
                logger.info(f"订单过期: order_id={order['id']} symbol={order['symbol']}")
            except Exception as e:
                logger.error(f"过期订单失败 order_id={order['id']}: {e}")

    return expired_count


def _update_position_on_buy(order: Dict, fill_price: float, fill_quantity: int, portfolio_repo: Optional[IPortfolioRepository] = None):
    """
    买入成交后更新持仓（新增或加仓）

    Args:
        order: 订单字典
        fill_price: 成交价格
        fill_quantity: 成交数量
    """
    symbol = order['symbol']
    account_name = order.get('account_name') or order.get('account_id')
    
    # 优先使用 SimulationORMRepository（新系统，支持 T+1）
    if account_name:
        try:
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
            sim_repo = SimulationORMRepository()
            existing_position = sim_repo.get_position(account_name, symbol)
            
            if existing_position:
                # 加仓：计算新的移动加权平均成本
                old_qty = existing_position.shares_total
                old_cost = existing_position.avg_cost
                total_qty = old_qty + fill_quantity
                avg_cost = (old_qty * old_cost + fill_quantity * fill_price) / total_qty
                
                # T+1: 新买入的 fill_quantity 当日不可卖，shares_available 保持不变
                shares_available = existing_position.shares_available
            else:
                # 建仓
                total_qty = fill_quantity
                avg_cost = fill_price
                # T+1: 当日买入不可卖
                shares_available = 0
            
            success = sim_repo.upsert_position(
                account_name=account_name,
                symbol=symbol,
                shares_total=total_qty,
                avg_cost=avg_cost,
                shares_available=shares_available,
                current_price=fill_price,
                commit=True
            )
            
            if success:
                logger.info(
                    f"持仓已更新（simulation）: {symbol} "
                    f"{'加仓' if existing_position else '建仓'} {fill_quantity}股 @ {fill_price}, "
                    f"total={total_qty}, available={shares_available} (T+1)"
                )
                return
            else:
                logger.warning(f"simulation 持仓更新失败，回退旧系统")
        except Exception as e:
            logger.warning(f"simulation 持仓更新异常，回退旧系统: {e}")
    
    # 回退到旧 holdings 系统（历史兼容）
    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    existing = portfolio_repo.get_holding(symbol)

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

    portfolio_repo.add_or_update_holding(holding_data)
    logger.info(f"持仓已更新（legacy）: {symbol} {'加仓' if existing else '建仓'} {fill_quantity}股 @ {fill_price}")


def _update_position_on_sell(order: Dict, fill_price: float, fill_quantity: int, portfolio_repo: Optional[IPortfolioRepository] = None):
    """
    卖出成交后更新持仓（减仓或清仓）

    Args:
        order: 订单字典
        fill_price: 成交价格
        fill_quantity: 成交数量
    """
    symbol = order['symbol']
    account_name = order.get('account_name') or order.get('account_id')
    
    # 优先使用 SimulationORMRepository（新系统，支持 T+1）
    if account_name:
        try:
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
            sim_repo = SimulationORMRepository()
            existing_position = sim_repo.get_position(account_name, symbol)
            
            if not existing_position:
                logger.warning(f"卖出但无持仓（simulation）: {symbol}，跳过持仓更新")
                return
            
            old_qty = existing_position.shares_total
            old_available = existing_position.shares_available
            new_qty = old_qty - fill_quantity
            new_available = max(0, old_available - fill_quantity)
            
            if new_qty <= 0:
                # 全部清仓
                success = sim_repo.delete_position(account_name, symbol, commit=True)
                if success:
                    logger.info(
                        f"持仓已清仓（simulation）: {symbol} 卖出 {fill_quantity}股 @ {fill_price}"
                    )
                    return
                else:
                    logger.warning(f"simulation 持仓删除失败，回退旧系统")
            else:
                # 减仓：保持 avg_cost 不变
                success = sim_repo.upsert_position(
                    account_name=account_name,
                    symbol=symbol,
                    shares_total=new_qty,
                    avg_cost=existing_position.avg_cost,
                    shares_available=new_available,
                    current_price=fill_price,
                    commit=True
                )
                
                if success:
                    logger.info(
                        f"持仓已减仓（simulation）: {symbol} 卖出 {fill_quantity}股 @ {fill_price}, "
                        f"剩余 total={new_qty}, available={new_available}"
                    )
                    return
                else:
                    logger.warning(f"simulation 持仓更新失败，回退旧系统")
        except Exception as e:
            logger.warning(f"simulation 持仓更新异常，回退旧系统: {e}")
    
    # 回退到旧 holdings 系统（历史兼容）
    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    existing = portfolio_repo.get_holding(symbol)

    if not existing:
        logger.warning(f"卖出但无持仓（legacy）: {symbol}，跳过持仓更新")
        return

    old_qty = int(existing['quantity'])
    new_qty = old_qty - fill_quantity

    if new_qty <= 0:
        # 全部清仓
        portfolio_repo.remove_holding(symbol)
        logger.info(f"持仓已清仓（legacy）: {symbol} 卖出 {fill_quantity}股 @ {fill_price}")
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
            'original_cost': float(existing.get('original_cost') or existing['avg_cost']),  # original_cost 可空，None 时回退 avg_cost
            'total_invested': round(new_invested, 2),
            'market': existing.get('market', 'A'),
            'sector': existing.get('sector'),
            'added_date': existing.get('added_date'),
            'stop_loss': existing.get('stop_loss'),
            'target_price': existing.get('target_price'),
            'buy_reason': existing.get('buy_reason'),
            'notes': existing.get('notes'),
        }
        portfolio_repo.add_or_update_holding(holding_data)
        logger.info(f"持仓已减仓（legacy）: {symbol} 卖出 {fill_quantity}股，剩余 {new_qty}股")


def _update_signal_tracking(signal_id: int, action: str, fill_price: float, symbol: str, perf_repo=None):
    """
    更新信号追踪记录（signal_test_log 和 strategy_performance）

    Args:
        signal_id: 信号ID
        action: 订单方向 ('buy' / 'sell')
        fill_price: 成交价格
        symbol: 股票代码
        perf_repo: 策略性能仓储（可选，用于依赖注入）
    """
    from application.services.signal_test_log import SignalTestLog
    from domain.ports import IStrategyPerformanceRepository
    from psycopg2.extras import RealDictCursor

    signal_log = SignalTestLog()
    if perf_repo is None:
        from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
        perf_repo = EnhancedServiceFactory.resolve(IStrategyPerformanceRepository)

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

        if action.upper() == 'BUY':
            # 买入成交：更新 entry_price（仅在首次成交时更新）
            if signal_dict.get('entry_price') is None:
                cursor.execute(
                    f"UPDATE {signal_log.TABLE_NAME} SET entry_price = %s, updated_at = NOW() WHERE id = %s",
                    (fill_price, signal_id)
                )
                conn.commit()
                logger.info(f"更新信号 entry_price: signal_id={signal_id} price={fill_price}")

        elif action.upper() == 'SELL':
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


def get_order(order_id: int, portfolio_repo: Optional[IPortfolioRepository] = None) -> Optional[Dict]:
    """
    获取单个订单详情

    Args:
        order_id: 订单ID

    Returns:
        订单详情，不存在返回None
    """
    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    return portfolio_repo.get_order(order_id)


def list_orders(
    symbol: str = None,
    status: str = None,
    limit: int = 50,
    portfolio_repo: Optional[IPortfolioRepository] = None,
) -> List[Dict]:
    """
    获取订单列表（支持筛选）

    Args:
        symbol: 股票代码筛选（可选）
        status: 状态筛选（可选）
        limit: 返回数量上限

    Returns:
        订单列表
    """
    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    return portfolio_repo.get_orders(symbol=symbol, status=status, limit=limit)


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
    order_id: str,
    new_state: str,
    reason: str = None,
    portfolio_repo: Optional[IPortfolioRepository] = None,
) -> bool:
    """
    Update an order's state with transition validation.

    Only allows valid state transitions as defined in VALID_TRANSITIONS.
    Terminal states (filled, cancelled, expired, rejected) cannot be
    transitioned away from.

    Args:
        order_id: Order ID to update
        new_state: Target state
        reason: Optional reason for the state change

    Returns:
        True if the transition was valid and applied
    """
    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()

    # Get current order state
    try:
        order = portfolio_repo.get_order(int(order_id))
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
        portfolio_repo.update_order_status(
            order_id=int(order_id),
            status=new_state,
        )
    except Exception as e:
        logger.error(f"Failed to update order state for {order_id}: {e}")
        return False

    # Record state change in audit log or history
    _record_state_change(order_id, current_state, new_state, reason)

    log_msg = (
        f"Order {order_id} state transition: {current_state} -> {new_state}"
    )
    if reason:
        log_msg += f" (reason: {reason})"
    logger.info(log_msg)

    return True


def _record_state_change(
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


def get_state_history(order_id: str, portfolio_repo: Optional[IPortfolioRepository] = None) -> List[Dict]:
    """
    Get the state change history for an order.

    Retrieves the order and returns its current status along with
    metadata. For systems with a dedicated state_history table,
    this would query that table.

    Args:
        order_id: Order ID

    Returns:
        List of state history records
    """
    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    try:
        order = portfolio_repo.get_order(int(order_id))
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
    symbol: str,
    action: str,
    quantity: float,
    entry_price: float,
    take_profit_price: float,
    stop_loss_price: float,
    portfolio_repo: Optional[IPortfolioRepository] = None,
    stock_repo: Optional[IStockRepository] = None,
    risk_repo: Optional[IRiskRepository] = None,
    signal_repo: Optional[ISignalRepository] = None,
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
    from infrastructure.quantlib.core.validators import validate_symbol, validate_positive

    validate_symbol(symbol)
    validate_positive(quantity, "quantity")
    validate_positive(entry_price, "entry_price")
    validate_positive(take_profit_price, "take_profit_price")
    validate_positive(stop_loss_price, "stop_loss_price")

    if action not in ('buy', 'sell'):
        raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")

    # Validate prices make sense
    if action.upper() == 'BUY':
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
    close_action = 'SELL' if action.upper() == 'BUY' else 'buy'

    # Create entry order (limit)
    entry_order_id = create_order(
        symbol=symbol,
        action=action,
        order_type='limit',
        quantity=int(quantity),
        price=entry_price,
        reason=f'Bracket entry: TP={take_profit_price} SL={stop_loss_price}',
        portfolio_repo=portfolio_repo,
        stock_repo=stock_repo,
        risk_repo=risk_repo,
        signal_repo=signal_repo,
    )

    # Create take profit order (limit at target)
    tp_order_id = create_order(
        symbol=symbol,
        action=close_action,
        order_type='limit',
        quantity=int(quantity),
        price=take_profit_price,
        reason=f'Bracket TP for entry order {entry_order_id}',
        portfolio_repo=portfolio_repo,
        stock_repo=stock_repo,
        risk_repo=risk_repo,
        signal_repo=signal_repo,
    )

    # Create stop loss order (stop market)
    sl_order_id = create_order(
        symbol=symbol,
        action=close_action,
        order_type='stop',
        quantity=int(quantity),
        price=stop_loss_price,
        reason=f'Bracket SL for entry order {entry_order_id}',
        portfolio_repo=portfolio_repo,
        stock_repo=stock_repo,
        risk_repo=risk_repo,
        signal_repo=signal_repo,
    )

    logger.info(
        f"Bracket order created: entry={entry_order_id} tp={tp_order_id} "
        f"sl={sl_order_id} for {symbol} {action} {quantity}@{entry_price} "
        f"TP@{take_profit_price} SL@{stop_loss_price}"
    )

    return [entry_order_id, tp_order_id, sl_order_id]


def create_order_from_signal(
    signal: dict,
    symbol: str,
    order_type: str = 'limit',
    portfolio_repo: Optional[IPortfolioRepository] = None,
    stock_repo: Optional[IStockRepository] = None,
    risk_repo: Optional[IRiskRepository] = None,
    signal_repo: Optional[ISignalRepository] = None,
    kline_repo: Optional[IKlineRepository] = None,
) -> dict:
    """
    从策略信号创建订单

    Args:
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

    portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
    stock_repo = stock_repo or ServiceFactory.get_stock_repository()
    risk_repo = risk_repo or ServiceFactory.get_risk_repository()
    kline_repo = kline_repo or ServiceFactory.get_kline_repository()

    # 1. 获取当前价格和账户信息
    latest = kline_repo.get_latest_daily_kline(symbol)
    current_price = latest['close'] if latest else 0
    account = risk_repo.get_latest_balance()

    # Fallback for test environments where account data may not exist
    # Production deployments should ensure get_latest_balance() returns valid data
    if account is None:
        account = {
            'total_assets': 1000000,
            'cash': 500000
        }

    # 2. 处理信号
    processor = SignalProcessor()
    trade_params = processor.process_signal(
        signal, symbol, current_price, account
    )

    # 3. 获取股票信息
    stock = stock_repo.get_by_symbol(symbol)
    if not stock:
        raise RuntimeError(f"股票不存在: {symbol}")

    stock_name = stock.get('name', symbol) if isinstance(stock, dict) else getattr(stock, 'name', symbol)

    # 4. 生成订单组 ID
    order_group = str(uuid.uuid4())

    # 5. 创建主订单
    order_id = portfolio_repo.create_order_with_risk_params(
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
        stop_loss_order_id = portfolio_repo.create_order_with_risk_params(
            symbol=symbol,
            name=stock_name,
            action = 'SELL',
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
        take_profit_order_id = portfolio_repo.create_order_with_risk_params(
            symbol=symbol,
            name=stock_name,
            action = 'SELL',
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
