"""
tools routes.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

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

tools_bp = Blueprint('tools', __name__)

@tools_bp.route('/api/tools/list', methods=['GET'])
@handle_api_error
def list_tools():
    """列出所有可用的 v2 命令（替代旧 quant_cli tools.list）"""
    from flask import current_app
    rules = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint != 'static':
            rules.append({
                'endpoint': rule.endpoint,
                'path': rule.rule,
                'methods': sorted(rule.methods - {'HEAD', 'OPTIONS'}),
            })
    rules.sort(key=lambda r: r['path'])
    return api_response({
        'success': True,
        'count': len(rules),
        'endpoints': rules,
    })


@tools_bp.route('/api/tools/describe', methods=['GET'])
@handle_api_error
def describe_tool():
    """描述单个 v2 命令（替代旧 quant_cli tools.describe）"""
    from flask import current_app

    # 支持两种查询方式：
    # 1. path=/api/strategies/create - 直接查询路由路径
    # 2. name=strategy.create - 通过命令名查询（需要映射到路由）
    path = request.args.get('path', '')
    name = request.args.get('name', '')

    # 命令名 → 路由路径映射表（从 quant-v2-client.ts V2_ROUTES 同步）
    COMMAND_TO_PATH = {
        'tools.list': '/api/tools/list',
        'tools.describe': '/api/tools/describe',
        'strategy.create': '/api/strategies/create',
        'strategy.list': '/api/strategies/list',
        'strategy.get': '/api/strategies/detail/{strategy_id}',
        'strategy.run': '/api/strategy/run',
        'strategy.status': '/api/strategy/status',
        'indicators.list': '/api/indicators/list',
        'indicators.detail': '/api/indicators/detail/{indicator_id}',
        'indicators.create': '/api/indicators/create',
        'indicators.update': '/api/indicators/update/{indicator_id}',
        'indicators.delete': '/api/indicators/delete/{indicator_id}',
        'indicators.run': '/api/indicators/run/{indicator_id}',
        'indicators.backtest': '/api/indicators/backtest',
        'indicators.compare': '/api/indicators/compare',
        'indicators.sandbox_columns': '/api/indicators/sandbox-columns',
        # 可以根据需要扩展更多映射
    }

    # 如果传了 name，先转换为 path
    if name and not path:
        path = COMMAND_TO_PATH.get(name, '')
        if not path:
            return jsonify({
                'success': False,
                'error': f'Unknown command name: {name}. Use path parameter for direct route lookup.'
            }), 404

    if not path:
        return jsonify({
            'success': False,
            'error': 'Missing required parameter: path or name'
        }), 400

    # 查找匹配的路由（支持路径参数占位符）
    for rule in current_app.url_map.iter_rules():
        # 精确匹配或模式匹配（处理 {param} 占位符）
        if rule.rule == path or ('{' in path and rule.rule.replace('<', '{').replace('>', '}').split(':')[-1] == path):
            return api_response({
                'success': True,
                'endpoint': rule.endpoint,
                'path': rule.rule,
                'methods': sorted(rule.methods - {'HEAD', 'OPTIONS'}),
            })

    return jsonify({'success': False, 'error': f'No endpoint matches path: {path}'}), 404


