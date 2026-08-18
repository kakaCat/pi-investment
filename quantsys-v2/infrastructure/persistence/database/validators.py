"""纯函数校验器（自 legacy BaseRepository 抽出，无 DB 依赖）。

错误消息文案与 legacy BaseRepository._validate_* 逐字一致——
调用方（含 agent 工具层）可能匹配这些文案。
"""
from datetime import datetime


def validate_symbol(symbol: str) -> bool:
    if not symbol:
        raise ValueError("股票代码不能为空")
    if not isinstance(symbol, str):
        raise ValueError("股票代码必须是字符串")

    base = symbol.strip().upper()
    for suffix in (".SZ", ".SH", ".HK"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    if not base.isdigit() or not (4 <= len(base) <= 6):
        raise ValueError(f"股票代码格式错误: {symbol}")
    return True


def validate_date(date_str: str) -> bool:
    if not date_str:
        raise ValueError("Date cannot be empty")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")


def validate_positive_number(value: float, name: str) -> bool:
    if value is None:
        raise ValueError(f"{name} cannot be None")
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return True
