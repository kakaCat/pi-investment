"""策略管理 API - FastAPI 版（从 Flask strategies.py 迁移，响应契约保持一致）

注意路由顺序：FastAPI 按注册顺序匹配，字面量路径（/list、/create 等）必须
放在 /{strategy_id} 参数路径之前，否则 /list 会被 {strategy_id} 吞掉。
复用 Flask 的 strategy_service（StrategyCodeService）与 ds，保证 parity。
"""
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    backtest_repo, execution_repo, api_response, error_response, handle_api_error,
    convert_keys_to_snake, strategy_service,
)
from adapters.shared.services import strategy_validation_service, strategy_optimizer
from application.services.search_space import SearchSpace

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Strategies - 策略管理"])

# 与 Flask 一致：模块级初始化 validation service（通过 ServiceFactory 统一获取）
validation_service = strategy_validation_service


def enrich_strategy_response(strategy: Dict) -> Dict:
    """丰富策略响应数据（与 Flask strategies.py 逻辑一致）。"""
    type_mapping = {'strategy': 'trend', 'indicator': 'momentum', 'script': 'arbitrage'}
    status_mapping = {
        'valid': 'stopped', 'invalid': 'error', 'stopped': 'stopped',
        'running': 'running', 'paused': 'paused',
    }
    validation_status = strategy.get('validation_status', strategy.get('status', 'valid'))
    strategy_profile = strategy.get('strategy_profile')
    if isinstance(strategy_profile, str):
        try:
            strategy_profile = json.loads(strategy_profile)
        except (json.JSONDecodeError, TypeError):
            strategy_profile = {}
    if not isinstance(strategy_profile, dict):
        strategy_profile = {}

    return {
        'id': str(strategy.get('id')),
        'name': strategy.get('strategy_name'),
        'strategy_type': strategy.get('strategy_type'),
        'type': type_mapping.get(strategy.get('code_type'), 'trend'),
        'status': status_mapping.get(validation_status, 'stopped'),
        'description': strategy.get('description'),
        'code': strategy.get('code_content'),
        'params': strategy.get('parsed_params'),
        'is_active': strategy.get('is_active', True),
        'validation_status': strategy.get('validation_status', 'unvalidated'),
        'strategy_profile': strategy_profile,
        'tags': strategy_profile.get('tags', []) if isinstance(strategy_profile.get('tags'), list) else [],
        'performance': None,
        'positions': 0,
        'created_at': strategy.get('created_at'),
        'updated_at': strategy.get('updated_at'),
        'last_executed': strategy.get('last_executed'),
    }


def is_active_strategy(strategy: Dict) -> bool:
    return strategy.get('is_active', True) is not False


# ============ 字面量路径（必须先于 /{strategy_id} 注册）============

@router.get('/api/strategies/list')
@handle_api_error
def get_strategies_list(source: str = Query('user'), category: Optional[str] = Query(None),
                        page: int = Query(1), pageSize: int = Query(20),
                        status: Optional[str] = Query(None), codeType: Optional[str] = Query(None)):
    """获取策略列表（source=user 用户策略 / source=builtin 内置策略）"""
    if source == 'builtin':
        from domain.backtest.engine.strategy_factory import StrategyFactory
        if not StrategyFactory._registry:
            StrategyFactory.auto_discover()
        strategies = []
        for strategy_type in StrategyFactory.list_all():
            metadata = StrategyFactory.get_info(strategy_type)
            if metadata:
                strategies.append({
                    'strategy_type': strategy_type,
                    'class_name': metadata['class_name'],
                    'description': metadata['description'],
                    'category': metadata['category'],
                    'default_params': metadata.get('default_params', {}),
                    'param_schema': metadata.get('param_schema', {}),
                })
        if category:
            strategies = [s for s in strategies if s['category'] == category]
        return api_response({'strategies': strategies, 'total': len(strategies)})

    code_type = codeType
    if code_type and code_type not in ('indicator', 'script', 'strategy'):
        return error_response({'success': False, 'error': f'无效的 code_type: {code_type}，必须是 indicator、script 或 strategy'}, 400)

    strategies = strategy_service.list_strategies(code_type=code_type, active_only=True)
    strategies = [s for s in strategies if is_active_strategy(s)]
    if status:
        strategies = [s for s in strategies if s.get('status') == status]
    enriched = [enrich_strategy_response(s) for s in strategies]
    total = len(enriched)
    offset = (page - 1) * pageSize
    return api_response({'total': total, 'page': page, 'page_size': pageSize,
                         'items': enriched[offset:offset + pageSize]})


@router.get('/api/strategies/detail/{strategy_id}')
@handle_api_error
def get_strategy_detail(strategy_id: str):
    strategy = strategy_service.get_strategy(strategy_id)
    if not strategy:
        return error_response({'success': False, 'error': '策略不存在'}, 404)
    return api_response(enrich_strategy_response(strategy))


@router.get('/api/strategies/performance/{strategy_id}')
@handle_api_error
def get_strategy_performance_detail(strategy_id: str, startDate: Optional[str] = Query(None),
                                    endDate: Optional[str] = Query(None)):
    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return error_response({'success': False, 'error': '策略不存在'}, 404)

    if startDate and endDate:
        backtest_results = backtest_repo.get_backtests_by_strategy(strategy_id, limit=200)
        backtest_results = [b for b in backtest_results
                            if b.get('start_date') and startDate <= str(b.get('start_date'))[:10] <= endDate]
    else:
        backtest_results = backtest_repo.get_backtests_by_strategy(strategy_id, limit=50)
    stats = backtest_repo.get_backtest_stats(strategy_name=strategy_id)

    executions = []
    try:
        all_executions = execution_repo.get_all_executions(limit=200)
        executions = [e for e in all_executions if e.get('strategy_id') == strategy_id]
        if startDate and endDate:
            executions = [e for e in executions
                          if e.get('created_at') and startDate <= str(e.get('created_at'))[:10] <= endDate]
    except Exception:
        pass

    performance_data = {
        'strategy_id': strategy_id,
        'strategy_name': existing.get('name'),
        'backtest_count': len(backtest_results),
        'execution_count': len(executions),
        'stats': stats,
        'recent_backtests': backtest_results[:10],
        'recent_executions': executions[:10],
        'date_range': {'start_date': startDate, 'end_date': endDate} if startDate and endDate else None,
    }
    return api_response(performance_data)


@router.post('/api/strategies/create')
@handle_api_error
def create_strategy(payload: Optional[Dict[str, Any]] = Body(None)):
    if not payload:
        return error_response({'success': False, 'error': '请求体不能为空'}, 400)
    strategy_data = convert_keys_to_snake(payload)
    if 'name' not in strategy_data:
        return error_response({'success': False, 'error': '缺少必需参数: name'}, 400)
    if 'code' not in strategy_data:
        return error_response({'success': False, 'error': '缺少必需参数: code'}, 400)
    code_type = strategy_data.get('code_type', 'indicator')
    if code_type not in ('indicator', 'script', 'strategy'):
        return error_response({'success': False, 'error': f'无效的策略类型: {code_type}，必须是 indicator、script 或 strategy'}, 400)

    result = strategy_service.create_strategy(
        name=strategy_data['name'], code=strategy_data['code'], code_type=code_type,
        description=strategy_data.get('description'), params=strategy_data.get('params'))
    strategy = strategy_service.get_strategy(result['strategy_id'])
    return api_response(enrich_strategy_response(strategy), message='策略创建成功')


@router.post('/api/strategies/optimize')
def optimize_strategy(payload: Optional[Dict[str, Any]] = Body(None)):
    try:
        data = payload or {}
        strategy_id = data.get('strategyId')
        symbol = data.get('symbol')
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        param_ranges = data.get('paramRanges')
        initial_cash = data.get('initialCash', 1000000)
        sort_by = data.get('sortBy', 'sharpe_ratio')
        period = data.get('period')

        if not all([strategy_id, symbol, start_date, end_date, param_ranges]):
            return error_response({'success': False, 'error': "strategyId, symbol, startDate, endDate, and paramRanges are required"}, 400)
        if not param_ranges or not isinstance(param_ranges, dict):
            return error_response({'success': False, 'error': "paramRanges must be a non-empty dictionary"}, 400)

        search_space = SearchSpace(param_ranges)
        param_grid = search_space.generate_grid()
        if not param_grid:
            return error_response({'success': False, 'error': "Generated parameter grid is empty"}, 400)

        optimizer = strategy_optimizer
        results = optimizer.optimize(
            strategy_id=strategy_id, symbol=symbol, start_date=start_date, end_date=end_date,
            param_grid=param_grid, initial_cash=initial_cash, sort_by=sort_by, period=period)

        camel_results = [{
            'params': r['params'], 'sharpeRatio': r.get('sharpe_ratio'),
            'totalReturn': r.get('total_return'), 'maxDrawdown': r.get('max_drawdown'),
            'winRate': r.get('win_rate'), 'totalTrades': r.get('total_trades'),
        } for r in results]

        return {'success': True, 'results': camel_results,
                'totalCombinations': len(param_grid), 'successfulCombinations': len(results)}
    except Exception as e:
        logger.error(f"optimize failed: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/strategies/validate')
@handle_api_error
def validate_strategies(payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    threshold = data.get('threshold', 60.0)
    dry_run = data.get('dryRun', False)
    if not start_date or not end_date:
        return error_response({'success': False, 'message': "startDate and endDate are required"}, 400)
    result = validation_service.validate_all_strategies(
        start_date=start_date, end_date=end_date, threshold=threshold, dry_run=dry_run)
    return api_response(success=True, data=result)


@router.post('/api/strategies/update/{strategy_id}')
@handle_api_error
def update_strategy(strategy_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    if not payload:
        return error_response({'success': False, 'error': '请求体不能为空'}, 400)
    strategy_data = convert_keys_to_snake(payload)
    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return error_response({'success': False, 'error': '策略不存在'}, 404)
    code_type = strategy_data.get('code_type')
    if code_type and code_type not in ('indicator', 'script'):
        return error_response({'success': False, 'error': f'无效的策略类型: {code_type}，必须是 indicator 或 script'}, 400)
    success = strategy_service.update_strategy(
        strategy_id=strategy_id, name=strategy_data.get('name'), code=strategy_data.get('code'),
        code_type=code_type, description=strategy_data.get('description'), params=strategy_data.get('params'))
    if not success:
        return error_response({'success': False, 'error': '策略更新失败'}, 500)
    strategy = strategy_service.get_strategy(strategy_id)
    return api_response(enrich_strategy_response(strategy), message='策略更新成功')


@router.post('/api/strategies/delete/{strategy_id}')
@handle_api_error
def delete_strategy(strategy_id: str):
    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return error_response({'success': False, 'error': '策略不存在'}, 404)
    success = strategy_service.delete_strategy(strategy_id)
    if not success:
        return error_response({'success': False, 'error': '策略删除失败'}, 500)
    return api_response({'strategy_id': strategy_id}, message='策略删除成功')


@router.post('/api/strategies/start/{strategy_id}')
@handle_api_error
def start_strategy(strategy_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    strategy_data = convert_keys_to_snake(data)
    symbol = (strategy_data.get('symbol') or '').strip()
    if not symbol:
        return error_response({'success': False, 'error': '缺少必填参数: symbol'}, 400)
    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return error_response({'success': False, 'error': '策略不存在'}, 404)
    limit = int(strategy_data.get('limit', 100))
    chart_limit = strategy_data.get('chart_limit')
    chart_limit = int(chart_limit) if chart_limit is not None else None
    result = strategy_service.run_strategy(
        strategy_id=strategy_id, symbol=symbol, limit=limit, chart_limit=chart_limit)
    return api_response(result, message='策略运行成功')


@router.post('/api/strategies/stop/{strategy_id}')
@handle_api_error
def stop_strategy(strategy_id: str):
    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return error_response({'success': False, 'error': '策略不存在'}, 404)
    success = strategy_service.update_strategy(strategy_id=strategy_id, is_active=False)
    if not success:
        return error_response({'success': False, 'error': '策略停止失败'}, 500)
    strategy = strategy_service.get_strategy(strategy_id)
    return api_response(enrich_strategy_response(strategy), message='策略停止成功')


# ============ RESTful 别名（复用上述处理器，与 Flask 一致）============

@router.get('/api/strategies')
@handle_api_error
def get_strategies(source: str = Query('user'), category: Optional[str] = Query(None),
                   page: int = Query(1), pageSize: int = Query(20),
                   status: Optional[str] = Query(None), codeType: Optional[str] = Query(None)):
    return get_strategies_list(source, category, page, pageSize, status, codeType)


@router.post('/api/strategies')
@handle_api_error
def create_strategy_rest(payload: Optional[Dict[str, Any]] = Body(None)):
    return create_strategy(payload)


# ============ /{strategy_id} 参数路径（必须最后注册，避免吞掉 /list 等字面量）============

@router.get('/api/strategies/{strategy_id}')
@handle_api_error
def get_strategy(strategy_id: str):
    return get_strategy_detail(strategy_id)


@router.put('/api/strategies/{strategy_id}')
@handle_api_error
def update_strategy_rest(strategy_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    return update_strategy(strategy_id, payload)


@router.delete('/api/strategies/{strategy_id}')
@handle_api_error
def delete_strategy_rest(strategy_id: str):
    return delete_strategy(strategy_id)


@router.post('/api/strategies/{strategy_id}/enable')
@handle_api_error
def enable_strategy(strategy_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    return start_strategy(strategy_id, payload)


@router.post('/api/strategies/{strategy_id}/disable')
@handle_api_error
def disable_strategy(strategy_id: str):
    return stop_strategy(strategy_id)
