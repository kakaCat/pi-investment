"""市场时钟端口 (Market Clock Port)

RFC 016 D10（2026-09-12）：领域层**不得**直接取系统时间——时间一律经本端口注入，
使领域策略保持纯函数、可单测（既有 14+ 处 naive `datetime.now()` 是时区事故的温床，
且任何依赖真实时钟的用例在非交易时段必假失败）。

本端口语义固定为 **Asia/Shanghai（北京时间）**，实现见
`adapters/outbound/clock/beijing_clock.py`。

domain 层定义接口，application/adapters 层实现（依赖倒置，同 ITradingCalendar）。
"""
from abc import ABC, abstractmethod
from datetime import date, datetime


class IMarketClock(ABC):
    """市场时钟接口（北京时间）"""

    @abstractmethod
    def now(self) -> datetime:
        """当前北京时间（tz-aware）"""
        pass

    @abstractmethod
    def today(self) -> date:
        """当前北京日期"""
        pass
