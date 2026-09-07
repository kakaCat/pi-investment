"""JSON 序列化与命名转换工具（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来"""
import math
from typing import Any


def _safe_float(value, default=0.0, decimals=None):
    """安全转换为浮点数"""
    if value is None:
        return default
    try:
        result = float(value)
        return round(result, decimals) if decimals is not None else result
    except (ValueError, TypeError):
        return default


def sanitize_for_json(obj):
    """递归清理对象，使其可以被JSON序列化"""
    import pandas as pd
    import numpy as np

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.integer, np.floating)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj.item()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.DataFrame):
        return sanitize_for_json(obj.to_dict('records'))
    if isinstance(obj, pd.Series):
        return sanitize_for_json(obj.tolist())
    if isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    # polars 支持（PySeries/PyDataFrame 默认不可 JSON 序列化）
    try:
        import polars as pl
        if isinstance(obj, pl.DataFrame):
            return sanitize_for_json(obj.to_dicts())
        if isinstance(obj, pl.Series):
            return sanitize_for_json(obj.to_list())
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {
            sanitize_for_json(k) if not isinstance(k, str) else k: sanitize_for_json(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


def to_camel_case(snake_str: str) -> str:
    """将蛇形命名转换为驼峰命名"""
    if not isinstance(snake_str, str):
        return snake_str
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def to_snake_case(camel_str: str) -> str:
    """将驼峰命名转换为蛇形命名"""
    import re
    if not isinstance(camel_str, str):
        return camel_str
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()


def convert_keys_to_camel(obj: Any) -> Any:
    """递归将字典的key转换为驼峰命名"""
    import pandas as pd
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str):
                new_key = to_camel_case(k)
            elif isinstance(k, pd.Timestamp):
                new_key = k.isoformat()
            elif hasattr(k, 'isoformat'):
                new_key = k.isoformat()
            else:
                new_key = str(k)
            result[new_key] = convert_keys_to_camel(v)
        return result
    elif isinstance(obj, list):
        return [convert_keys_to_camel(item) for item in obj]
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


def convert_keys_to_snake(obj: Any) -> Any:
    """递归将字典的key转换为蛇形命名"""
    import pandas as pd
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str):
                new_key = to_snake_case(k)
            elif isinstance(k, pd.Timestamp):
                new_key = k.isoformat()
            elif hasattr(k, 'isoformat'):
                new_key = k.isoformat()
            else:
                new_key = str(k)
            result[new_key] = convert_keys_to_snake(v)
        return result
    elif isinstance(obj, list):
        return [convert_keys_to_snake(item) for item in obj]
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj
