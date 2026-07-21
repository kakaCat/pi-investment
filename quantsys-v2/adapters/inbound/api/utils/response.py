"""
响应数据处理工具

提供API响应的通用数据转换和字段映射功能
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


def normalize_indicator_fields(indicators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    标准化指标字段，添加前端兼容的字段映射

    Args:
        indicators: 指标列表

    Returns:
        标准化后的指标列表

    Raises:
        TypeError: 如果输入不是列表
    """
    if not isinstance(indicators, list):
        raise TypeError(f"indicators must be a list, got {type(indicators).__name__}")

    normalized = []
    for indicator in indicators:
        if not isinstance(indicator, dict):
            continue

        # 创建副本避免修改原始数据
        normalized_indicator = indicator.copy()

        # 字段映射：strategy_name -> name
        if 'strategy_name' in normalized_indicator and 'name' not in normalized_indicator:
            normalized_indicator['name'] = normalized_indicator['strategy_name']

        # 字段映射：strategy_id -> id
        if 'strategy_id' in normalized_indicator and 'id' not in normalized_indicator:
            normalized_indicator['id'] = normalized_indicator['strategy_id']

        # 确保必需字段存在
        normalized_indicator.setdefault('name', 'Unnamed Indicator')
        normalized_indicator.setdefault('description', '')
        normalized_indicator.setdefault('category', 'custom')
        normalized_indicator.setdefault('author', 'unknown')
        normalized_indicator.setdefault('is_active', True)
        normalized_indicator.setdefault('is_public', False)
        normalized_indicator.setdefault('favorite_count', 0)
        normalized_indicator.setdefault('use_count', 0)

        # 时间戳格式化
        for time_field in ['created_at', 'updated_at']:
            if time_field in normalized_indicator:
                value = normalized_indicator[time_field]
                if isinstance(value, datetime):
                    normalized_indicator[time_field] = value.isoformat()
                elif value is None:
                    normalized_indicator[time_field] = None

        # 清理 None 值的数值字段
        for numeric_field in ['favorite_count', 'use_count']:
            if normalized_indicator.get(numeric_field) is None:
                normalized_indicator[numeric_field] = 0

        metadata = normalized_indicator.get('metadata')
        if isinstance(metadata, dict) and isinstance(metadata.get('notebook'), dict):
            normalized_indicator['notebook'] = metadata['notebook']

        # 解析 strategy_profile 并提取 tags
        strategy_profile = normalized_indicator.get('strategy_profile')
        if isinstance(strategy_profile, str):
            import json
            try:
                strategy_profile = json.loads(strategy_profile)
            except (json.JSONDecodeError, TypeError):
                strategy_profile = {}
        if not isinstance(strategy_profile, dict):
            strategy_profile = {}
        normalized_indicator['strategy_profile'] = strategy_profile
        normalized_indicator['tags'] = strategy_profile.get('tags') if isinstance(strategy_profile.get('tags'), list) else []

        # 添加类型标识
        normalized_indicator.setdefault('type', 'indicator')

        normalized.append(normalized_indicator)

    return normalized


def normalize_strategy_fields(strategies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    标准化策略字段，添加前端兼容的字段映射

    Args:
        strategies: 策略列表

    Returns:
        标准化后的策略列表

    Raises:
        TypeError: 如果输入不是列表
    """
    if not isinstance(strategies, list):
        raise TypeError(f"strategies must be a list, got {type(strategies).__name__}")

    normalized = []
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue

        # 创建副本避免修改原始数据
        normalized_strategy = strategy.copy()

        # 字段映射：strategy_name -> name
        if 'strategy_name' in normalized_strategy and 'name' not in normalized_strategy:
            normalized_strategy['name'] = normalized_strategy['strategy_name']

        # 字段映射：strategy_id -> id
        if 'strategy_id' in normalized_strategy and 'id' not in normalized_strategy:
            normalized_strategy['id'] = normalized_strategy['strategy_id']

        # 确保必需字段存在
        normalized_strategy.setdefault('name', 'Unnamed Strategy')
        normalized_strategy.setdefault('description', '')
        normalized_strategy.setdefault('category', 'custom')
        normalized_strategy.setdefault('author', 'unknown')
        normalized_strategy.setdefault('is_active', True)
        normalized_strategy.setdefault('is_public', False)
        normalized_strategy.setdefault('favorite_count', 0)
        normalized_strategy.setdefault('use_count', 0)

        # 时间戳格式化
        for time_field in ['created_at', 'updated_at']:
            if time_field in normalized_strategy:
                value = normalized_strategy[time_field]
                if isinstance(value, datetime):
                    normalized_strategy[time_field] = value.isoformat()
                elif value is None:
                    normalized_strategy[time_field] = None

        # 清理 None 值的数值字段
        for numeric_field in ['favorite_count', 'use_count']:
            if normalized_strategy.get(numeric_field) is None:
                normalized_strategy[numeric_field] = 0

        # 解析 strategy_profile 并提取 tags
        strategy_profile = normalized_strategy.get('strategy_profile')
        if isinstance(strategy_profile, str):
            import json
            try:
                strategy_profile = json.loads(strategy_profile)
            except (json.JSONDecodeError, TypeError):
                strategy_profile = {}
        if not isinstance(strategy_profile, dict):
            strategy_profile = {}
        normalized_strategy['strategy_profile'] = strategy_profile
        normalized_strategy['tags'] = strategy_profile.get('tags') if isinstance(strategy_profile.get('tags'), list) else []

        # is_active 必须为布尔值
        normalized_strategy['is_active'] = bool(normalized_strategy.get('is_active', True))

        # 添加类型标识
        normalized_strategy.setdefault('type', 'strategy')

        normalized.append(normalized_strategy)

    return normalized
