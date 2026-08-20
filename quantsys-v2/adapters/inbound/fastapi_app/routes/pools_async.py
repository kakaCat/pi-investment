"""股票池管理 API - FastAPI 版（从 Flask pools.py + pool_scan.py + pool_scan_switch.py 迁移，契约一致）

路由顺序：字面量路径（/scan-and-create、/scan-all、/scan-status、/scan-results、
/scan/schedule）必须先于 /{pool_id} 注册，否则会被参数路径吞掉。
复用 Flask 的 stock_pool_service / pool_validation_service，保证 parity。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error,
    stock_pool_service, pool_validation_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Stock Pools - 股票池管理"])

svc = stock_pool_service
val_svc = pool_validation_service

# 筛选条件校验（与 Flask pools.py 一致）
ALLOWED_FIELDS = {
    'roe', 'pe', 'pb', 'gross_margin', 'debt_ratio',
    'net_profit_growth', 'market_cap', 'circulating_mv',
    'avg_turnover_rate', 'rsi', 'macd', 'volume_ratio_5d'
}
ALLOWED_OPERATORS = {'>=', '<=', '>', '<', '==', '!='}


def validate_filter(filter_dict):
    conditions = filter_dict.get('conditions', [])
    for cond in conditions:
        field = cond.get('field')
        operator = cond.get('operator')
        value = cond.get('value')
        if field not in ALLOWED_FIELDS:
            raise ValueError(f"Invalid field: {field}. Allowed: {', '.join(sorted(ALLOWED_FIELDS))}")
        if operator not in ALLOWED_OPERATORS:
            raise ValueError(f"Invalid operator: {operator}. Allowed: {', '.join(sorted(ALLOWED_OPERATORS))}")
        if not isinstance(value, (int, float)):
            raise ValueError(f"Invalid value type for field '{field}': {type(value).__name__}. Must be number.")
    return True


def _convert_filter_keys(filter_dict):
    if not filter_dict:
        return filter_dict
    mapping = {'minScore': 'min_score', 'maxRiskLevel': 'max_risk_level', 'topN': 'top_n'}
    return {mapping.get(k, k): v for k, v in filter_dict.items()}


# ============ 字面量路径（先于 /{pool_id} 注册）============

@router.post('/api/pools/scan-and-create')
def scan_and_create(payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload
    if not data:
        return error_response({'success': False, 'error': 'Request body required'}, 400)
    name = data.get('name')
    pool_type = data.get('poolType') or data.get('pool_type')
    filter_params = data.get('filter') or data.get('filterTemplate') or data.get('filter_template')
    if not name or not pool_type or not filter_params:
        return error_response({'success': False, 'error': 'name, poolType, and filter are required'}, 400)
    if filter_params and filter_params.get('conditions'):
        try:
            validate_filter(filter_params)
        except ValueError as e:
            return error_response({'success': False, 'error': str(e)}, 400)
    try:
        pool = svc.create_from_scan(
            name=name, pool_type=pool_type, scan_params=_convert_filter_keys(filter_params),
            refresh_interval=data.get('refreshInterval') or data.get('refresh_interval'),
            description=data.get('description'))
        return error_response({'success': True, 'data': pool}, 201)
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error(f"Scan and create failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/pools/scan-all')
@handle_api_error
def scan_all_pools(payload: Optional[Dict[str, Any]] = Body(None)):
    from application.services.pool_scanner_service import pool_scanner_service
    data = payload or {}
    result = pool_scanner_service.scan_all_pools(
        strategy_ids=data.get('strategy_ids'), min_score=data.get('min_score', 70))
    return api_response(result)


@router.get('/api/pools/scan-results')
@handle_api_error
def get_scan_results():
    return api_response({'results': [], 'count': 0, 'message': '扫描历史功能开发中'})


@router.get('/api/pools/scan-status')
@handle_api_error
def get_scan_status():
    from adapters.outbound.repositories import StockPoolORMRepository
    pool_repo = StockPoolORMRepository()
    pools = pool_repo.get_all_pools()
    pools_status = []
    enabled_count = 0
    disabled_count = 0
    for pool in pools:
        scan_enabled = pool.get('scan_enabled', True)
        if scan_enabled:
            enabled_count += 1
        else:
            disabled_count += 1
        pools_status.append({
            'pool_id': pool['id'], 'pool_name': pool.get('name'),
            'pool_type': pool.get('pool_type'), 'scan_enabled': scan_enabled,
            'symbols_count': len(pool.get('symbols', [])),
        })
    return api_response({'pools': pools_status,
                         'summary': {'total': len(pools), 'enabled': enabled_count, 'disabled': disabled_count}})


@router.post('/api/pools/scan/schedule')
@handle_api_error
def manage_scan_schedule(payload: Optional[Dict[str, Any]] = Body(None)):
    from application.services.pool_scan_scheduler import pool_scan_scheduler
    data = payload or {}
    action = data.get('action', 'start')
    if action == 'start':
        pool_scan_scheduler.start()
        return api_response({'status': 'running', 'message': '股票池扫描定时任务已启动（每天16:05执行）'})
    elif action == 'stop':
        pool_scan_scheduler.stop()
        return api_response({'status': 'stopped', 'message': '股票池扫描定时任务已停止'})
    elif action == 'trigger':
        pool_scan_scheduler.trigger_scan_now()
        return api_response({'status': 'triggered', 'message': '已触发立即扫描'})
    else:
        return error_response({'success': False, 'error': f'无效的操作: {action}，支持: start/stop/trigger'}, 400)


# ============ 池子 CRUD ============

@router.post('/api/pools')
def create_pool(payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload
    if not data:
        return error_response({'success': False, 'error': 'Request body required'}, 400)
    name = data.get('name')
    pool_type = data.get('poolType') or data.get('pool_type')
    if not name or not pool_type:
        return error_response({'success': False, 'error': 'name and poolType are required'}, 400)
    filter_template_raw = data.get('filterTemplate') or data.get('filter_template')
    if filter_template_raw and filter_template_raw.get('conditions'):
        try:
            validate_filter(filter_template_raw)
        except ValueError as e:
            return error_response({'success': False, 'error': str(e)}, 400)
    try:
        pool = svc.create_pool(
            name=name, pool_type=pool_type, symbols=data.get('symbols'),
            filter_template=_convert_filter_keys(filter_template_raw),
            refresh_interval=data.get('refreshInterval') or data.get('refresh_interval'),
            description=data.get('description'))
        return error_response({'success': True, 'data': pool}, 201)
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error(f"Create pool failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/pools')
def list_pools():
    try:
        pools = svc.list_pools()
        return {'success': True, 'data': pools}
    except Exception as e:
        logger.error(f"List pools failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ /{pool_id} 参数路径 ============

@router.get('/api/pools/{pool_id}')
def get_pool(pool_id: int):
    try:
        pool = svc.get_pool(pool_id)
        return {'success': True, 'data': pool}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)
    except Exception as e:
        logger.error(f"Get pool failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.put('/api/pools/{pool_id}')
def update_pool(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    try:
        pool = svc.update_pool(pool_id, name=data.get('name'), symbols=data.get('symbols'),
                               description=data.get('description'))
        return {'success': True, 'data': pool}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)
    except Exception as e:
        logger.error(f"Update pool failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.delete('/api/pools/{pool_id}')
def delete_pool(pool_id: int):
    try:
        svc.delete_pool(pool_id)
        return {'success': True, 'message': f'Pool {pool_id} deleted'}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)
    except Exception as e:
        logger.error(f"Delete pool failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/pools/{pool_id}/refresh')
def refresh_pool(pool_id: int):
    try:
        pool = svc.refresh_pool(pool_id)
        return {'success': True, 'data': pool}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error(f"Refresh pool failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/pools/{pool_id}/sync-stock-names')
def sync_stock_names(pool_id: int):
    try:
        pool = svc.sync_stock_names(pool_id)
        return {'success': True, 'data': pool}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error(f"Sync stock names failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.put('/api/pools/{pool_id}/members/{symbol}')
def update_member(pool_id: int, symbol: str, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    try:
        pool = svc.update_member(
            pool_id=pool_id, symbol=symbol,
            member_data={
                'description': data.get('description'),
                'buy_point': data.get('buyPoint') or data.get('buy_point'),
                'sell_point': data.get('sellPoint') or data.get('sell_point'),
                'tags': data.get('tags', []),
            })
        return {'success': True, 'data': pool}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)
    except Exception as e:
        logger.error(f"Update member failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/pools/{pool_id}/members')
def add_members(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return error_response({'success': False, 'error': 'symbols must be a non-empty array'}, 400)
    try:
        result = svc.add_members(
            pool_id=pool_id, symbols=symbols,
            member_data={
                'description': data.get('description'),
                'buy_point': data.get('buyPoint') or data.get('buy_point'),
                'sell_point': data.get('sellPoint') or data.get('sell_point'),
                'tags': data.get('tags', []),
            })
        return {'success': True, 'data': result}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)
    except Exception as e:
        logger.error(f"Add members failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.delete('/api/pools/{pool_id}/members')
def remove_members(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return error_response({'success': False, 'error': 'symbols must be a non-empty array'}, 400)
    try:
        result = svc.remove_members(pool_id=pool_id, symbols=symbols)
        return {'success': True, 'data': result}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)
    except Exception as e:
        logger.error(f"Remove members failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/pools/{pool_id}/validate')
def validate_pool(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    try:
        result = val_svc.validate_pool(
            pool_id=pool_id,
            strategy_ids=data.get('strategyIds') or data.get('strategy_ids'),
            start_date=data.get('startDate') or data.get('start_date'),
            end_date=data.get('endDate') or data.get('end_date'))
        return {'success': True, 'data': result}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error(f"Validate pool failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/pools/{pool_id}/scan-signals')
def scan_pool_signals(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    from application.services.pool_signal_scanner import PoolSignalScanner
    from adapters.outbound.repositories import KlineORMRepository, StrategyORMRepository
    data = payload or {}
    strategy_id = data.get('strategy_id') or data.get('strategyId')
    lookback_days = data.get('lookback_days') or data.get('lookbackDays') or 60
    if not strategy_id:
        return error_response({'success': False, 'error': 'strategy_id is required'}, 400)
    try:
        pool = svc._pool_repo.get_pool(pool_id)
        if not pool:
            return error_response({'success': False, 'error': f'Pool {pool_id} not found'}, 404)
        symbols = pool.get('symbols', [])
        if not symbols:
            return error_response({'success': False, 'error': 'Pool is empty'}, 400)
        kline_repo = KlineORMRepository()
        strategy_repo = StrategyORMRepository()
        scanner = PoolSignalScanner(kline_repo, strategy_repo)
        result = scanner.scan_pool_signals(symbols=symbols, strategy_id=strategy_id, lookback_days=lookback_days)
        svc._pool_repo.update_signal_scan(pool_id, result)
        return {'success': True, 'data': result}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error(f"Scan pool signals failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/pools/{pool_id}/scan')
@handle_api_error
def scan_pool(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    from application.services.pool_scanner_service import pool_scanner_service
    data = payload or {}
    result = pool_scanner_service.scan_pool(
        pool_id=pool_id, strategy_ids=data.get('strategy_ids'), min_score=data.get('min_score', 70))
    if not result['success']:
        return error_response(result, 404)
    return api_response(result)


@router.put('/api/pools/{pool_id}/scan-switch')
@handle_api_error
def toggle_pool_scan(pool_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    from adapters.outbound.repositories import StockPoolORMRepository
    data = payload
    if data is None:
        return error_response({'success': False, 'error': '请求体不能为空'}, 400)
    enabled = data.get('enabled')
    if enabled is None:
        return error_response({'success': False, 'error': 'enabled 参数必需（true 或 false）'}, 400)
    pool_repo = StockPoolORMRepository()
    pool = pool_repo.get_pool_by_id(pool_id)
    if not pool:
        return error_response({'success': False, 'error': f'股票池 {pool_id} 不存在'}, 404)
    success = pool_repo.update_scan_enabled(pool_id, enabled)
    if not success:
        return error_response({'success': False, 'error': '更新失败'}, 500)
    return api_response({
        'pool_id': pool_id, 'pool_name': pool.get('name'), 'scan_enabled': enabled,
        'message': f"股票池扫描已{'开启' if enabled else '关闭'}"})
