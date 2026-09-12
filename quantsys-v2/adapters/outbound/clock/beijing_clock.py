"""北京时间时钟（IMarketClock 的出站适配器）

RFC 016 D10（2026-09-12）：全仓唯一的时间来源。时区语义在此收口，
消除领域/应用层的 naive `datetime.now()`（写法对齐
`infrastructure/scheduler/scheduler.py` 的 `ZoneInfo("Asia/Shanghai")`）。
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from domain.trading.ports.IMarketClock import IMarketClock

BEIJING_TZ = ZoneInfo('Asia/Shanghai')


class BeijingClock(IMarketClock):
    """北京时间时钟"""

    def now(self) -> datetime:
        """当前北京时间（tz-aware，ISO 序列化自带 +08:00 偏移）"""
        return datetime.now(BEIJING_TZ)

    def today(self) -> date:
        """当前北京日期"""
        return self.now().date()
