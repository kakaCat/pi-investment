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


def sanitize_for_json(obj, _depth=0, _seen=None):
    """递归清理对象，使其可以被 JSON 序列化

    2026-09-11（w-8f2c4cc5）加固。此前实现遇到未知类型直接 return obj，
    在 HTTP 响应边界造成两类 500（实证）：
      ① GET /api/backtest/results —— 元素是 BacktestResult（非 dict/list/dataclass，
         但有 to_dict），原样透传后 json.dumps 报
         Object of type BacktestResult is not JSON serializable；
      ② GET /api/signals —— opportunity 的 metadata 字段是 SQLAlchemy 的 MetaData
         （tables → Table → metadata 自引用环），透传给 FastAPI jsonable_encoder
         后无限递归 RecursionError → 500。
    现在：支持 to_dict()/dataclass/Enum/set/Decimal/bytes，加环检测与深度保护，
    最后兜底转 str —— 保证 sanitize 结果必然可 JSON 序列化。
    """
    import pandas as pd
    import numpy as np
    import dataclasses
    import decimal
    import enum

    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.integer, np.floating)):
        try:
            if np.isnan(obj) or np.isinf(obj):
                return None
        except (TypeError, ValueError):
            pass
        return obj.item()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, enum.Enum):
        return sanitize_for_json(obj.value, _depth, _seen)
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode('utf-8', 'replace')
    if isinstance(obj, (set, frozenset)):
        return sanitize_for_json(list(obj), _depth, _seen)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.DataFrame):
        return sanitize_for_json(obj.to_dict('records'), _depth, _seen)
    if isinstance(obj, pd.Series):
        return sanitize_for_json(obj.tolist(), _depth, _seen)
    if isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist(), _depth, _seen)
    # polars 支持（PySeries/PyDataFrame 默认不可 JSON 序列化）
    try:
        import polars as pl
        if isinstance(obj, pl.DataFrame):
            return sanitize_for_json(obj.to_dicts(), _depth, _seen)
        if isinstance(obj, pl.Series):
            return sanitize_for_json(obj.to_list(), _depth, _seen)
    except ImportError:
        pass

    # 环检测 + 深度保护：容器类才需要（标量在上方已返回）
    if _seen is None:
        _seen = set()
    if isinstance(obj, (dict, list, tuple)):
        if id(obj) in _seen:
            return None  # 自引用环 → 断链，避免 jsonable_encoder 无限递归
        if _depth >= 20:
            return None
        _seen = _seen | {id(obj)}
        if isinstance(obj, dict):
            return {
                sanitize_for_json(k, _depth + 1, _seen) if not isinstance(k, str) else k:
                    sanitize_for_json(v, _depth + 1, _seen)
                for k, v in obj.items()
            }
        return [sanitize_for_json(item, _depth + 1, _seen) for item in obj]

    if hasattr(obj, 'isoformat'):
        try:
            return obj.isoformat()
        except (TypeError, ValueError):
            return str(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        try:
            return sanitize_for_json(dataclasses.asdict(obj), _depth, _seen)
        except (TypeError, ValueError):
            return str(obj)
    to_dict = getattr(obj, 'to_dict', None)
    if callable(to_dict) and not isinstance(obj, type):
        try:
            return sanitize_for_json(to_dict(), _depth, _seen)
        except Exception:
            return str(obj)
    # 兜底：未知类型（含 SQLAlchemy MetaData 等带自引用环的对象）一律字符串化，
    # 宁可丢结构也不能让响应边界 500 / 递归爆栈。
    return str(obj)


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
