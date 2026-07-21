"""
watchlist routes.
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

watchlist_bp = Blueprint('watchlist', __name__)

@watchlist_bp.route('/api/stocks/watchlist/groups', methods=['GET'])
def get_watchlist_groups():
    """获取自选股分组列表"""
    groups_data = _read_groups()
    return jsonify({'success': True, 'groups': groups_data.get('groups', [])})


@watchlist_bp.route('/api/stocks/watchlist/groups', methods=['POST'])
def create_watchlist_group():
    """创建自选股分组"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': '分组名称不能为空'}), 400

    groups_data = _read_groups()
    new_group = {
        'id': str(uuid.uuid4())[:8],
        'name': name,
        'description': data.get('description', ''),
        'created_at': datetime.now().isoformat()
    }
    groups_data['groups'].append(new_group)
    _write_groups(groups_data)

    return jsonify({'success': True, 'group': new_group})


@watchlist_bp.route('/api/stocks/watchlist/groups/<group_id>', methods=['PUT'])
def update_watchlist_group(group_id):
    """更新自选股分组名称"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': '分组名称不能为空'}), 400

    groups_data = _read_groups()
    for group in groups_data.get('groups', []):
        if group['id'] == group_id:
            group['name'] = name
            if 'description' in data:
                group['description'] = data['description']
            group['updated_at'] = datetime.now().isoformat()
            _write_groups(groups_data)
            return jsonify({'success': True, 'group': group})

    return jsonify({'success': False, 'error': '分组不存在'}), 404


@watchlist_bp.route('/api/stocks/watchlist/groups/<group_id>', methods=['DELETE'])
def delete_watchlist_group(group_id):
    """删除自选股分组（同时清理该分组下的自选股）"""
    if group_id == 'default':
        return jsonify({'success': False, 'error': '不能删除默认分组'}), 400

    groups_data = _read_groups()
    original_len = len(groups_data.get('groups', []))
    groups_data['groups'] = [g for g in groups_data.get('groups', []) if g['id'] != group_id]

    if len(groups_data['groups']) == original_len:
        return jsonify({'success': False, 'error': '分组不存在'}), 404

    _write_groups(groups_data)

    wl = _read_watchlist()
    for item in wl.get('items', []):
        if item.get('group_id') == group_id:
            item['group_id'] = 'default'
    _write_watchlist(wl)

    return jsonify({'success': True, 'message': '分组已删除'})


@watchlist_bp.route('/api/stocks/watchlist/<symbol>/check', methods=['GET'])
def check_watchlist(symbol):
    """检查股票是否在自选股中"""
    wl = _read_watchlist()
    found = any(item['symbol'] == symbol for item in wl.get('items', []))
    return jsonify({'success': True, 'inWatchlist': found, 'symbol': symbol})


@watchlist_bp.route('/api/stocks/watchlist', methods=['POST'])
def add_to_watchlist():
    """添加股票到自选股"""
    data = request.get_json() or {}
    symbol = data.get('symbol', '').strip()
    if not symbol:
        return jsonify({'success': False, 'error': '股票代码不能为空'}), 400

    stock_info = ds.stock.get_by_symbol(symbol)
    if not stock_info:
        return jsonify({'success': False, 'error': f'股票不存在: {symbol}'}), 404

    wl = _read_watchlist()

    for item in wl.get('items', []):
        if item['symbol'] == symbol:
            return jsonify({'success': True, 'message': '已在自选股中', 'item': item})

    new_item = {
        'symbol': symbol,
        'name': stock_info.get('name', symbol),
        'market': stock_info.get('market', ''),
        'group_id': data.get('groupId', 'default'),
        'note': data.get('note', ''),
        'added_at': datetime.now().isoformat()
    }

    wl.setdefault('items', []).append(new_item)
    _write_watchlist(wl)

    return jsonify({'success': True, 'item': new_item, 'message': '已添加到自选股'})


@watchlist_bp.route('/api/stocks/watchlist/<symbol>', methods=['DELETE'])
def remove_from_watchlist(symbol):
    """从自选股移除股票"""
    wl = _read_watchlist()
    original_len = len(wl.get('items', []))
    wl['items'] = [item for item in wl.get('items', []) if item['symbol'] != symbol]

    if len(wl['items']) == original_len:
        return jsonify({'success': False, 'error': f'股票不在自选股中: {symbol}'}), 404

    _write_watchlist(wl)
    return jsonify({'success': True, 'message': f'已从自选股移除: {symbol}'})


@watchlist_bp.route('/api/stocks/watchlist', methods=['GET'])
def get_watchlist():
    """获取自选股列表"""
    group_id = request.args.get('groupId')
    wl = _read_watchlist()
    items = wl.get('items', [])
    if group_id:
        items = [item for item in items if item.get('group_id') == group_id]
    return jsonify({'success': True, 'items': items, 'count': len(items)})


