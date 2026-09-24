"""多账户域 FastAPI 端点（与 Flask simulation.py 契约一致）

注意：Flask 路由直接 jsonify 未做 camelCase 转换，此处同样返回原始 key，
保持前后端契约一致（不用 shared.api_response）。
"""
from collections import defaultdict
from datetime import datetime   # 滑点报表的窗口过滤（2026-09-13）
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.shared.services import simulation_service
from application.services.account_trading_service import (
    AccountTradingService, TradingError,
)
from adapters.outbound.repositories.simulation_repository import (
    SimulationORMRepository, SimulationPendingOrder,   # 后者用于滑点报表（M5 闭环）
)

logger = structlog.get_logger(__name__)

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
            submitted_by=payload.get('submitted_by'),  # 下单窗口编码
        )
        return {'success': True, 'data': result}
    except TradingError as e:
        body = {'success': False, 'error': str(e)}
        if getattr(e, 'details', None) is not None:
            body['details'] = e.details
        return JSONResponse(status_code=e.status_code, content=body)
    except Exception as e:
        # 2026-09-11（w-8f2c4cc5）：此前 500 分支不打日志，看板事件 56dab403
        # 只留下 access log 的 "500"，根因（shares 传字符串 → TypeError）无处可查。
        # 非预期异常必须留 traceback + 请求上下文。
        logger.error("manual_trade_unexpected_error", account=account_name,
                     payload={k: v for k, v in (payload or {}).items()
                              if k != 'reason'},
                     error=str(e), exc_info=True)
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


@router.get("/accounts/{account_name}/slippage-report")
async def slippage_report(account_name: str, days: int = Query(30, ge=1, le=365),
                          symbol: Optional[str] = Query(None)):
    """执行质量报表：决策价 vs 成交价的滑点（2026-09-13 w-a9ec14d7，M5 闭环）

    口径（R-013 可追溯）：
      · slippage_bps 方向归一：**正数 = 买贵 / 卖便宜 = 成本**；
      · 只统计**两者都有值**的已成交挂单；无决策价的单子单列 missing，
        绝不按 0 计入均值（否则「缺数据」会被平均成「没滑点」）；
      · price_source 一并返回，便于判断基准价的可信来源。
    """
    try:
        from datetime import timedelta
        svc = AccountTradingService(repo=SimulationORMRepository())
        since = datetime.now() - timedelta(days=days)
        rows = (svc.repo.session.query(SimulationPendingOrder)
                .filter(SimulationPendingOrder.account_name == account_name,
                        SimulationPendingOrder.status == 'executed')
                .order_by(SimulationPendingOrder.id.desc())
                .limit(1000).all())
        recs, missing = [], 0
        for o in rows:
            if getattr(o, 'updated_at', None) and o.updated_at.replace(tzinfo=None) < since:
                continue
            if symbol and o.symbol != symbol:
                continue
            if o.slippage_bps is None:
                missing += 1
            recs.append({
                'pending_order_id': o.id, 'symbol': o.symbol,
                'action': str(o.action).lower(), 'shares': o.shares,
                'decision_price': float(o.decision_price) if o.decision_price is not None else None,
                'price_source': o.price_source,
                'fill_price': float(o.fill_price) if o.fill_price is not None else None,
                'slippage_bps': float(o.slippage_bps) if o.slippage_bps is not None else None,
                'executed_trade_id': o.executed_trade_id,
                'at': str(getattr(o, 'updated_at', '') or ''),
            })
        vals = [r['slippage_bps'] for r in recs if r['slippage_bps'] is not None]
        payload = {
            'account_name': account_name, 'days': days,
            'total_fills': len(vals),
            'missing_decision_price': missing,
            'avg_slippage_bps': round(sum(vals) / len(vals), 2) if vals else None,
            'max_slippage_bps': max(vals) if vals else None,
            'min_slippage_bps': min(vals) if vals else None,
            'cost_bps_total': round(sum(vals), 2) if vals else None,
            'records': recs,
            'note': ('平均/极值只统计 decision_price 与 fill_price 都有的单子；'
                     'missing_decision_price 单列——缺数据不等于零滑点'),
        }
        return {'success': True, 'data': payload}
    except Exception as e:
        logger.error("slippage_report_failed", account=account_name, error=str(e), exc_info=True)
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
        logger.error("cancel_pending_order_unexpected_error",
                     account=account_name, order_id=order_id,
                     error=str(e), exc_info=True)
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
    items = [t.to_dict() for t in trades]
    # 补股票名称（2026-09-10）：SimulationTrade.to_dict 无 name 列，联查 stocks 主数据表，
    # 一次 IN 查询避免 N+1；失败容忍为空串（与 _trade_to_dict 同语义）
    try:
        from infrastructure.persistence.orm.models import Stock
        from sqlalchemy import select
        symbols = list({t.symbol for t in trades})
        if symbols:
            names = {sym: name for sym, name in repo.session.execute(
                select(Stock.symbol, Stock.name).where(Stock.symbol.in_(symbols))).all() if name}
            for it in items:
                it['name'] = names.get(it.get('symbol'), '')
    except Exception:
        pass
    return {'success': True, 'data': items}


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
