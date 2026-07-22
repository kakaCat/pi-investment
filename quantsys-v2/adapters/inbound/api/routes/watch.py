"""WatchEngine 盯盘规则 API（Flask，生产路径）"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository, rule_to_dict, trigger_to_dict,
)
from application.services.watch_engine.conditions import validate_condition

watch_bp = Blueprint('watch', __name__)

_rule_repo = WatchRuleRepository()
_trigger_repo = WatchTriggerRepository()


def _parse_expires_at(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


@watch_bp.route('/api/watch/rules', methods=['GET'])
def list_rules():
    symbol = request.args.get('symbol')
    enabled_arg = request.args.get('enabled')
    enabled = None if enabled_arg is None else enabled_arg.lower() == 'true'
    rules = _rule_repo.list_rules(symbol=symbol, enabled=enabled)
    return jsonify({'success': True, 'rules': [rule_to_dict(r) for r in rules]})


@watch_bp.route('/api/watch/rules', methods=['POST'])
def create_rule():
    data = request.get_json() or {}
    symbol = (data.get('symbol') or '').strip()
    conditions = data.get('conditions')
    if not symbol:
        return jsonify({'success': False, 'error': '缺少必填参数: symbol'}), 400
    if not conditions:
        return jsonify({'success': False, 'error': '缺少必填参数: conditions（非空数组）'}), 400
    try:
        for cond in conditions:
            validate_condition(cond)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    try:
        rule = _rule_repo.create_rule(
            symbol=symbol,
            conditions=conditions,
            context=data.get('context'),
            cost_price=data.get('cost_price'),
            active_window=data.get('active_window'),
            expires_at=_parse_expires_at(data.get('expires_at')),
            created_by=data.get('created_by', 'agent'),
        )
    except Exception as e:
        return jsonify({'success': False, 'error': f'创建失败: {e}'}), 500
    return jsonify({'success': True, 'rule': rule_to_dict(rule)})


@watch_bp.route('/api/watch/rules/<int:rule_id>', methods=['PUT', 'PATCH'])
def update_rule(rule_id):
    data = request.get_json() or {}
    if 'conditions' in data:
        try:
            for cond in data['conditions']:
                validate_condition(cond)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    if 'expires_at' in data:
        data['expires_at'] = _parse_expires_at(data['expires_at'])
    rule = _rule_repo.update_fields(rule_id, **data)
    if rule is None:
        return jsonify({'success': False, 'error': '规则不存在'}), 404
    return jsonify({'success': True, 'rule': rule_to_dict(rule)})


@watch_bp.route('/api/watch/rules/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    if _rule_repo.get_by_id(rule_id) is None:
        return jsonify({'success': False, 'error': '规则不存在'}), 404
    _rule_repo.delete_by_id(rule_id)
    return jsonify({'success': True})


@watch_bp.route('/api/watch/triggers', methods=['GET'])
def list_triggers():
    symbol = request.args.get('symbol')
    limit = min(int(request.args.get('limit', 50)), 200)
    triggers = _trigger_repo.list_by_symbol(symbol=symbol, limit=limit)
    return jsonify({'success': True, 'triggers': [trigger_to_dict(t) for t in triggers]})
