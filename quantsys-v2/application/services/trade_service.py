"""
交易执行和盈亏计算服务

处理交易记录的创建、查询和持仓盈亏（P&L）计算。
通过 DataService (ds) 统一访问 PortfolioRepository 和 KlineRepository。
"""
from typing import Optional, Dict, List
from datetime import datetime
import structlog

from infrastructure.persistence.database.validators import validate_symbol, validate_positive_number
from application.services.data_service import DataService

logger = structlog.get_logger(__name__)

# 费率常量
COMMISSION_RATE = 0.0003   # 佣金费率 0.03%
STAMP_DUTY_RATE = 0.001    # 印花税率 0.1%（仅卖出收取，A股）


def create_trade_from_order(
    ds: DataService,
    order: Dict,
    fill_price: float,
    fill_quantity: int,
) -> int:
    """
    从订单创建交易记录（含费用计算）

    费用规则:
    - 佣金: 成交金额 × 0.03%（买卖双向）
    - 印花税: 成交金额 × 0.1%（仅卖出收取，A股）

    Args:
        ds: DataService 实例
        order: 订单字典（需含 symbol, name, action 等字段）
        fill_price: 成交价格
        fill_quantity: 成交数量

    Returns:
        新创建的交易记录ID
    """
    validate_positive_number(fill_price, "fill_price")
    validate_positive_number(fill_quantity, "fill_quantity")

    amount = fill_price * fill_quantity

    # 计算费用
    fee = round(amount * COMMISSION_RATE, 2)
    is_sell = order['action'] == 'sell'
    stamp_duty = round(amount * STAMP_DUTY_RATE, 2) if is_sell else 0.0

    trade_data = {
        'symbol': order['symbol'],
        'name': order['name'],
        'action': order['action'],
        'price': fill_price,
        'quantity': fill_quantity,
        'amount': round(amount, 2),
        'fee': fee,
        'stamp_duty': stamp_duty,
        'trade_date': datetime.now().strftime('%Y-%m-%d'),
        'reason': order.get('reason'),
        'order_id': order.get('id'),
    }

    trade_id = ds.portfolio.record_trade(trade_data)

    logger.info(
        f"创建交易记录: trade_id={trade_id} symbol={order['symbol']} "
        f"{order['action']} qty={fill_quantity} @ {fill_price} "
        f"amount={amount:.2f} fee={fee}+{stamp_duty}"
    )

    return trade_id


def get_trades(
    ds: DataService,
    symbol: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
) -> List[Dict]:
    """
    获取交易记录列表（支持筛选）

    Args:
        ds: DataService 实例
        symbol: 股票代码筛选（可选）
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        limit: 返回数量上限

    Returns:
        交易记录列表
    """
    if symbol:
        trades = ds.portfolio.get_trades_by_symbol(symbol, start_date, end_date)
    else:
        if not start_date:
            start_date = '2000-01-01'
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        trades = ds.portfolio.get_trades_by_date(start_date, end_date)

    return trades[:limit]


def get_trade_stats(
    ds: DataService,
    symbol: str = None,
    start_date: str = None,
    end_date: str = None,
) -> Dict:
    """
    获取交易统计信息（含盈亏计算）

    Args:
        ds: DataService 实例
        symbol: 股票代码筛选（可选）
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）

    Returns:
        {
            'total_trades': 总交易笔数,
            'total_buys': 买入笔数,
            'total_sells': 卖出笔数,
            'total_buy_amount': 买入总额,
            'total_sell_amount': 卖出总额,
            'total_commission': 总费用（佣金+印花税）,
            'gross_pnl': 毛盈亏（卖出额-买入额）,
            'net_pnl': 净盈亏（扣除费用后）
        }
    """
    stats = ds.portfolio.get_trade_stats(symbol, start_date, end_date)

    if not stats or stats.get('total_trades', 0) == 0:
        return {
            'total_trades': 0,
            'total_buys': 0,
            'total_sells': 0,
            'total_buy_amount': 0.0,
            'total_sell_amount': 0.0,
            'total_commission': 0.0,
            'gross_pnl': 0.0,
            'net_pnl': 0.0,
        }

    buy_amount = float(stats.get('total_buy_amount', 0) or 0)
    sell_amount = float(stats.get('total_sell_amount', 0) or 0)
    total_fee = float(stats.get('total_fee', 0) or 0)

    gross_pnl = round(sell_amount - buy_amount, 2)
    net_pnl = round(gross_pnl - total_fee, 2)

    return {
        'total_trades': int(stats.get('total_trades', 0)),
        'total_buys': int(stats.get('buy_trades', 0)),
        'total_sells': int(stats.get('sell_trades', 0)),
        'total_buy_amount': buy_amount,
        'total_sell_amount': sell_amount,
        'total_commission': total_fee,
        'gross_pnl': gross_pnl,
        'net_pnl': net_pnl,
    }


def get_position(
    ds: DataService,
    symbol: str,
) -> Dict:
    """
    计算指定股票的当前持仓

    基于交易历史计算持仓数量、平均成本、已实现盈亏和未实现盈亏。

    Args:
        ds: DataService 实例
        symbol: 股票代码

    Returns:
        {
            'symbol': 股票代码,
            'name': 股票名称,
            'remaining_quantity': 剩余持仓数量,
            'avg_cost': 平均成本价,
            'total_cost': 总成本,
            'latest_price': 最新价格,
            'market_value': 当前市值,
            'realized_pnl': 已实现盈亏,
            'unrealized_pnl': 未实现盈亏,
            'total_pnl': 总盈亏
        }

        如果没有持仓，remaining_quantity 为 0
    """
    validate_symbol(symbol)

    # 获取所有该股票的交易记录
    trades = ds.portfolio.get_trades_by_symbol(symbol)

    # 分别统计买入和卖出
    total_buy_qty = 0
    total_buy_amount = 0.0
    total_sell_qty = 0
    total_sell_amount = 0.0
    total_fee = 0.0
    stock_name = symbol

    for trade in trades:
        if trade.get('name'):
            stock_name = trade['name']
        qty = trade['quantity'] or 0
        amt = float(trade['amount'] or 0)
        fee = float(trade.get('fee', 0) or 0)
        stamp = float(trade.get('stamp_duty', 0) or 0)

        if trade['action'] == 'buy':
            total_buy_qty += qty
            total_buy_amount += amt
        elif trade['action'] == 'sell':
            total_sell_qty += qty
            total_sell_amount += amt

        total_fee += fee + stamp

    # 剩余持仓数量
    remaining_qty = total_buy_qty - total_sell_qty

    # 平均成本价
    if total_buy_qty > 0:
        avg_cost = round(total_buy_amount / total_buy_qty, 4)
    else:
        avg_cost = 0.0

    # 已实现盈亏（使用平均成本法计算）
    if total_sell_qty > 0 and total_buy_qty > 0:
        cost_of_sold = total_sell_qty * avg_cost
        realized_pnl = round(total_sell_amount - cost_of_sold - total_fee, 2)
    else:
        realized_pnl = 0.0

    # 获取最新价格
    latest_price = None
    try:
        kline = ds.kline.get_latest_daily_kline(symbol)
        if kline:
            latest_price = float(kline['close'])
    except Exception as e:
        logger.warning(f"获取最新价格失败 {symbol}: {e}")

    # 未实现盈亏
    unrealized_pnl = 0.0
    market_value = 0.0
    if latest_price and remaining_qty > 0:
        market_value = round(remaining_qty * latest_price, 2)
        unrealized_pnl = round(remaining_qty * (latest_price - avg_cost), 2)

    total_pnl = round(realized_pnl + unrealized_pnl, 2)

    return {
        'symbol': symbol,
        'name': stock_name,
        'remaining_quantity': remaining_qty,
        'avg_cost': avg_cost,
        'total_cost': round(remaining_qty * avg_cost, 2),
        'latest_price': latest_price,
        'market_value': market_value,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized_pnl,
        'total_pnl': total_pnl,
    }
