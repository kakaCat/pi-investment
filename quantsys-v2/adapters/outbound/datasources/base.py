"""Abstract base classes for all data providers."""
from abc import ABC, abstractmethod
from typing import Optional, TypeVar, Generic, List

from adapters.outbound.datasources.models import (
    QuoteData,
    FinancialData,
    DividendData,
    MarketData,
    StockData
)

T = TypeVar('T')


class BaseDataProvider(ABC, Generic[T]):
    """Base data provider class

    All providers must inherit from this class and implement abstract methods.
    """

    def __init__(self):
        self.timeout = 5
        self.retry_count = 1

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'sina', 'eastmoney', 'akshare')"""
        pass


class QuoteProvider(BaseDataProvider[QuoteData]):
    """Realtime quote provider interface"""

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """Get realtime quote for a symbol

        Args:
            symbol: Stock symbol (e.g., '600519.SH')

        Returns:
            QuoteData or None if failed
        """
        pass

    def get_quotes(self, symbols: "list[str]") -> "dict[str, QuoteData]":
        """批量实时行情（2026-09-13，w-adb088f2）

        默认实现退化为逐只调用 get_quote —— 语义正确但对**支持批量的源**不是最优。
        支持一次请求多只的 provider（如腾讯）应覆盖本方法，把 N 次新建连接降为 1 次。

        约定（调用方 manager.get_quotes 依赖）：
          - 返回 {symbol: QuoteData}，只包含**成功且非空**的标的；
          - 未返回 ≠ 该股无行情，只表示本 provider 没给；
          - 单只失败不得让整批抛错（吞掉并继续），除非整批请求本身失败。

        Args:
            symbols: 标准代码列表（如 ['600519.SH', '000001']）

        Returns:
            {symbol: QuoteData}
        """
        out: "dict[str, QuoteData]" = {}
        for symbol in symbols:
            try:
                quote = self.get_quote(symbol)
            except Exception:
                continue
            if quote is not None:
                out[symbol] = quote
        return out


class FinancialProvider(BaseDataProvider[FinancialData]):
    """Financial data provider interface"""

    @abstractmethod
    def get_financial(self, symbol: str, report_type: str = 'latest') -> Optional[FinancialData]:
        """Get financial data for a symbol

        Args:
            symbol: Stock symbol
            report_type: 'latest' | 'quarterly' | 'annual'

        Returns:
            FinancialData or None if failed
        """
        pass


class DividendProvider(BaseDataProvider[DividendData]):
    """Dividend data provider interface"""

    @abstractmethod
    def get_dividends(self, symbol: str, years: int = 5) -> Optional[List[DividendData]]:
        """Get dividend history for a symbol

        Args:
            symbol: Stock symbol
            years: Number of years to fetch

        Returns:
            List of DividendData or None if failed
        """
        pass

    @abstractmethod
    def get_dividend_calendar(self, start_date: str, end_date: str) -> Optional[List[DividendData]]:
        """Get dividend calendar within date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of DividendData or None if failed
        """
        pass

    @abstractmethod
    def screen_high_dividend(self, min_yield: float = 3.0, min_years: int = 5) -> Optional[List[DividendData]]:
        """Screen high dividend stocks

        Args:
            min_yield: Minimum dividend yield (%)
            min_years: Minimum consecutive dividend years

        Returns:
            List of DividendData or None if failed
        """
        pass


class MarketProvider(BaseDataProvider[MarketData]):
    """Market data provider interface"""

    @abstractmethod
    def get_market_overview(self) -> Optional[MarketData]:
        """Get market overview (rise/fall counts, indices)

        Returns:
            MarketData or None if failed
        """
        pass

    @abstractmethod
    def get_lhb_stock(self, symbol: str, date: str) -> Optional[MarketData]:
        """Get dragon-tiger list (龙虎榜) for a stock

        Args:
            symbol: Stock symbol
            date: Date (YYYY-MM-DD)

        Returns:
            MarketData or None if failed
        """
        pass

    @abstractmethod
    def get_lhb_daily(self, date: str) -> Optional[MarketData]:
        """Get daily dragon-tiger list

        Args:
            date: Date (YYYY-MM-DD)

        Returns:
            MarketData or None if failed
        """
        pass


class StockProvider(BaseDataProvider[StockData]):
    """Stock basic data provider interface"""

    @abstractmethod
    def get_announcements(self, symbol: str) -> Optional[StockData]:
        """Get stock announcements

        Args:
            symbol: Stock symbol

        Returns:
            StockData or None if failed
        """
        pass

    @abstractmethod
    def get_news(self, symbol: str, num: int = 10) -> Optional[StockData]:
        """Get stock news

        Args:
            symbol: Stock symbol
            num: Number of news items to fetch

        Returns:
            StockData or None if failed
        """
        pass

    @abstractmethod
    def get_trading_calendar(self, start_date: str, end_date: str) -> Optional[StockData]:
        """Get trading calendar (trading days)

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            StockData or None if failed
        """
        pass
