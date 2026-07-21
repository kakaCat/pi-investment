"""
orders routes.
"""
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

from application.services import order_service
from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake,
    convert_keys_to_camel,
    _safe_float,
    _V2_ROOT,
    _PROJECT_ROOT_PATH,
    _LEGACY_QUANT_ROOT,
    _load_pipeline_runs,
    _save_pipeline_runs,
    _get_pipeline_run,
    _update_pipeline_run,
    acquire_task,
    release_task,
    get_running_tasks_snapshot,
    strategy_service,
    stock_pool_service,
    factor_adapter,
    scoring_service,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
    _parse_sina_a_quote,
    _parse_sina_hk_quote,
    to_camel_case,
    to_snake_case,
    get_query_params_snake_case,
    enrich_stock_data,
    signal_to_opportunity,
)

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/api/orders/list', methods=['GET'])
@handle_api_error
def get_orders_list():
    """获取订单列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    status = request.args.get('status')

    offset = (page - 1) * page_size
    orders = ds.portfolio.get_orders(limit=page_size + offset)

    if status:
        orders = [o for o in orders if o.get('status') == status]

    total = len(orders)
    orders_page = orders[offset:offset + page_size]

    return api_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': orders_page
    })


@orders_bp.route('/api/orders/detail/<int:order_id>', methods=['GET'])
@handle_api_error
def get_order_detail(order_id):
    """获取订单详情"""
    order = ds.portfolio.get_order_by_id(order_id)

    if not order:
        return jsonify({'success': False, 'error': '订单不存在'}), 404

    return api_response(order)


@orders_bp.route('/api/orders/create', methods=['POST'])
@handle_api_error
def create_order():
    """
    创建订单

    Request Body (JSON):
    {
        "symbol": "600000.SH",           // 股票代码（必需）
        "action": "buy",                 // 交易方向 buy/sell（必需）
        "orderType": "limit",            // 订单类型 limit/market/stop（必需）
        "quantity": 100,                 // 委托数量（必需）
        "price": 1450.00,                // 委托价格（限价单必需）
        "notes": "手动买入",             // 订单备注（可选）
        "signalId": 123,                 // 关联信号ID（可选，但走信号时必填）
        "fromSignal": true               // 是否来自策略信号（可选，默认false）
    }

    校验规则：
    - fromSignal=true 时，signalId 必填（策略生成的订单必须关联信号）
    - fromSignal=false 或未提供时，signalId 可选（手动创建订单）
    """
    data = request.get_json() or {}

    params = convert_keys_to_snake(data)

    required_fields = ['symbol', 'action', 'order_type', 'quantity']
    for field in required_fields:
        if field not in params:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400

    # 提取参数
    from_signal = params.get('from_signal', False)
    signal_id = params.get('signal_id')

    # 校验：如果标记为来自信号，则 signal_id 必填
    if from_signal and signal_id is None:
        return jsonify({
            'success': False,
            'error': '订单标记为来自策略信号（fromSignal=true），但未提供 signalId。策略生成的订单必须关联信号ID。'
        }), 400

    order_id = order_service.create_order(
        ds,
        symbol=params['symbol'],
        action=params['action'],
        order_type=params['order_type'],
        quantity=params['quantity'],
        price=params.get('price') or params.get('stop_price'),  # stop_price 作为 price 的备选
        reason=params.get('notes'),  # notes 映射为 reason
        signal_id=signal_id,
        from_signal=from_signal
    )

    order = ds.portfolio.get_order_by_id(order_id)

    return api_response({
        'order_id': order_id,
        'order': order
    }, message='订单创建成功')


@orders_bp.route('/api/orders/cancel/<int:order_id>', methods=['POST'])
@handle_api_error
def cancel_order(order_id):
    """取消订单"""
    success = order_service.cancel_order(ds, order_id)

    if not success:
        return jsonify({'success': False, 'error': '订单取消失败或订单不存在'}), 400

    order = ds.portfolio.get_order_by_id(order_id)

    return api_response({
        'order_id': order_id,
        'order': order
    }, message='订单已取消')


@orders_bp.route('/api/orders/fill/<int:order_id>', methods=['POST'])
@handle_api_error
def fill_order(order_id):
    """
    成交订单（支持全部成交或部分成交）

    Request Body (JSON):
    {
        "fill_price": 150.50,        // 成交价格（必需）
        "fill_quantity": 100         // 成交数量（可选，默认全部剩余）
    }

    Response:
    {
        "success": true,
        "data": {
            "order": {...},
            "trade_id": 5,
            "filled_quantity": 100,
            "is_full_fill": true
        },
        "message": "订单已成交"
    }
    """
    data = request.get_json() or {}

    fill_price = data.get('fill_price')
    if fill_price is None:
        return jsonify({'success': False, 'error': '缺少必需参数: fill_price'}), 400

    fill_quantity = data.get('fill_quantity')

    try:
        result = order_service.fill_order(ds, order_id, float(fill_price), int(fill_quantity) if fill_quantity is not None else None)
    except (ValueError, RuntimeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    return api_response(result, message='订单已成交')


@orders_bp.route('/api/orders/update/<int:order_id>', methods=['POST'])
@handle_api_error
def update_order(order_id):
    """修改订单"""
    data = request.get_json() or {}
    params = convert_keys_to_snake(data)

    order = ds.portfolio.get_order_by_id(order_id)
    if not order:
        return jsonify({'success': False, 'error': '订单不存在'}), 404

    if order.get('status') not in ['pending', 'submitted']:
        return jsonify({'success': False, 'error': '只能修改待处理或已提交的订单'}), 400

    update_fields = {}
    allowed_fields = ['quantity', 'price', 'stop_price', 'notes']
    for field in allowed_fields:
        if field in params:
            update_fields[field] = params[field]

    if not update_fields:
        return jsonify({'success': False, 'error': '没有可更新的字段'}), 400

    ds.portfolio.update_order(order_id, update_fields)

    updated_order = ds.portfolio.get_order_by_id(order_id)

    return api_response({
        'order_id': order_id,
        'order': updated_order
    }, message='订单更新成功')


@orders_bp.route('/api/trades/list', methods=['GET'])
@handle_api_error
def get_trades_list():
    """获取交易历史"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    symbol = request.args.get('symbol')
    direction = request.args.get('direction')
    keyword = request.args.get('keyword')

    offset = (page - 1) * page_size

    trades = ds.portfolio.get_trades(limit=9999)

    if symbol:
        trades = [t for t in trades if t.get('symbol') == symbol]
    if direction:
        trades = [t for t in trades if t.get('action') == direction]
    if keyword:
        kw = keyword.lower()
        trades = [t for t in trades if kw in (t.get('symbol') or '').lower() or kw in (t.get('name') or '').lower() or kw in (t.get('reason') or '').lower()]

    total = len(trades)
    trades_page = trades[offset:offset + page_size]

    return api_response({
        'total': total,
        'page': page,
        'pageSize': page_size,
        'items': trades_page
    })


@orders_bp.route('/api/portfolio/positions', methods=['GET'])
@handle_api_error
def get_portfolio_positions():
    """获取持仓列表（数据源：simulation_* 体系，account_name 必填）"""
    account_name = request.args.get('account_name')
    if not account_name:
        return jsonify({'success': False, 'error': 'account_name is required'}), 400

    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    repo = SimulationORMRepository()
    if not repo.get_account(account_name):
        return jsonify({'success': False, 'error': f'账户不存在: {account_name}'}), 404

    positions = []
    for pos in repo.get_all_positions(account_name):
        positions.append({
            'symbol': pos.symbol,
            'name': '',
            'quantity': pos.shares_total,
            'shares_available': pos.shares_available,
            'avg_cost': float(pos.avg_cost or 0),
            'current_price': float(pos.current_price or pos.avg_cost or 0),
            'total_cost': float(pos.cost or 0),
            'current_value': float(pos.market_value or 0),
            'profit_loss': float(pos.profit_total or 0),
            'profit_loss_pct': round(float(pos.profit_total_rate or 0) * 100, 2),
            'profit_today': float(pos.profit_today or 0),
        })

    return api_response({
        'positions': positions,
        'count': len(positions)
    })


@orders_bp.route('/api/portfolio/summary', methods=['GET'])
@handle_api_error
def get_portfolio_summary():
    """获取账户汇总（数据源：simulation_* 体系，account_name 必填）"""
    try:
        account_name = request.args.get('account_name')
        if not account_name:
            return jsonify({'success': False, 'error': 'account_name is required'}), 400

        from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
        repo = SimulationORMRepository()
        account = repo.get_account(account_name)
        if not account:
            return jsonify({'success': False, 'error': f'账户不存在: {account_name}'}), 404

        positions = repo.get_all_positions(account_name)
        total_cost = sum(float(p.cost or 0) for p in positions)
        market_value = sum(float(p.market_value or 0) for p in positions)
        profit_count = sum(1 for p in positions if float(p.profit_total or 0) > 0)
        loss_count = sum(1 for p in positions if float(p.profit_total or 0) < 0)
        available_cash = float(account.cash_available or 0) + float(account.cash_frozen or 0)
        unrealized_pnl = market_value - total_cost
        total_assets = available_cash + market_value
        pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0.0

        summary = {
            'totalValue': total_assets,
            'totalCost': total_cost,
            'totalMarketValue': market_value,
            'totalPnl': unrealized_pnl,
            'totalPnlPct': round(pnl_pct, 2),
            'dailyChange': 0.0,
            'positions': len(positions),
            'cash': available_cash,
            'liquidAssets': available_cash,
            'profitCount': profit_count,
            'lossCount': loss_count,
            'lastUpdated': account.updated_at.isoformat() if account.updated_at else None
        }

        return api_response(summary)

    except Exception as e:
        logger.error(f"Failed to get portfolio summary: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/portfolio/history', methods=['GET'])
@handle_api_error
def get_portfolio_history():
    """Get portfolio value history"""
    try:
        days = request.args.get('days', 30, type=int)

        if days not in [7, 30, 90]:
            days = 30

        history = ds.risk.get_history(days=days)

        if not history:
            return api_response({
                'period': f'{days}d',
                'startDate': None,
                'endDate': None,
                'history': [],
                'summary': {
                    'totalReturn': 0.0,
                    'maxDrawdown': 0.0,
                    'volatility': 0.0
                }
            })

        first_value = history[0]['total_assets']
        last_value = history[-1]['total_assets']
        total_return = ((last_value - first_value) / first_value) * 100 if first_value > 0 else 0.0

        max_drawdown = 0.0
        peak = history[0]['total_assets']
        for record in history:
            if record['total_assets'] > peak:
                peak = record['total_assets']
            drawdown = ((record['total_assets'] - peak) / peak) * 100 if peak > 0 else 0.0
            if drawdown < max_drawdown:
                max_drawdown = drawdown

        returns = [r['daily_return'] for r in history if r['daily_return'] is not None]
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
        else:
            volatility = 0.0

        formatted_history = [
            {
                'date': record['balance_date'].isoformat() if hasattr(record['balance_date'], 'isoformat') else str(record['balance_date']),
                'totalAssets': record['total_assets'],
                'dailyReturn': record['daily_return'],
                'cash': record['cash'],
                'marketValue': record['market_value']
            }
            for record in history
        ]

        response_data = {
            'period': f'{days}d',
            'startDate': formatted_history[0]['date'] if formatted_history else None,
            'endDate': formatted_history[-1]['date'] if formatted_history else None,
            'history': formatted_history,
            'summary': {
                'totalReturn': round(total_return, 2),
                'maxDrawdown': round(max_drawdown, 2),
                'volatility': round(volatility, 2)
            }
        }

        return api_response(response_data)

    except Exception as e:
        logger.error(f"Failed to get portfolio history: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/portfolio/holdings', methods=['GET'])
@handle_api_error
def get_portfolio_holdings():
    """Get current portfolio holdings with real-time prices"""
    try:
        holdings = ds.portfolio.get_all_holdings()

        if not holdings:
            return api_response({
                'holdings': [],
                'totalCount': 0,
                'totalMarketValue': 0.0,
                'totalCost': 0.0,
                'totalProfit': 0.0,
                'totalProfitPercent': 0.0
            })

        enriched_holdings = []
        total_market_value = 0.0
        total_cost = 0.0

        for holding in holdings:
            latest_kline = ds.kline.get_latest_daily_kline(holding['symbol'])

            if latest_kline is not None and not latest_kline.is_empty():
                kline_row = latest_kline.to_dicts()[0]
                current_price = float(kline_row['close'])
            else:
                current_price = holding['avg_cost']
                logger.warning(f"Price not available for {holding['symbol']}, using avg_cost")

            market_value = holding['quantity'] * current_price
            cost = holding['quantity'] * holding['avg_cost']
            profit = market_value - cost
            profit_percent = (profit / cost) * 100 if cost > 0 else 0.0

            enriched_holdings.append({
                'symbol': holding['symbol'],
                'name': holding['name'],
                'quantity': holding['quantity'],
                'avgCost': holding['avg_cost'],
                'currentPrice': current_price,
                'marketValue': market_value,
                'totalCost': cost,
                'profit': profit,
                'profitPercent': profit_percent,
                'market': holding['market'],
                'sector': holding.get('sector'),
                'addedDate': holding['added_date'].isoformat() if hasattr(holding['added_date'], 'isoformat') else str(holding['added_date'])
            })

            total_market_value += market_value
            total_cost += cost

        for holding in enriched_holdings:
            holding['weight'] = (holding['marketValue'] / total_market_value) * 100 if total_market_value > 0 else 0.0

        enriched_holdings.sort(key=lambda x: x['marketValue'], reverse=True)

        response_data = {
            'holdings': enriched_holdings,
            'totalCount': len(enriched_holdings),
            'totalMarketValue': total_market_value,
            'totalCost': total_cost,
            'totalProfit': total_market_value - total_cost,
            'totalProfitPercent': ((total_market_value - total_cost) / total_cost) * 100 if total_cost > 0 else 0.0
        }

        return api_response(response_data)

    except Exception as e:
        logger.error(f"Failed to get portfolio holdings: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@orders_bp.route('/api/portfolio/positions/<symbol>', methods=['GET'])
@handle_api_error
def get_portfolio_position_detail(symbol):
    """Get single position detail by symbol"""
    holdings = ds.portfolio.get_all_holdings()

    for holding in holdings:
        if holding['symbol'] == symbol:
            latest_kline = ds.kline.get_latest_daily_kline(symbol)
            if latest_kline is not None and not latest_kline.is_empty():
                kline_row = latest_kline.to_dicts()[0]
                current_price = float(kline_row['close'])
            else:
                current_price = holding['avg_cost']
            market_value = holding['quantity'] * current_price
            total_cost = holding['quantity'] * holding['avg_cost']
            profit = market_value - total_cost
            profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0.0

            stock_info = ds.stock.get_by_symbol(symbol)
            return api_response({
                'symbol': symbol,
                'name': stock_info['name'] if stock_info else holding.get('name', ''),
                'quantity': holding['quantity'],
                'avgCost': holding['avg_cost'],
                'currentPrice': current_price,
                'marketValue': market_value,
                'totalCost': total_cost,
                'profit': profit,
                'profitPercent': profit_pct,
                'market': holding.get('market'),
                'sector': holding.get('sector'),
            })

    return jsonify({'success': False, 'error': 'Position not found'}), 404


@orders_bp.route('/api/portfolio/allocation', methods=['GET'])
@handle_api_error
def get_portfolio_allocation():
    """Get portfolio allocation by position"""
    holdings = ds.portfolio.get_all_holdings()

    allocation = []
    total_value = 0.0
    items = []

    for holding in holdings:
        latest_kline = ds.kline.get_latest_daily_kline(holding['symbol'])
        if latest_kline is not None and not latest_kline.is_empty():
            kline_row = latest_kline.to_dicts()[0]
            current_price = float(kline_row['close'])
        else:
            current_price = holding['avg_cost']
        value = holding['quantity'] * current_price
        items.append({
            'symbol': holding['symbol'],
            'name': holding.get('name', ''),
            'value': value,
        })
        total_value += value

    for item in items:
        item['percentage'] = round((item['value'] / total_value) * 100, 2) if total_value > 0 else 0.0

    items.sort(key=lambda x: x['value'], reverse=True)
    return api_response(items)


@orders_bp.route('/api/portfolio/equity-curve', methods=['GET'])
@handle_api_error
def get_portfolio_equity_curve():
    """Get equity curve data from trade history (compatible with Express frontend)"""
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')

    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    trades = ds.portfolio.get_trades(limit=10000)
    trades = [t for t in trades if t.get('trade_date') and start_date <= str(t['trade_date']) <= end_date]

    if not trades:
        holdings = ds.portfolio.get_all_holdings()
        return api_response({
            'data': {
                'dates': [datetime.now().strftime('%Y-%m-%d')],
                'values': [sum(float(h.get('market_value', 0)) for h in holdings)],
                'holdings_count': len(holdings),
            },
            'message': 'No trade history in range — showing current holdings value',
        })

    trades.sort(key=lambda t: str(t['trade_date']))
    dates = []
    values = []
    cumulative = 0.0

    for t in trades:
        pnl = float(t.get('pnl', 0) or 0)
        cumulative += pnl
        dates.append(str(t['trade_date']))
        values.append(round(cumulative, 2))

    holdings = ds.portfolio.get_all_holdings()

    return api_response({
        'data': {
            'dates': dates,
            'values': values,
            'holdings_count': len(holdings),
        }
    })


@orders_bp.route('/api/orders/algo-execute', methods=['POST'])
@handle_api_error
def algo_execute():
    """
    算法交易执行：TWAP/VWAP拆单

    Request:
    {
      "symbol": "000001.SZ",
      "side": "buy",
      "quantity": 10000,
      "algo": "TWAP",
      "duration_minutes": 30,
      "start_time": "09:30:00"  // 可选
    }

    Response:
    {
      "success": true,
      "order_id": "algo_20260525_001",
      "symbol": "000001.SZ",
      "algo": "TWAP",
      "status": "pending",
      "parent_quantity": 10000,
      "child_orders": [
        {"time": "09:30:00", "quantity": 1000, "status": "pending"},
        {"time": "09:33:00", "quantity": 1000, "status": "pending"},
        ...
      ],
      "execution_stats": {
        "total_slices": 10,
        "avg_slice_size": 1000,
        "duration_minutes": 30,
        "interval_minutes": 3
      }
    }
    """
    try:
        data = request.get_json()

        symbol = data.get('symbol')
        side = data.get('side')
        quantity = data.get('quantity')
        algo = data.get('algo')
        duration_minutes = data.get('duration_minutes', 30)
        start_time_str = data.get('start_time', '09:30:00')

        # 参数验证
        if not all([symbol, side, quantity, algo]):
            return jsonify({
                'success': False,
                'error': '缺少必需参数: symbol, side, quantity, algo'
            }), 400

        if side not in ['buy', 'sell']:
            return jsonify({
                'success': False,
                'error': 'side 必须是 buy 或 sell'
            }), 400

        if algo not in ['TWAP', 'VWAP']:
            return jsonify({
                'success': False,
                'error': 'algo 必须是 TWAP 或 VWAP'
            }), 400

        if quantity <= 0:
            return jsonify({
                'success': False,
                'error': 'quantity 必须大于 0'
            }), 400

        if duration_minutes <= 0:
            return jsonify({
                'success': False,
                'error': 'duration_minutes 必须大于 0'
            }), 400

        # 生成订单ID
        order_id = f"algo_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

        # 解析开始时间
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'start_time 格式错误，应为 HH:MM:SS'
            }), 400

        # 生成拆单计划
        if algo == 'TWAP':
            child_orders = _generate_twap_slices(quantity, duration_minutes, start_time)
        else:  # VWAP
            child_orders = _generate_vwap_slices(quantity, duration_minutes, start_time)

        # 计算执行统计
        total_slices = len(child_orders)
        avg_slice_size = quantity / total_slices if total_slices > 0 else 0
        interval_minutes = duration_minutes / max(1, total_slices - 1) if total_slices > 1 else duration_minutes

        execution_stats = {
            'total_slices': total_slices,
            'avg_slice_size': round(avg_slice_size, 2),
            'duration_minutes': duration_minutes,
            'interval_minutes': round(interval_minutes, 2)
        }

        return api_response({
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'algo': algo,
            'status': 'pending',
            'parent_quantity': quantity,
            'child_orders': child_orders,
            'execution_stats': execution_stats
        })

    except Exception as e:
        logger.error(f"Algorithm execution failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _generate_twap_slices(quantity: int, duration_minutes: int, start_time) -> list:
    """
    生成 TWAP 拆单计划（时间加权平均）
    均匀拆分到时间段内

    Args:
        quantity: 总交易数量
        duration_minutes: 执行时长（分钟）
        start_time: 开始时间（time对象）

    Returns:
        拆单计划列表，每个元素包含 time, quantity, status
    """
    # 每3分钟一笔，计算笔数
    interval_minutes = 3
    num_slices = max(1, duration_minutes // interval_minutes)
    slice_quantity = quantity // num_slices
    remainder = quantity % num_slices

    child_orders = []
    current_time = datetime.combine(datetime.today(), start_time)

    for i in range(num_slices):
        # 将余数分配到前面的订单中
        qty = slice_quantity + (1 if i < remainder else 0)
        child_orders.append({
            'time': current_time.strftime('%H:%M:%S'),
            'quantity': qty,
            'status': 'pending'
        })
        current_time += timedelta(minutes=interval_minutes)

    return child_orders


def _generate_vwap_slices(quantity: int, duration_minutes: int, start_time) -> list:
    """
    生成 VWAP 拆单计划（成交量加权平均）
    根据历史成交量分布加权拆分

    简化版：使用典型的日内成交量分布模式
    开盘和收盘时段成交量较大（U型分布）

    Args:
        quantity: 总交易数量
        duration_minutes: 执行时长（分钟）
        start_time: 开始时间（time对象）

    Returns:
        拆单计划列表，每个元素包含 time, quantity, status
    """
    # 每3分钟一笔
    interval_minutes = 3
    num_slices = max(1, duration_minutes // interval_minutes)

    # 成交量权重分布（模拟U型分布）
    # 开盘和收盘权重高，中间时段权重低
    weights = []
    for i in range(num_slices):
        progress = i / max(1, num_slices - 1)
        # U型曲线：开盘和收盘权重高
        # 使用二次函数：weight = 1.5 - |progress - 0.5|
        weight = 1.5 - abs(progress - 0.5)
        weights.append(weight)

    # 归一化权重
    total_weight = sum(weights)
    normalized_weights = [w / total_weight for w in weights]

    # 分配数量
    child_orders = []
    current_time = datetime.combine(datetime.today(), start_time)
    allocated = 0

    for i, weight in enumerate(normalized_weights):
        if i == len(normalized_weights) - 1:
            # 最后一笔分配剩余全部，确保总量准确
            qty = quantity - allocated
        else:
            qty = int(quantity * weight)
            allocated += qty

        child_orders.append({
            'time': current_time.strftime('%H:%M:%S'),
            'quantity': qty,
            'status': 'pending'
        })
        current_time += timedelta(minutes=interval_minutes)

    return child_orders


