"""
市场数据领域模型

这些模型定义了系统中市场数据的核心结构，独立于具体的数据源实现。
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class QuoteData:
    """实时行情数据（领域模型）

    表示某一时刻的股票行情快照
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
        """数据验证"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")


@dataclass
class KlineData:
    """K线数据（领域模型）

    表示某一时间周期的OHLC数据
    """
    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: Optional[float] = None
    change_pct: Optional[float] = None
    turnover_rate: Optional[float] = None
    source: str = ''
    timestamp: str = ''


@dataclass
class FinancialData:
    """财务数据（领域模型）

    表示公司的财务指标
    """
    symbol: str
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    net_profit_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None
    ocf_to_profit: Optional[float] = None
    current_ratio: Optional[float] = None
    roa: Optional[float] = None
    operating_margin: Optional[float] = None
    source: str = ''
    timestamp: str = ''


@dataclass
class DividendData:
    """分红数据（领域模型）

    表示股票分红信息
    """
    symbol: str
    dividend_per_share: float
    dividend_yield: Optional[float] = None
    ex_dividend_date: Optional[str] = None
    record_date: Optional[str] = None
    pay_date: Optional[str] = None
    source: str = ''
    timestamp: str = ''


@dataclass
class MarketData:
    """市场数据（领域模型）

    通用容器，用于板块、龙虎榜、资金流等灵活结构的市场数据
    """
    data_type: str  # 'overview' | 'sector' | 'lhb' | 'fund_flow' | etc.
    data: Dict[str, Any]
    source: str = ''
    timestamp: str = ''


@dataclass
class StockData:
    """股票基础数据（领域模型）

    表示公告、新闻、交易日历等股票相关信息
    """
    symbol: str
    data_type: str  # 'announcement' | 'news' | 'trading_calendar' | etc.
    data: List[Dict[str, Any]]
    total: int = 0
    source: str = ''
    timestamp: str = ''
