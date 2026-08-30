"""WatchEngine 盯盘规则 API - FastAPI 版（与 Flask watch.py 响应契约一致）"""
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository, rule_to_dict, trigger_to_dict,
)
from application.services.watch_engine.conditions import validate_condition

router = APIRouter(tags=['Watch - 实时盯盘'])

EXPIRES_AT_ERROR = 'expires_at 格式无效（需 ISO 格式，如 2026-07-25T15:00:00）'


def _err(message: str, status: int) -> JSONResponse:
    return JSONResponse({'success': False, 'error': message}, status_code=status)


def _parse_expires_at(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


@router.get('/api/watch/rules')
def list_rules(symbol: Optional[str] = Query(None), enabled: Optional[str] = Query(None)):
    rule_repo = WatchRuleRepository()
    enabled_value = None if enabled is None else enabled.lower() == 'true'
    rules = rule_repo.list_rules(symbol=symbol, enabled=enabled_value)
    return {'success': True, 'data': {'rules': [rule_to_dict(r) for r in rules]}}


@router.post('/api/watch/rules')
def create_rule(payload: Dict[str, Any] = Body(default_factory=dict)):
    data = payload or {}
    symbol = (data.get('symbol') or '').strip()
    conditions = data.get('conditions')
    if not symbol:
        return _err('缺少必填参数: symbol', 400)
    if not conditions:
        return _err('缺少必填参数: conditions（非空数组）', 400)
    if not isinstance(conditions, list):
        return _err('conditions 必须为数组', 400)
    try:
        for cond in conditions:
            validate_condition(cond)
    except ValueError as e:
        return _err(str(e), 400)
    try:
        expires_at = _parse_expires_at(data.get('expires_at'))
    except ValueError:
        return _err(EXPIRES_AT_ERROR, 400)
    try:
        rule_repo = WatchRuleRepository()
        rule = rule_repo.create_rule(
            symbol=symbol,
            conditions=conditions,
            context=data.get('context'),
            cost_price=data.get('cost_price'),
            active_window=data.get('active_window'),
            expires_at=expires_at,
            created_by=data.get('created_by', 'agent'),
        )
    except Exception as e:
        return _err(f'创建失败: {e}', 500)
    return {'success': True, 'data': {'rule': rule_to_dict(rule)}}


def _update_rule(rule_id: int, payload: Dict[str, Any]):
    rule_repo = WatchRuleRepository()
    data = dict(payload or {})
    if 'conditions' in data:
        if not isinstance(data['conditions'], list):
            return _err('conditions 必须为数组', 400)
        try:
            for cond in data['conditions']:
                validate_condition(cond)
        except ValueError as e:
            return _err(str(e), 400)
    if 'expires_at' in data:
        try:
            data['expires_at'] = _parse_expires_at(data['expires_at'])
        except ValueError:
            return _err(EXPIRES_AT_ERROR, 400)
    rule = rule_repo.update_fields(rule_id, **data)
    if rule is None:
        return _err('规则不存在', 404)
    return {'success': True, 'data': {'rule': rule_to_dict(rule)}}


@router.put('/api/watch/rules/{rule_id}')
def update_rule_put(rule_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    return _update_rule(rule_id, payload)


@router.patch('/api/watch/rules/{rule_id}')
def update_rule_patch(rule_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    return _update_rule(rule_id, payload)


@router.delete('/api/watch/rules/{rule_id}')
def delete_rule(rule_id: int):
    rule_repo = WatchRuleRepository()
    if rule_repo.get_by_id(rule_id) is None:
        return _err('规则不存在', 404)
    rule_repo.delete_by_id(rule_id)
    return {'success': True}


@router.get('/api/watch/triggers')
def list_triggers(symbol: Optional[str] = Query(None), limit: Optional[str] = Query(None)):
    trigger_repo = WatchTriggerRepository()
    try:
        limit_value = int(limit) if limit is not None else 50
    except (TypeError, ValueError):
        limit_value = 50
    limit_value = max(1, min(limit_value, 200))
    triggers = trigger_repo.list_by_symbol(symbol=symbol, limit=limit_value)
    return {'success': True, 'data': {'triggers': [trigger_to_dict(t) for t in triggers]}}
