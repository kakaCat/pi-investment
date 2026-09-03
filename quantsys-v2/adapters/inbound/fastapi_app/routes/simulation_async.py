"""多账户域 FastAPI 端点（与 Flask simulation.py 契约一致）

注意：Flask 路由直接 jsonify 未做 camelCase 转换，此处同样返回原始 key，
保持前后端契约一致（不用 shared.api_response）。
"""
from collections import defaultdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.shared.services import simulation_service
from application.services.account_trading_service import (
    AccountTradingService, TradingError,
)
from adapters.outbound.repositories.simulation_repository import (
    SimulationORMRepository,
)

router = APIRouter(prefix="/api/simulation", tags=["Simulation Accounts"])

_service = None


def get_service():
    """SimulationService 模块级单例（通过 ServiceFactory 统一获取）"""
    global _service
    if _service is None:
        _service = simulation_service()  # 别名是函数（惰性求值设计），必须调用
    return _service


def _available_accounts(repo: SimulationORMRepository):
    return [a.account_name for a in repo.list_accounts()]


@router.get("/accounts")
async def list_accounts(status: str = Query('active')):
    """账户发现：列出账户 + 摘要"""
    try:
        repo = SimulationORMRepository()
        summaries = repo.list_account_summaries(status=status)
        return {'success': True, 'data': {'accounts': summaries, 'total': len(summaries)}}
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.post("/accounts", status_code=201)
async def create_account(payload: Dict[str, Any] = Body(...)):
    """开户"""
    account_name = payload.get('account_name')
    initial_capital = payload.get('initial_capital')
    if not account_name or initial_capital is None:
        return JSONResponse(status_code=400, content={
            'success': False, 'error': 'account_name 和 initial_capital 必填'})
    try:
        repo = SimulationORMRepository()
        if repo.get_account(account_name):
            return JSONResponse(status_code=409, content={
                'success': False, 'error': f'账户已存在: {account_name}'})
        repo.create_account(
            account_name=account_name,
            initial_capital=float(initial_capital),
            display_name=payload.get('display_name'),
            strategy_name=payload.get('strategy_name'))
        return {'success': True, 'data': {'account_name': account_name}}
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.post("/accounts/{account_name}/trade")
async def manual_trade(account_name: str, payload: Dict[str, Any] = Body(...)):
    """手工/代管交易（agent 虚拟仓核心端点）"""
    try:
        svc = AccountTradingService(repo=SimulationORMRepository())
        result = svc.execute_trade(
            account_name=account_name,
            action=payload.get('action'),
            symbol=payload.get('symbol'),
            shares=payload.get('shares'),
            amount=payload.get('amount'),
            price_limit=payload.get('price_limit'),
            reason=payload.get('reason'),
            max_positions=payload.get('max_positions', 10),
            price=payload.get('price'),
            execute_at=payload.get('execute_at'),  # 条件委托：'market_open' 盘前挂单
            allow_duplicate=bool(payload.get('allow_duplicate', False)),  # 重复挂单确认放行（2026-09-03）
        )
        return {'success': True, 'data': result}
    except TradingError as e:
        body = {'success': False, 'error': str(e)}
        if getattr(e, 'details', None) is not None:
            body['details'] = e.details
        return JSONResponse(status_code=e.status_code, content=body)
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.get("/accounts/{account_name}/pending-orders")
async def list_pending_orders(account_name: str,
                              status: Optional[str] = Query('pending')):
    """挂单列表（默认只返回 pending，?status=all 返回全部）"""
    try:
        svc = AccountTradingService(repo=SimulationORMRepository())
        orders = svc.repo.get_pending_orders(
            account_name=account_name,
            status=None if status == 'all' else status)
        return {'success': True, 'data': [o.to_dict() for o in orders]}
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.post("/accounts/{account_name}/pending-orders/{order_id}/cancel")
async def cancel_pending_order(account_name: str, order_id: int):
    """取消挂单（仅 pending 状态可取消）"""
    try:
        svc = AccountTradingService(repo=SimulationORMRepository())
        result = svc.cancel_pending_order(account_name, order_id)
        return {'success': True, 'data': result}
    except TradingError as e:
        return JSONResponse(status_code=e.status_code,
                            content={'success': False, 'error': str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.get("/trades")
async def get_trades(account_name: Optional[str] = Query(None),
                     limit: int = Query(100)):
    """交易记录（account_name 必填）"""
    repo = SimulationORMRepository()
    if not account_name:
        return JSONResponse(status_code=400, content={
            'success': False, 'error': 'account_name is required',
            'available_accounts': _available_accounts(repo)})
    if not repo.get_account(account_name):
        return JSONResponse(status_code=404, content={
            'success': False, 'error': f'账户不存在: {account_name}',
            'available_accounts': _available_accounts(repo)})
    trades = repo.get_trades(account_name, limit=limit)
    return {'success': True, 'data': [t.to_dict() for t in trades]}


@router.get("/accounts/{account_name}/trades")
async def get_account_trades(account_name: str, limit: int = Query(100)):
    """RESTful 风格的交易记录查询（别名，与 GET /trades 功能相同）"""
    return await get_trades(account_name=account_name, limit=limit)


@router.get("/performance")
async def get_performance(account_name: Optional[str] = Query(None)):
    """账户绩效（account_name 必填，优先读快照表）"""
    repo = SimulationORMRepository()
    if not account_name:
        return JSONResponse(status_code=400, content={
            'success': False, 'error': 'account_name is required',
            'available_accounts': _available_accounts(repo)})
    account = repo.get_account(account_name)
    if not account:
        return JSONResponse(status_code=404, content={
            'success': False, 'error': f'账户不存在: {account_name}',
            'available_accounts': _available_accounts(repo)})

    initial_capital = float(account.initial_capital or 0) or 100000.0
    snaps = repo.get_equity_snapshots(account_name, limit=365)
    equity_curve = [{
        'date': s.snapshot_date.isoformat(),
        'total_value': float(s.total_value or 0),
        'cash': float(s.cash or 0),
        'market_value': float(s.position_value or 0),
        'return': round(float(s.cumulative_return or 0) * 100, 2),
    } for s in reversed(snaps)]
    total_value = float(account.total_value or 0)
    return {'success': True, 'data': {
        'equity_curve': equity_curve,
        'initial_capital': initial_capital,
        'current_value': total_value,
        'cumulative_return': round((total_value - initial_capital) / initial_capital * 100, 2),
        'max_drawdown': round(float(account.max_drawdown or 0) * 100, 2),
    }}


# ============ 策略 / 执行（P7 补齐，对齐 Flask simulation.py） ============

@router.get("/strategies")
async def list_strategies():
    """列出所有可用策略"""
    try:
        strategies = get_service().list_strategies()
        return {'success': True, 'data': strategies}
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """获取策略详情"""
    try:
        strategy = get_service().get_strategy_info(strategy_id)
        if not strategy:
            return JSONResponse(status_code=404, content={
                'success': False, 'error': f'Strategy {strategy_id} not found'})
        return {'success': True, 'data': strategy}
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.post("/run")
async def run_strategy(payload: Dict[str, Any] = Body(default_factory=dict)):
    """执行策略"""
    try:
        data = payload or {}
        strategy_id = data.get('strategy_id')
        account_name = data.get('account_name')
        repo = SimulationORMRepository()
        if not account_name:
            return JSONResponse(status_code=400, content={
                'success': False, 'error': 'account_name is required',
                'available_accounts': _available_accounts(repo)})
        if not repo.get_account(account_name):
            return JSONResponse(status_code=404, content={
                'success': False, 'error': f'账户不存在: {account_name}',
                'available_accounts': _available_accounts(repo)})
        force_rebalance = data.get('force_rebalance', False)
        if not strategy_id:
            return JSONResponse(status_code=400, content={
                'success': False, 'error': 'strategy_id is required'})
        result = get_service().run_strategy(
            strategy_id, account_name=account_name, force_rebalance=force_rebalance)
        return {'success': True, 'data': result}
    except ValueError as e:
        return JSONResponse(status_code=404, content={'success': False, 'error': str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.get("/accounts/{account_name}")
async def get_account(account_name: str):
    """获取账户状态和持仓"""
    try:
        account = get_service().get_account_status(account_name)
        return {'success': True, 'data': account}
    except ValueError as e:
        return JSONResponse(status_code=404, content={'success': False, 'error': str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})


@router.get("/execution-history")
async def get_execution_history(account_name: Optional[str] = Query(None),
                                strategy_id: Optional[str] = Query(None),
                                limit: int = Query(50)):
    """获取策略执行历史"""
    try:
        repo = SimulationORMRepository()
        if not account_name:
            return JSONResponse(status_code=400, content={
                'success': False, 'error': 'account_name is required',
                'available_accounts': _available_accounts(repo)})

        trades = repo.get_trades_by_account(account_name, limit)
        history_by_date = defaultdict(list)
        for trade in trades:
            date = str(trade.trade_date) if hasattr(trade, 'trade_date') else None
            if date:
                history_by_date[date].append({
                    'symbol': trade.symbol,
                    'action': trade.action,
                    'shares': trade.shares,
                    'price': float(trade.filled_price) if trade.filled_price else 0,
                })

        history = []
        for date, trades_list in sorted(history_by_date.items(), reverse=True):
            history.append({
                'date': date,
                'strategy_id': strategy_id or 'v13',
                'strategy_name': 'V13 XGBoost Multi-Factor',
                'status': 'completed',
                'trades_count': len(trades_list),
                'trades': trades_list,
            })
        return {'success': True, 'data': history[:limit]}
    except Exception as e:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(e)})
