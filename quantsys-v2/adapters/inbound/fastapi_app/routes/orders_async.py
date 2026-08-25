"""订单/交易/投资组合 API - FastAPI 版（从 Flask orders.py 迁移，响应契约保持一致）

orders.py 同时承载 orders CRUD、trades/list 和 portfolio 端点。
复用同一 ds 单例与 order_service，原始 SQL 与 kline 逻辑与 Flask 完全一致。
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.shared.services import order_service
from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error, convert_keys_to_snake,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Orders/Portfolio - 订单与组合"])


def _generate_twap_slices(quantity: int, duration_minutes: int, start_time) -> list:
    """生成 TWAP 拆单计划（时间加权平均），与 Flask orders.py 一致。"""
    interval_minutes = 3
    num_slices = max(1, duration_minutes // interval_minutes)
    slice_quantity = quantity // num_slices
    remainder = quantity % num_slices
    child_orders = []
    current_time = datetime.combine(datetime.today(), start_time)
    for i in range(num_slices):
        qty = slice_quantity + (1 if i < remainder else 0)
        child_orders.append({'time': current_time.strftime('%H:%M:%S'), 'quantity': qty, 'status': 'pending'})
        current_time += timedelta(minutes=interval_minutes)
    return child_orders


def _generate_vwap_slices(quantity: int, duration_minutes: int, start_time) -> list:
    """生成 VWAP 拆单计划（成交量加权，U型分布），与 Flask orders.py 一致。"""
    interval_minutes = 3
    num_slices = max(1, duration_minutes // interval_minutes)
    weights = []
    for i in range(num_slices):
        progress = i / max(1, num_slices - 1)
        weight = 1.5 - abs(progress - 0.5)
        weights.append(weight)
    total_weight = sum(weights)
    normalized_weights = [w / total_weight for w in weights]
    child_orders = []
    current_time = datetime.combine(datetime.today(), start_time)
    allocated = 0
    for i, weight in enumerate(normalized_weights):
        if i == len(normalized_weights) - 1:
            qty = quantity - allocated
        else:
            qty = int(quantity * weight)
            allocated += qty
        child_orders.append({'time': current_time.strftime('%H:%M:%S'), 'quantity': qty, 'status': 'pending'})
        current_time += timedelta(minutes=interval_minutes)
    return child_orders


@router.post('/api/orders/algo-execute')
@handle_api_error
def algo_execute(payload: Optional[Dict[str, Any]] = Body(None)):
    """算法交易执行：TWAP/VWAP拆单（与 Flask orders.py 一致）"""
    try:
        data = payload or {}
        symbol = data.get('symbol')
        side = data.get('side')
        quantity = data.get('quantity')
        algo = data.get('algo')
        duration_minutes = data.get('duration_minutes', 30)
        start_time_str = data.get('start_time', '09:30:00')

        if not all([symbol, side, quantity, algo]):
            return error_response({'success': False, 'error': '缺少必需参数: symbol, side, quantity, algo'}, 400)
        if side not in ['buy', 'sell']:
            return error_response({'success': False, 'error': 'side 必须是 buy 或 sell'}, 400)
        if algo not in ['TWAP', 'VWAP']:
            return error_response({'success': False, 'error': 'algo 必须是 TWAP 或 VWAP'}, 400)
        if quantity <= 0:
            return error_response({'success': False, 'error': 'quantity 必须大于 0'}, 400)
        if duration_minutes <= 0:
            return error_response({'success': False, 'error': 'duration_minutes 必须大于 0'}, 400)

        order_id = f"algo_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
        except ValueError:
            return error_response({'success': False, 'error': 'start_time 格式错误，应为 HH:MM:SS'}, 400)

        if algo == 'TWAP':
            child_orders = _generate_twap_slices(quantity, duration_minutes, start_time)
        else:
            child_orders = _generate_vwap_slices(quantity, duration_minutes, start_time)

        total_slices = len(child_orders)
        avg_slice_size = quantity / total_slices if total_slices > 0 else 0
        interval_minutes = duration_minutes / max(1, total_slices - 1) if total_slices > 1 else duration_minutes
        execution_stats = {
            'total_slices': total_slices,
            'avg_slice_size': round(avg_slice_size, 2),
            'duration_minutes': duration_minutes,
            'interval_minutes': round(interval_minutes, 2),
        }
        return api_response({
            'order_id': order_id, 'symbol': symbol, 'side': side, 'algo': algo,
            'status': 'pending', 'parent_quantity': quantity,
            'child_orders': child_orders, 'execution_stats': execution_stats,
        })
    except Exception as e:
        logger.error(f"Algorithm execution failed: {str(e)}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)



# ============ Orders ============

@router.get('/api/orders/list')
@handle_api_error
def get_orders_list(page: int = Query(1), pageSize: int = Query(20), status: Optional[str] = Query(None)):
    offset = (page - 1) * pageSize
    orders = ds.portfolio.get_orders(limit=pageSize + offset)
    if status:
        orders = [o for o in orders if o.get('status') == status]
    total = len(orders)
    orders_page = orders[offset:offset + pageSize]
    return api_response({'total': total, 'page': page, 'page_size': pageSize, 'items': orders_page})


@router.get('/api/orders/detail/{order_id}')
@handle_api_error
def get_order_detail(order_id: int):
    order = ds.portfolio.get_order_by_id(order_id)
    if not order:
        return error_response({'success': False, 'error': '订单不存在'}, 404)
    return api_response(order)


@router.post('/api/orders/create')
@handle_api_error
def create_order(payload: Optional[Dict[str, Any]] = Body(None)):
    """
    ⚠️ DEPRECATED: 此 API 已废弃，请使用新 API
    
    新 API: POST /api/simulation/accounts/{account_name}/trade
    
    废弃原因:
    - account_name 丢失（保存为 null）
    - 使用旧 quant.orders 表（已归档）
    - 持仓更新回退到旧系统
    - T+1 规则失效
    
    废弃日期: 2026-08-25
    下线日期: 2026-09-25（1个月后）
    迁移指南: https://github.com/kakaCat/pi-investment/blob/main/agent-dh/docs/guides/order-api-guide.md
    """
    logger.warning(
        "⚠️ DEPRECATED API called: /api/orders/create. "
        "Please migrate to /api/simulation/accounts/{account_name}/trade"
    )
    
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=410,  # 410 Gone
        content={
            'success': False,
            'error': '此 API 已废弃',
            'deprecated_at': '2026-08-25',
            'sunset_date': '2026-09-25',
            'reason': 'account_name 丢失、使用旧表、T+1 规则失效',
            'migration_guide': 'https://github.com/kakaCat/pi-investment/blob/main/agent-dh/docs/guides/order-api-guide.md',
            'new_api': {
                'method': 'POST',
                'path': '/api/simulation/accounts/{account_name}/trade',
                'example': {
                    'url': '/api/simulation/accounts/agent_virtual/trade',
                    'body': {
                        'action': 'buy',
                        'symbol': '000001',
                        'shares': 200,
                        'price_limit': 12.50,
                        'reason': '买入理由'
                    }
                }
            }
        }
    )


@router.post('/api/orders/cancel/{order_id}')
@handle_api_error
def cancel_order(order_id: int):
    success = order_service.cancel_order(ds, order_id)
    if not success:
        return error_response({'success': False, 'error': '订单取消失败或订单不存在'}, 400)
    order = ds.portfolio.get_order_by_id(order_id)
    return api_response({'order_id': order_id, 'order': order}, message='订单已取消')


@router.post('/api/orders/fill/{order_id}')
@handle_api_error
def fill_order(order_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    fill_price = data.get('fill_price')
    if fill_price is None:
        return error_response({'success': False, 'error': '缺少必需参数: fill_price'}, 400)
    fill_quantity = data.get('fill_quantity')
    try:
        result = order_service.fill_order(ds, order_id, float(fill_price), int(fill_quantity) if fill_quantity is not None else None)
    except (ValueError, RuntimeError) as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    return api_response(result, message='订单已成交')


@router.post('/api/orders/update/{order_id}')
@handle_api_error
def update_order(order_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    params = convert_keys_to_snake(data)
    order = ds.portfolio.get_order_by_id(order_id)
    if not order:
        return error_response({'success': False, 'error': '订单不存在'}, 404)
    if order.get('status') not in ['pending', 'submitted']:
        return error_response({'success': False, 'error': '只能修改待处理或已提交的订单'}, 400)
    update_fields = {}
    for field in ['quantity', 'price', 'stop_price', 'notes']:
        if field in params:
            update_fields[field] = params[field]
    if not update_fields:
        return error_response({'success': False, 'error': '没有可更新的字段'}, 400)
    ds.portfolio.update_order(order_id, update_fields)
    updated_order = ds.portfolio.get_order_by_id(order_id)
    return api_response({'order_id': order_id, 'order': updated_order}, message='订单更新成功')


# ============ Trades ============

@router.get('/api/trades/list')
@handle_api_error
def get_trades_list(page: int = Query(1), pageSize: int = Query(20),
                    symbol: Optional[str] = Query(None), direction: Optional[str] = Query(None),
                    keyword: Optional[str] = Query(None)):
    offset = (page - 1) * pageSize
    trades = ds.portfolio.get_trades(limit=9999)
    if symbol:
        trades = [t for t in trades if t.get('symbol') == symbol]
    if direction:
        trades = [t for t in trades if t.get('action') == direction]
    if keyword:
        kw = keyword.lower()
        trades = [t for t in trades if kw in (t.get('symbol') or '').lower() or kw in (t.get('name') or '').lower() or kw in (t.get('reason') or '').lower()]
    total = len(trades)
    trades_page = trades[offset:offset + pageSize]
    return api_response({'total': total, 'page': page, 'pageSize': pageSize, 'items': trades_page})


# ============ Portfolio ============

@router.get('/api/portfolio/positions')
@handle_api_error
def get_portfolio_positions(account_name: Optional[str] = Query(None)):
    """获取持仓列表（数据源：simulation_* 体系，account_name 必填）。与 Flask 新版对齐。"""
    if not account_name:
        return error_response({'success': False, 'error': 'account_name is required'}, 400)
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    repo = SimulationORMRepository()
    if not repo.get_account(account_name):
        return error_response({'success': False, 'error': f'账户不存在: {account_name}'}, 404)

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
    return api_response({'positions': positions, 'count': len(positions)})


@router.get('/api/portfolio/positions/{symbol}')
@handle_api_error
def get_portfolio_position_detail(symbol: str):
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
                'symbol': symbol, 'name': stock_info['name'] if stock_info else holding.get('name', ''),
                'quantity': holding['quantity'], 'avgCost': holding['avg_cost'], 'currentPrice': current_price,
                'marketValue': market_value, 'totalCost': total_cost, 'profit': profit,
                'profitPercent': profit_pct, 'market': holding.get('market'), 'sector': holding.get('sector'),
            })
    return error_response({'success': False, 'error': 'Position not found'}, 404)


@router.get('/api/portfolio/summary')
@handle_api_error
def get_portfolio_summary(account_name: Optional[str] = Query(None)):
    """获取账户汇总（数据源：simulation_* 体系，account_name 必填）。与 Flask 新版对齐。"""
    try:
        if not account_name:
            return error_response({'success': False, 'error': 'account_name is required'}, 400)
        from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
        repo = SimulationORMRepository()
        account = repo.get_account(account_name)
        if not account:
            return error_response({'success': False, 'error': f'账户不存在: {account_name}'}, 404)

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
            'totalValue': total_assets, 'totalCost': total_cost, 'totalMarketValue': market_value,
            'totalPnl': unrealized_pnl, 'totalPnlPct': round(pnl_pct, 2), 'dailyChange': 0.0,
            'positions': len(positions), 'cash': available_cash, 'liquidAssets': available_cash,
            'profitCount': profit_count, 'lossCount': loss_count,
            'lastUpdated': account.updated_at.isoformat() if account.updated_at else None,
        }
        return api_response(summary)
    except Exception as e:
        logger.error(f"Failed to get portfolio summary: {str(e)}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/portfolio/history')
@handle_api_error
def get_portfolio_history(days: int = Query(30)):
    try:
        if days not in [7, 30, 90]:
            days = 30
        history = ds.risk.get_history(days=days)
        if not history:
            return api_response({
                'period': f'{days}d', 'startDate': None, 'endDate': None, 'history': [],
                'summary': {'totalReturn': 0.0, 'maxDrawdown': 0.0, 'volatility': 0.0},
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
        formatted_history = [{
            'date': record['balance_date'].isoformat() if hasattr(record['balance_date'], 'isoformat') else str(record['balance_date']),
            'totalAssets': record['total_assets'], 'dailyReturn': record['daily_return'],
            'cash': record['cash'], 'marketValue': record['market_value'],
        } for record in history]
        response_data = {
            'period': f'{days}d',
            'startDate': formatted_history[0]['date'] if formatted_history else None,
            'endDate': formatted_history[-1]['date'] if formatted_history else None,
            'history': formatted_history,
            'summary': {'totalReturn': round(total_return, 2), 'maxDrawdown': round(max_drawdown, 2), 'volatility': round(volatility, 2)},
        }
        return api_response(response_data)
    except Exception as e:
        logger.error(f"Failed to get portfolio history: {str(e)}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/portfolio/holdings')
@handle_api_error
def get_portfolio_holdings():
    try:
        holdings = ds.portfolio.get_all_holdings()
        if not holdings:
            return api_response({'holdings': [], 'totalCount': 0, 'totalMarketValue': 0.0,
                                 'totalCost': 0.0, 'totalProfit': 0.0, 'totalProfitPercent': 0.0})
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
            market_value = holding['quantity'] * current_price
            cost = holding['quantity'] * holding['avg_cost']
            profit = market_value - cost
            profit_percent = (profit / cost) * 100 if cost > 0 else 0.0
            enriched_holdings.append({
                'symbol': holding['symbol'], 'name': holding['name'], 'quantity': holding['quantity'],
                'avgCost': holding['avg_cost'], 'currentPrice': current_price, 'marketValue': market_value,
                'totalCost': cost, 'profit': profit, 'profitPercent': profit_percent,
                'market': holding['market'], 'sector': holding.get('sector'),
                'addedDate': holding['added_date'].isoformat() if hasattr(holding['added_date'], 'isoformat') else str(holding['added_date']),
            })
            total_market_value += market_value
            total_cost += cost
        for holding in enriched_holdings:
            holding['weight'] = (holding['marketValue'] / total_market_value) * 100 if total_market_value > 0 else 0.0
        enriched_holdings.sort(key=lambda x: x['marketValue'], reverse=True)
        response_data = {
            'holdings': enriched_holdings, 'totalCount': len(enriched_holdings),
            'totalMarketValue': total_market_value, 'totalCost': total_cost,
            'totalProfit': total_market_value - total_cost,
            'totalProfitPercent': ((total_market_value - total_cost) / total_cost) * 100 if total_cost > 0 else 0.0,
        }
        return api_response(response_data)
    except Exception as e:
        logger.error(f"Failed to get portfolio holdings: {str(e)}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/portfolio/allocation')
@handle_api_error
def get_portfolio_allocation():
    holdings = ds.portfolio.get_all_holdings()
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
        items.append({'symbol': holding['symbol'], 'name': holding.get('name', ''), 'value': value})
        total_value += value
    for item in items:
        item['percentage'] = round((item['value'] / total_value) * 100, 2) if total_value > 0 else 0.0
    items.sort(key=lambda x: x['value'], reverse=True)
    return api_response(items)


@router.get('/api/portfolio/equity-curve')
@handle_api_error
def get_portfolio_equity_curve(startDate: Optional[str] = Query(None), endDate: Optional[str] = Query(None)):
    if not endDate:
        endDate = datetime.now().strftime('%Y-%m-%d')
    if not startDate:
        startDate = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    trades = ds.portfolio.get_trades(limit=10000)
    trades = [t for t in trades if t.get('trade_date') and startDate <= str(t['trade_date']) <= endDate]
    if not trades:
        holdings = ds.portfolio.get_all_holdings()
        return api_response({
            'data': {'dates': [datetime.now().strftime('%Y-%m-%d')],
                     'values': [sum(float(h.get('market_value', 0)) for h in holdings)],
                     'holdings_count': len(holdings)},
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
    return api_response({'data': {'dates': dates, 'values': values, 'holdings_count': len(holdings)}})
