"""日期归一（2026-09-13 w-c8cae280 建立）

为什么要建这个模块：同一个"把各种日期形态归一为 date"的需求，全库此前**各自复制了 4 份** ——
  domain/trading/models/market_session.py:_as_date
  application/services/evolution/decision_score_service.py:_as_date
  tools/check_data_contracts.py:_as_date
  adapters/.../events/akshare_unlock.py:_as_date（返回 str，语义不同）
没有共享家 → 守卫各写各的、逐步漂移 → "对 date 调 .date() 抛 AttributeError"（或静默落空）反复发生。
本模块是唯一实现；各处保留原有名字作为薄封装，只为兼容调用方。

⚠️ 真实踩坑（2026-09-13）：
  - strategy_rotation_engine.py 对 updated_at 只处理了 str / datetime，
    **没有 date 分支** → psycopg 若返回 date 就静默落空、轮动状态陈旧且无日志；
  - 同一字段在 SQLAlchemy 路径返回 datetime.date、在 psql CSV 路径被 pandas 解析成 Timestamp，
    两种类型都真实存在（core_plan 的透镜就因此崩过一次）。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

__all__ = ["as_date", "as_datetime", "as_date_str"]


def as_date(value, default: Optional[date] = None) -> Optional[date]:
    """把 datetime / date / 'YYYY-MM-DD[THH:MM[:SS]]' / None 归一为 date。

    不可解析 → 返回 default（默认 None）。**不抛异常**：调用方几乎都在做"取个日期而已"，
    为一个格式问题把整条链路打断（或反过来静默给今天）都不合适，故由调用方决定 default。
    注意分支顺序：datetime 是 date 的子类，必须先判 datetime。
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return default


def as_datetime(value, default: Optional[datetime] = None) -> Optional[datetime]:
    """把 datetime / date / ISO 字符串归一为 datetime（date 取 00:00:00）。"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    d = as_date(value)
    return datetime(d.year, d.month, d.day) if d else default


def as_date_str(value, default: Optional[str] = None) -> Optional[str]:
    """归一为 'YYYY-MM-DD' 字符串（给 SQL 参数 / 日志用）。"""
    d = as_date(value)
    return d.isoformat() if d else default
