"""
实时行情数据源基础接口
"""
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


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
