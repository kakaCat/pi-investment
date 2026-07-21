"""
strategies routes.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid
from typing import Dict, List, Optional, Any

from flask import Blueprint, jsonify, request

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
from application.services.strategy_validation_service import StrategyValidationService
from application.services.strategy_optimizer import StrategyOptimizer
from application.services.search_space import SearchSpace
from domain.quantlib.engine.strategy_factory import StrategyFactory

strategies_bp = Blueprint('strategies', __name__)

# Initialize validation service
validation_service = StrategyValidationService()

def enrich_strategy_response(strategy: Dict) -> Dict:
    """
    丰富策略响应数据，添加前端需要的字段

    将后端数据库结构转换为前端期望的格式：
    - code_type -> type (映射到前端策略类型)
    - status -> status (映射到前端状态)
    - 添加 performance 和 positions 字段（需要单独查询）

    Args:
        strategy: 后端策略数据

    Returns:
        enriched: 前端期望的策略数据格式
    """
    type_mapping = {
        'strategy': 'trend',
        'indicator': 'momentum',
        'script': 'arbitrage'
    }

    status_mapping = {
        'valid': 'stopped',      # 有效但未运行
        'invalid': 'error',      # 验证失败
        'stopped': 'stopped',    # 已停止
        'running': 'running',    # 运行中
        'paused': 'paused'       # 已暂停
    }

    validation_status = strategy.get('validation_status', strategy.get('status', 'valid'))

    # 解析 strategy_profile（可能是 JSON 字符串或已解析的 dict）
    strategy_profile = strategy.get('strategy_profile')
    if isinstance(strategy_profile, str):
        try:
            strategy_profile = json.loads(strategy_profile)
        except (json.JSONDecodeError, TypeError):
            strategy_profile = {}
    if not isinstance(strategy_profile, dict):
        strategy_profile = {}

    enriched = {
        'id': str(strategy.get('id')),
        'name': strategy.get('strategy_name'),  # 使用 strategy_name 字段
        'strategy_type': strategy.get('strategy_type'),  # 保留原始 strategy_type 字段供 ID 转换使用
        'type': type_mapping.get(strategy.get('code_type'), 'trend'),
        'status': status_mapping.get(validation_status, 'stopped'),
        'description': strategy.get('description'),
        'code': strategy.get('code_content'),
        'params': strategy.get('parsed_params'),
        'is_active': strategy.get('is_active', True),
        'validation_status': strategy.get('validation_status', 'unvalidated'),
        'strategy_profile': strategy_profile,
        'tags': strategy_profile.get('tags', []) if isinstance(strategy_profile.get('tags'), list) else [],
        'performance': None,  # 需要单独查询回测结果
        'positions': 0,       # 需要单独查询持仓数量
        'created_at': strategy.get('created_at'),
        'updated_at': strategy.get('updated_at'),
        'last_executed': strategy.get('last_executed')
    }

    return enriched


def is_active_strategy(strategy: Dict) -> bool:
    """Treat missing is_active as active for legacy/builtin records."""
    return strategy.get('is_active', True) is not False


@strategies_bp.route('/api/strategies/list', methods=['GET'])
@handle_api_error
def get_strategies_list():
    """
    获取策略列表

    支持两种模式：
    1. 不带 source 参数或 source=user：返回用户自定义策略（原有行为）
    2. source=builtin：返回 StrategyFactory 的 18 种内置策略
    """
    source = request.args.get('source', 'user')  # 'user' | 'builtin'

    if source == 'builtin':
        # 返回 StrategyFactory 的内置策略
        from domain.quantlib.engine.strategy_factory import StrategyFactory

        # 确保策略已注册
        if not StrategyFactory._registry:
            StrategyFactory.auto_discover()

        # 获取所有策略元数据
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

        # 支持按分类过滤
        category = request.args.get('category')
        if category:
            strategies = [s for s in strategies if s['category'] == category]

        return api_response({
            'strategies': strategies,
            'total': len(strategies)
        })

    # 原有逻辑：返回用户自定义策略
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    status = request.args.get('status')
    code_type = request.args.get('codeType')  # 'indicator' | 'script' | None (all)

    if code_type and code_type not in ('indicator', 'script', 'strategy'):
        return jsonify({'success': False, 'error': f'无效的 code_type: {code_type}，必须是 indicator、script 或 strategy'}), 400

    strategies = strategy_service.list_strategies(code_type=code_type, active_only=True)
    strategies = [s for s in strategies if is_active_strategy(s)]

    if status:
        strategies = [s for s in strategies if s.get('status') == status]

    enriched_strategies = [enrich_strategy_response(s) for s in strategies]

    total = len(enriched_strategies)
    offset = (page - 1) * page_size
    strategies_page = enriched_strategies[offset:offset + page_size]

    return api_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': strategies_page
    })


@strategies_bp.route('/api/strategies/detail/<strategy_id>', methods=['GET'])
@handle_api_error
def get_strategy_detail(strategy_id):
    """获取策略详情"""
    strategy = strategy_service.get_strategy(strategy_id)

    if not strategy:
        return jsonify({'success': False, 'error': '策略不存在'}), 404

    enriched_strategy = enrich_strategy_response(strategy)

    return api_response(enriched_strategy)


@strategies_bp.route('/api/strategies/create', methods=['POST'])
@handle_api_error
def create_strategy():
    """创建策略"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400

    strategy_data = convert_keys_to_snake(data)

    if 'name' not in strategy_data:
        return jsonify({'success': False, 'error': '缺少必需参数: name'}), 400
    if 'code' not in strategy_data:
        return jsonify({'success': False, 'error': '缺少必需参数: code'}), 400

    code_type = strategy_data.get('code_type', 'indicator')
    if code_type not in ('indicator', 'script', 'strategy'):
        return jsonify({'success': False, 'error': f'无效的策略类型: {code_type}，必须是 indicator、script 或 strategy'}), 400

    result = strategy_service.create_strategy(
        name=strategy_data['name'],
        code=strategy_data['code'],
        code_type=code_type,
        description=strategy_data.get('description'),
        params=strategy_data.get('params')
    )

    strategy = strategy_service.get_strategy(result['strategy_id'])

    enriched_strategy = enrich_strategy_response(strategy)

    return api_response(enriched_strategy, message='策略创建成功')


@strategies_bp.route('/api/strategies/update/<strategy_id>', methods=['POST'])
@handle_api_error
def update_strategy(strategy_id):
    """更新策略"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400

    strategy_data = convert_keys_to_snake(data)

    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return jsonify({'success': False, 'error': '策略不存在'}), 404

    # 验证 code_type（如果提供）
    code_type = strategy_data.get('code_type')
    if code_type and code_type not in ('indicator', 'script'):
        return jsonify({'success': False, 'error': f'无效的策略类型: {code_type}，必须是 indicator 或 script'}), 400

    success = strategy_service.update_strategy(
        strategy_id=strategy_id,
        name=strategy_data.get('name'),
        code=strategy_data.get('code'),
        code_type=code_type,
        description=strategy_data.get('description'),
        params=strategy_data.get('params')
    )

    if not success:
        return jsonify({'success': False, 'error': '策略更新失败'}), 500

    strategy = strategy_service.get_strategy(strategy_id)

    enriched_strategy = enrich_strategy_response(strategy)

    return api_response(enriched_strategy, message='策略更新成功')


@strategies_bp.route('/api/strategies/delete/<strategy_id>', methods=['POST'])
@handle_api_error
def delete_strategy(strategy_id):
    """删除策略（软删除）"""
    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return jsonify({'success': False, 'error': '策略不存在'}), 404

    success = strategy_service.delete_strategy(strategy_id)

    if not success:
        return jsonify({'success': False, 'error': '策略删除失败'}), 500

    return api_response({'strategy_id': strategy_id}, message='策略删除成功')


@strategies_bp.route('/api/strategies/start/<strategy_id>', methods=['POST'])
@handle_api_error
def start_strategy(strategy_id):
    """
    运行策略生成实时信号

    Request body:
    {
        "symbol": "600737.SH",  // 必填：股票代码
        "limit": 120            // 可选：K线数量，默认100
    }

    Returns:
    {
        "symbol": "600737.SH",
        "latest_signal": "buy" | "sell" | "hold",
        "confidence": 0.8,
        "price": 12.50,
        "date": "2026-06-01",
        "indicators": {...}
    }
    """
    data = request.get_json() or {}
    strategy_data = convert_keys_to_snake(data)

    symbol = strategy_data.get('symbol', '').strip()
    if not symbol:
        return jsonify({'success': False, 'error': '缺少必填参数: symbol'}), 400

    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return jsonify({'success': False, 'error': '策略不存在'}), 404

    limit = int(strategy_data.get('limit', 100))
    chart_limit = strategy_data.get('chart_limit')
    chart_limit = int(chart_limit) if chart_limit is not None else None

    result = strategy_service.run_strategy(
        strategy_id=strategy_id,
        symbol=symbol,
        limit=limit,
        chart_limit=chart_limit
    )

    return api_response(result, message='策略运行成功')


@strategies_bp.route('/api/strategies/stop/<strategy_id>', methods=['POST'])
@handle_api_error
def stop_strategy(strategy_id):
    """停止策略"""
    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return jsonify({'success': False, 'error': '策略不存在'}), 404

    success = strategy_service.update_strategy(
        strategy_id=strategy_id,
        is_active=False
    )

    if not success:
        return jsonify({'success': False, 'error': '策略停止失败'}), 500

    strategy = strategy_service.get_strategy(strategy_id)

    enriched_strategy = enrich_strategy_response(strategy)

    return api_response(enriched_strategy, message='策略停止成功')

@strategies_bp.route('/api/strategies/optimize', methods=['POST'])
def optimize_strategy():
    """
    优化策略参数

    使用真实回测进行参数网格搜索，返回按 Sharpe 排序的最优参数组合。

    Request:
        {
            "strategyId": 1,
            "symbol": "600000.SH",
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
            "paramRanges": {
                "fast": [5, 10, 20],
                "slow": [20, 50, 60]
            },
            "initialCash": 1000000,
            "sortBy": "sharpe_ratio"
        }

    Response:
        {
            "success": true,
            "results": [
                {
                    "params": {"fast": 10, "slow": 30},
                    "sharpeRatio": 2.0,
                    "totalReturn": 0.15,
                    "maxDrawdown": -0.08,
                    "winRate": 0.65,
                    "totalTrades": 45
                },
                ...
            ],
            "totalCombinations": 9,
            "successfulCombinations": 8
        }
    """
    try:
        # Parse request
        data = request.get_json()
        strategy_id = data.get('strategyId')
        symbol = data.get('symbol')
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        param_ranges = data.get('paramRanges')
        initial_cash = data.get('initialCash', 1000000)
        sort_by = data.get('sortBy', 'sharpe_ratio')
        period = data.get('period')  # None=日线, '5min'/'15min'/'30min'=分钟线

        # Validate required fields
        if not all([strategy_id, symbol, start_date, end_date, param_ranges]):
            return jsonify({
                'success': False,
                'error': "strategyId, symbol, startDate, endDate, and paramRanges are required"
            }), 400

        # Validate param_ranges is not empty
        if not param_ranges or not isinstance(param_ranges, dict):
            return jsonify({
                'success': False,
                'error': "paramRanges must be a non-empty dictionary"
            }), 400

        # Generate parameter grid
        search_space = SearchSpace(param_ranges)
        param_grid = search_space.generate_grid()

        if not param_grid:
            return jsonify({
                'success': False,
                'error': "Generated parameter grid is empty"
            }), 400

        # Run optimization
        optimizer = StrategyOptimizer(strategy_service)
        results = optimizer.optimize(
            strategy_id=strategy_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            param_grid=param_grid,
            initial_cash=initial_cash,
            sort_by=sort_by,
            period=period
        )

        # Convert to camelCase for frontend
        camel_results = []
        for result in results:
            camel_result = {
                'params': result['params'],
                'sharpeRatio': result.get('sharpe_ratio'),
                'totalReturn': result.get('total_return'),
                'maxDrawdown': result.get('max_drawdown'),
                'winRate': result.get('win_rate'),
                'totalTrades': result.get('total_trades')
            }
            camel_results.append(camel_result)

        return jsonify({
            'success': True,
            'results': camel_results,
            'totalCombinations': len(param_grid),
            'successfulCombinations': len(results)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@strategies_bp.route('/api/strategies', methods=['GET'])
@handle_api_error
def get_strategies():
    """获取策略列表（RESTful 路径，兼容前端）"""
    return get_strategies_list()


@strategies_bp.route('/api/strategies/<strategy_id>', methods=['GET'])
@handle_api_error
def get_strategy(strategy_id):
    """获取策略详情（RESTful 路径，兼容前端）"""
    return get_strategy_detail(strategy_id)


@strategies_bp.route('/api/strategies', methods=['POST'])
@handle_api_error
def create_strategy_rest():
    """创建策略（RESTful 路径，兼容前端）"""
    return create_strategy()


@strategies_bp.route('/api/strategies/<strategy_id>', methods=['PUT'])
@handle_api_error
def update_strategy_rest(strategy_id):
    """更新策略（RESTful 路径，兼容前端）"""
    return update_strategy(strategy_id)


@strategies_bp.route('/api/strategies/<strategy_id>', methods=['DELETE'])
@handle_api_error
def delete_strategy_rest(strategy_id):
    """删除策略（RESTful 路径，兼容前端）"""
    return delete_strategy(strategy_id)


@strategies_bp.route('/api/strategies/<strategy_id>/enable', methods=['POST'])
@handle_api_error
def enable_strategy(strategy_id):
    """启用策略（RESTful 路径，兼容前端）"""
    return start_strategy(strategy_id)


@strategies_bp.route('/api/strategies/<strategy_id>/disable', methods=['POST'])
@handle_api_error
def disable_strategy(strategy_id):
    """停止策略（RESTful 路径，兼容前端）"""
    return stop_strategy(strategy_id)


@strategies_bp.route('/api/strategies/performance/<strategy_id>', methods=['GET'])
@handle_api_error
def get_strategy_performance_detail(strategy_id):
    """获取策略绩效"""
    existing = strategy_service.get_strategy(strategy_id)
    if not existing:
        return jsonify({'success': False, 'error': '策略不存在'}), 404

    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')

    if start_date and end_date:
        backtest_results = ds.backtest.get_backtests_by_strategy(strategy_id, limit=200)
        backtest_results = [
            b for b in backtest_results
            if b.get('start_date') and start_date <= str(b.get('start_date'))[:10] <= end_date
        ]
    else:
        backtest_results = ds.backtest.get_backtests_by_strategy(strategy_id, limit=50)

    stats = ds.backtest.get_backtest_stats(strategy_name=strategy_id)

    executions = []
    try:
        all_executions = ds.execution.get_all_executions(limit=200)
        executions = [e for e in all_executions if e.get('strategy_id') == strategy_id]

        if start_date and end_date:
            executions = [
                e for e in executions
                if e.get('created_at') and start_date <= str(e.get('created_at'))[:10] <= end_date
            ]
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
        'date_range': {
            'start_date': start_date,
            'end_date': end_date
        } if start_date and end_date else None
    }

    return api_response(performance_data)


@strategies_bp.route('/api/strategies/validate', methods=['POST'])
@handle_api_error
def validate_strategies():
    """
    批量验证所有策略

    Request:
        {
            "startDate": "2024-05-27",
            "endDate": "2026-05-27",
            "threshold": 60,
            "dryRun": false
        }

    Response:
        {
            "success": true,
            "data": {
                "total": 50,
                "passed": 32,
                "failed": 18,
                "duration": 1847,
                "details": [...]
            }
        }
    """
    # Parse request
    data = request.get_json()
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    threshold = data.get('threshold', 60.0)
    dry_run = data.get('dryRun', False)

    # Validate inputs
    if not start_date or not end_date:
        return api_response(
            success=False,
            message="startDate and endDate are required"
        ), 400

    # Call validation service
    result = validation_service.validate_all_strategies(
        start_date=start_date,
        end_date=end_date,
        threshold=threshold,
        dry_run=dry_run
    )

    return api_response(
        success=True,
        data=result
    )
    # Errors propagate to the @handle_api_error decorator, which logs the full
    # traceback and returns a 500 with the real message.
