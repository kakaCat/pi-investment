"""
Output Formatters

CLI输出格式化工具，支持JSON、表格、简洁文本等格式。
"""

import json
import math
from typing import Any, Dict, List, Optional
from datetime import datetime


class Formatter:
    """格式化器基类"""

    def format(self, data: Any) -> str:
        """格式化数据"""
        raise NotImplementedError


class JSONFormatter(Formatter):
    """JSON格式化器"""

    def __init__(self, pretty: bool = True):
        self.pretty = pretty

    def format(self, data: Any) -> str:
        """格式化为JSON"""
        indent = 2 if self.pretty else None
        return json.dumps(
            self._clean(data),
            indent=indent,
            ensure_ascii=False,
            default=str
        )

    def _clean(self, obj):
        """清理不可序列化的对象"""
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._clean(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._clean(i) for i in obj]
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return obj


class TableFormatter(Formatter):
    """表格格式化器"""

    def format(self, data: Any) -> str:
        """格式化为表格"""
        if isinstance(data, dict):
            # 单个对象，显示为键值对
            return self._format_dict(data)
        elif isinstance(data, list) and data:
            # 列表，显示为表格
            if isinstance(data[0], dict):
                return self._format_table(data)
            else:
                return self._format_list(data)
        else:
            return str(data)

    def _format_dict(self, data: Dict) -> str:
        """格式化字典为键值对"""
        lines = []
        max_key_len = max(len(str(k)) for k in data.keys()) if data else 0

        for key, value in data.items():
            key_str = str(key).ljust(max_key_len)
            value_str = self._format_value(value)
            lines.append(f"{key_str} : {value_str}")

        return "\n".join(lines)

    def _format_table(self, data: List[Dict]) -> str:
        """格式化为表格"""
        if not data:
            return ""

        # 获取所有列
        columns = list(data[0].keys())

        # 计算列宽
        col_widths = {}
        for col in columns:
            col_widths[col] = max(
                len(str(col)),
                max(len(self._format_value(row.get(col, ''))) for row in data)
            )

        # 构建表头
        header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
        separator = "-+-".join("-" * col_widths[col] for col in columns)

        # 构建数据行
        rows = []
        for row in data:
            row_str = " | ".join(
                self._format_value(row.get(col, '')).ljust(col_widths[col])
                for col in columns
            )
            rows.append(row_str)

        return "\n".join([header, separator] + rows)

    def _format_list(self, data: List) -> str:
        """格式化列表"""
        return "\n".join(f"- {self._format_value(item)}" for item in data)

    def _format_value(self, value: Any) -> str:
        """格式化单个值"""
        if value is None:
            return ""
        elif isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return ""
            return f"{value:.2f}"
        elif isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        else:
            return str(value)


class CompactFormatter(Formatter):
    """简洁格式化器"""

    def format(self, data: Any) -> str:
        """格式化为简洁文本"""
        if isinstance(data, dict):
            return self._format_dict(data)
        elif isinstance(data, list):
            return self._format_list(data)
        else:
            return str(data)

    def _format_dict(self, data: Dict, indent: int = 0) -> str:
        """格式化字典"""
        lines = []
        prefix = "  " * indent

        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_dict(value, indent + 1))
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                lines.append(f"{prefix}{key}: ({len(value)} items)")
            else:
                value_str = self._format_value(value)
                lines.append(f"{prefix}{key}: {value_str}")

        return "\n".join(lines)

    def _format_list(self, data: List) -> str:
        """格式化列表"""
        if not data:
            return "(empty)"

        if isinstance(data[0], dict):
            return f"({len(data)} items)\n" + "\n---\n".join(
                self._format_dict(item) for item in data[:5]
            )
        else:
            return ", ".join(self._format_value(item) for item in data[:10])

    def _format_value(self, value: Any) -> str:
        """格式化单个值"""
        if value is None:
            return "-"
        elif isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return "-"
            return f"{value:.2f}"
        elif isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        else:
            return str(value)


def get_formatter(format_type: str = "json", **kwargs) -> Formatter:
    """
    获取格式化器

    Args:
        format_type: 格式类型 (json/table/compact)
        **kwargs: 格式化器参数

    Returns:
        Formatter实例
    """
    if format_type == "json":
        return JSONFormatter(**kwargs)
    elif format_type == "table":
        return TableFormatter(**kwargs)
    elif format_type == "compact":
        return CompactFormatter(**kwargs)
    else:
        return JSONFormatter(**kwargs)
