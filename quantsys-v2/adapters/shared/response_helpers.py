"""响应数据标准化工具（框架无关）— 从 adapters/inbound/api/utils/response.py 解耦而来"""
from typing import List, Dict, Any
from datetime import datetime


def _normalize_fields(items, entity_type: str, default_name: str):
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        n = item.copy()
        if 'strategy_name' in n and 'name' not in n:
            n['name'] = n['strategy_name']
        if 'strategy_id' in n and 'id' not in n:
            n['id'] = n['strategy_id']
        n.setdefault('name', default_name)
        n.setdefault('description', '')
        n.setdefault('category', 'custom')
        n.setdefault('author', 'unknown')
        n.setdefault('is_active', True)
        n.setdefault('is_public', False)
        n.setdefault('favorite_count', 0)
        n.setdefault('use_count', 0)
        for time_field in ['created_at', 'updated_at']:
            if time_field in n:
                value = n[time_field]
                if isinstance(value, datetime):
                    n[time_field] = value.isoformat()
                elif value is None:
                    n[time_field] = None
        for numeric_field in ['favorite_count', 'use_count']:
            if n.get(numeric_field) is None:
                n[numeric_field] = 0
        metadata = n.get('metadata')
        if entity_type == 'indicator' and isinstance(metadata, dict) and isinstance(metadata.get('notebook'), dict):
            n['notebook'] = metadata['notebook']
        strategy_profile = n.get('strategy_profile')
        if isinstance(strategy_profile, str):
            import json
            try:
                strategy_profile = json.loads(strategy_profile)
            except (json.JSONDecodeError, TypeError):
                strategy_profile = {}
        if not isinstance(strategy_profile, dict):
            strategy_profile = {}
        n['strategy_profile'] = strategy_profile
        n['tags'] = strategy_profile.get('tags') if isinstance(strategy_profile.get('tags'), list) else []
        if entity_type == 'strategy':
            n['is_active'] = bool(n.get('is_active', True))
        n.setdefault('type', entity_type)
        normalized.append(n)
    return normalized


def normalize_indicator_fields(indicators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """标准化指标字段（与 adapters/inbound/api/utils/response.py 一致）"""
    if not isinstance(indicators, list):
        raise TypeError(f"indicators must be a list, got {type(indicators).__name__}")
    return _normalize_fields(indicators, 'indicator', 'Unnamed Indicator')


def normalize_strategy_fields(strategies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """标准化策略字段（与 adapters/inbound/api/utils/response.py 一致）"""
    if not isinstance(strategies, list):
        raise TypeError(f"strategies must be a list, got {type(strategies).__name__}")
    return _normalize_fields(strategies, 'strategy', 'Unnamed Strategy')
