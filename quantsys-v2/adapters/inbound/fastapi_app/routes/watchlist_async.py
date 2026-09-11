"""自选股 API - FastAPI 版（从 Flask watchlist.py 迁移，响应契约保持一致）"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    ds, error_response, _read_watchlist, _write_watchlist, _read_groups, _write_groups,
    stock_repo,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Watchlist - 自选股"])


@router.get('/api/stocks/watchlist/groups')
def get_watchlist_groups():
    groups_data = _read_groups()
    return {'success': True, 'groups': groups_data.get('groups', [])}


@router.post('/api/stocks/watchlist/groups')
def create_watchlist_group(payload: Dict[str, Any] = Body(default_factory=dict)):
    name = (payload.get('name') or '').strip()
    if not name:
        return error_response({'success': False, 'error': '分组名称不能为空'}, 400)
    groups_data = _read_groups()
    new_group = {
        'id': str(uuid.uuid4())[:8],
        'name': name,
        'description': payload.get('description', ''),
        'created_at': datetime.now().isoformat(),
    }
    groups_data['groups'].append(new_group)
    _write_groups(groups_data)
    return {'success': True, 'group': new_group}


@router.put('/api/stocks/watchlist/groups/{group_id}')
def update_watchlist_group(group_id: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    name = (payload.get('name') or '').strip()
    if not name:
        return error_response({'success': False, 'error': '分组名称不能为空'}, 400)
    groups_data = _read_groups()
    for group in groups_data.get('groups', []):
        if group['id'] == group_id:
            group['name'] = name
            if 'description' in payload:
                group['description'] = payload['description']
            group['updated_at'] = datetime.now().isoformat()
            _write_groups(groups_data)
            return {'success': True, 'group': group}
    return error_response({'success': False, 'error': '分组不存在'}, 404)


@router.delete('/api/stocks/watchlist/groups/{group_id}')
def delete_watchlist_group(group_id: str):
    if group_id == 'default':
        return error_response({'success': False, 'error': '不能删除默认分组'}, 400)
    groups_data = _read_groups()
    original_len = len(groups_data.get('groups', []))
    groups_data['groups'] = [g for g in groups_data.get('groups', []) if g['id'] != group_id]
    if len(groups_data['groups']) == original_len:
        return error_response({'success': False, 'error': '分组不存在'}, 404)
    _write_groups(groups_data)
    wl = _read_watchlist()
    for item in wl.get('items', []):
        if item.get('group_id') == group_id:
            item['group_id'] = 'default'
    _write_watchlist(wl)
    return {'success': True, 'message': '分组已删除'}


@router.get('/api/stocks/watchlist/{symbol}/check')
def check_watchlist(symbol: str):
    wl = _read_watchlist()
    found = any(item['symbol'] == symbol for item in wl.get('items', []))
    return {'success': True, 'inWatchlist': found, 'symbol': symbol}


@router.post('/api/stocks/watchlist')
def add_to_watchlist(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = (payload.get('symbol') or '').strip()
    if not symbol:
        return error_response({'success': False, 'error': '股票代码不能为空'}, 400)
    stock_info = stock_repo.get_by_symbol(symbol)
    if not stock_info:
        return error_response({'success': False, 'error': f'股票不存在: {symbol}'}, 404)
    wl = _read_watchlist()
    for item in wl.get('items', []):
        if item['symbol'] == symbol:
            return {'success': True, 'message': '已在自选股中', 'item': item}
    # 2026-09-11 修复（w-aebfddcd 代 w-348bf585 处理）：stock_repo.get_by_symbol 返回的是
    # **ORM 对象（Stock）**而非 dict——原代码 stock_info.get(...) 直接抛
    # AttributeError: 'Stock' object has no attribute 'get'，导致 POST /api/stocks/watchlist
    # 线上恒 500（自选股加不进去）。统一用 _field() 取值，兼容 ORM 对象与 dict 两种返回。
    def _field(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    new_item = {
        'symbol': symbol,
        'name': _field(stock_info, 'name', symbol),
        'market': _field(stock_info, 'market', ''),
        'group_id': payload.get('groupId', 'default'),
        'note': payload.get('note', ''),
        'added_at': datetime.now().isoformat(),
    }
    wl.setdefault('items', []).append(new_item)
    _write_watchlist(wl)
    return {'success': True, 'item': new_item, 'message': '已添加到自选股'}


@router.delete('/api/stocks/watchlist/{symbol}')
def remove_from_watchlist(symbol: str):
    wl = _read_watchlist()
    original_len = len(wl.get('items', []))
    wl['items'] = [i for i in wl.get('items', []) if i['symbol'] != symbol]
    if len(wl['items']) == original_len:
        return error_response({'success': False, 'error': f'股票不在自选股中: {symbol}'}, 404)
    _write_watchlist(wl)
    return {'success': True, 'message': f'已从自选股移除: {symbol}'}


@router.get('/api/stocks/watchlist')
def get_watchlist(groupId: Optional[str] = Query(None)):
    wl = _read_watchlist()
    items = wl.get('items', [])
    if groupId:
        items = [i for i in items if i.get('group_id') == groupId]
    return {'success': True, 'items': items, 'count': len(items)}
