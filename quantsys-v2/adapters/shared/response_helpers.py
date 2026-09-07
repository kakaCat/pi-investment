# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""响应数据标准化工具（框架无关）— 从 adapters/inbound/api/utils/response.py 解耦而来"""
from typing import List, Dict, Any
from datetime import datetime


# TODO: Refactor - complexity 20 (target < 15)

def _validate__normalize_fields_input(data):
    """验证输入参数"""
    # TODO: 将验证逻辑从 _normalize_fields 移到这里
    return True, None

def _process__normalize_fields_data(data):
    """处理数据转换"""
    # TODO: 将数据处理逻辑从 _normalize_fields 移到这里
    return data

def _build__normalize_fields_result(data):
    """构建返回结果"""
    # TODO: 将结果构建逻辑从 _normalize_fields 移到这里
    return data

# TODO: Refactor - complexity 20 (target < 15)
# REFACTOR: Split this function into smaller pieces
def _check_condition_0():
    """Check: entity_type == 'indicator' and isinstance(metadata, dict) an..."""
    return entity_type == 'indicator' and isinstance(metadata, dict) and isinstance(metadata.get('notebook'), dict)

# TODO: Refactor - complexity 21 (target < 15)
# TODO: 复杂度 21 - 需要重构拆分为更小的函数

def _normalize_fields(items, entity_type: str, default_name: str):
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        n = item.copy()
        if 'strategy_name' in n and 'name' not in n and 'strategy_id' in n and 'id' not in n:
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
            # TODO: 提取嵌套逻辑为独立方法

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
        if entity_type == 'indicator' and isinstance(metadata, dict) and isinstance(metadata.get('notebook'), dict) and _check_condition_0():
            pass  # TODO: implement
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