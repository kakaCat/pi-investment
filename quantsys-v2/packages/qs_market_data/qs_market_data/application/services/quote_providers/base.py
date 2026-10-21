"""
实时行情数据源基础接口
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


class QuoteUnavailableError(Exception):
    """实时行情不可用（真实失败：所有数据源都尝试过且都失败）。

    与 None 的区别：None 历史上同时表示「真实全灭」与「熔断冷却跳过」两种
    语义，调用方无法分辨（2026-10-20/21 盯盘引擎 70 条"疑似停牌/退市"
    误报的根因之一）。真实全灭抛本异常，语义单一。
    """


class AllProvidersCoolingDownError(QuoteUnavailableError):
    """所有数据源都处于熔断冷却中——**不是**取数失败。

    熔断是上游故障时的自我保护（60 秒冷却），本轮跳过属预期行为，绝不能
    与「标的取不到数据」混为一谈：前者是数据源集体休克，后者才可能意味着
    标的停牌/退市。

    误报实证（2026-10-20 09:30:47~09:30:58）：5 个源逐个失败后全部进入冷却，
    随后所有标的取价批量返回 None，盯盘引擎 90 秒内累计 3 次即误判
    「连续 3 个交易日取数失败 → 疑似停牌/退市」。

    冷却剩余秒数放在 blocked 供调用方记账。
    """

    def __init__(self, symbol: str, blocked: Optional[Dict[str, Any]] = None):
        self.symbol = symbol
        self.blocked = blocked or {}
        super().__init__(
            '%s 本轮跳过：所有数据源熔断冷却中（%s），非真实失败' % (
                symbol,
                ', '.join('%s(剩%s秒)' % (n, s.get('remaining_seconds', '?'))
                          for n, s in self.blocked.items()) or '全部',
            )
        )


@dataclass
class QuoteData:
    """实时行情数据模型

    Attributes:
        symbol: 股票代码
        name: 股票名称
        price: 当前价格
        open: 开盘价
        high: 最高价
        low: 最低价
        prev_close: 昨收价
        volume: 成交量
        amount: 成交额
        change: 涨跌额
        change_pct: 涨跌幅
        source: 数据源名称
        timestamp: 时间戳（ISO 8601 格式字符串，如 '2026-05-29T14:30:00'）
    """
    symbol: str
    name: str
    price: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    source: str = ''
    timestamp: str = ''

    def __post_init__(self):
        """验证数据有效性"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")


class QuoteProvider(ABC):
    """实时行情数据源接口"""

    def __init__(self):
        self.timeout = 5
        self.retry_count = 1

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情

        Args:
            symbol: 股票代码（支持 6位数字 或 带后缀格式）

        Returns:
            QuoteData 或 None（失败时）
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码（去除首尾空格）"""
        return symbol.strip()
