"""订单/交易/投资组合 API - FastAPI 版（从 Flask orders.py 迁移，响应契约保持一致）

orders.py 同时承载 orders CRUD、trades/list 和 portfolio 端点。
复用同一 ds 单例与 order_service，原始 SQL 与 kline 逻辑与 Flask 完全一致。
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

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

# ============ Trades ============

@router.get('/api/trades/list')
@handle_api_error
def get_trade_history(
    account_name: Optional[str] = Query('agent_virtual'),
    order_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    查询交易历史记录

    参数:
    - account_name: 账户名称，默认 agent_virtual
    - order_id: 订单ID（可选）
    - symbol: 股票代码（可选）
    - direction: 交易方向 BUY/SELL（可选）
    - page: 页码，默认 1
    - page_size: 每页数量，默认 20，最大 100

    返回:
    {
        "success": true,
        "data": {
            "orders": [...],
            "pending_count": 0,
            "filled_count": 5,
            "total": 5,
            "page": 1,
            "page_size": 20
        }
    }
    """
    from infrastructure.persistence.orm.models.simulation import SimulationTrade
    from infrastructure.persistence.orm import get_session

    try:
        session = get_session()

        # 构建查询
        query = session.query(SimulationTrade).filter(
            SimulationTrade.account_name == account_name
        )

        # 添加可选过滤条件
        if order_id:
            try:
                query = query.filter(SimulationTrade.order_id == int(order_id))
            except ValueError:
                pass  # 忽略无效的 order_id

        if symbol:
            query = query.filter(SimulationTrade.symbol == symbol)

        if direction:
            query = query.filter(SimulationTrade.action == direction.upper())

        # 排序和分页
        query = query.order_by(
            SimulationTrade.trade_date.desc(),
            SimulationTrade.id.desc()
        )

        offset = (page - 1) * page_size
        trades = query.limit(page_size).offset(offset).all()

        # 格式化交易记录
        orders = []
        for trade in trades:
            orders.append({
                'order_id': trade.order_id or trade.id,
                'symbol': trade.symbol,
                'action': trade.action,
                'status': 'filled',  # simulation_trades 中所有记录都是已成交
                'price': float(trade.price or 0),
                'filled_price': float(trade.filled_price or 0),
                'shares': trade.shares,
                'filled_shares': trade.shares,  # simulation_trades 中所有记录都是已成交
                'amount': float(trade.amount or 0),
                'commission': float(trade.commission or 0),
                'stamp_duty': float(trade.stamp_duty or 0),
                'total_cost': float(trade.total_cost or 0) if trade.total_cost else None,
                'realized_pnl': float(trade.realized_pnl or 0) if trade.realized_pnl else None,
                'realized_pnl_rate': float(trade.realized_pnl_rate or 0) if trade.realized_pnl_rate else None,
                'trade_date': trade.trade_date.isoformat() if trade.trade_date else None,
                'trade_time': trade.trade_time.isoformat() if trade.trade_time else None,
                'created_at': trade.created_at.isoformat() if trade.created_at else None,
                'reason': trade.reason,
            })

        # 统计状态（simulation_trades 中的记录都是已执行）
        pending_count = 0
        filled_count = len(orders)
        total = filled_count

        return api_response({
            'orders': orders,
            'pending_count': pending_count,
            'filled_count': filled_count,
            'total': total,
            'page': page,
            'page_size': page_size,
        })

    except Exception as e:
        logger.error(f"查询交易历史失败: {str(e)}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)
    finally:
        if 'session' in locals():
            session.close()


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
            'accountName': account_name,
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


    return api_response({'data': {'dates': dates, 'values': values, 'holdings_count': len(holdings)}})
