"""Data models for all provider domains.

All models include source and timestamp fields for tracking data origin.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class QuoteData:
    """Realtime quote data (existing model from quote_providers, kept unchanged)"""
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
        """Validate data"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")


@dataclass
class FinancialData:
    """Financial data (statements and indicators)"""
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
    """Dividend data"""
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
    """Market data (flexible structure for overview, sectors, LHB, etc.)"""
    data_type: str  # 'overview' | 'sector' | 'lhb' | 'fund_flow' | etc.
    data: Dict[str, Any]
    source: str = ''
    timestamp: str = ''


@dataclass
class StockData:
    """Stock basic data (announcements, news, trading calendar, etc.)"""
    symbol: str
    data_type: str  # 'announcement' | 'news' | 'trading_calendar' | etc.
    data: List[Dict[str, Any]]
    total: int = 0
    source: str = ''
    timestamp: str = ''
