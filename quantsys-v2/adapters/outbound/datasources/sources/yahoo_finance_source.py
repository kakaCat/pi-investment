"""Yahoo Finance data source.

Provides free access to US stock market data without API key requirement.
"""

from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timedelta

from adapters.outbound.datasources.base import MarketDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import safe_call, validate_symbol

logger = logging.getLogger(__name__)


class YahooFinanceSource(MarketDataSource):
    """Yahoo Finance data source.

    Provides free access to:
    - US stock quotes and historical data
    - International stocks
    - Indices, ETFs, mutual funds
    - Forex and commodities

    No API key required.
    """

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance"
    CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self):
        super().__init__(name="YahooFinance", requires_api_key=False)
        self.session = SessionManager.get_session("yahoo_finance")

    def validate_config(self) -> bool:
        """Yahoo Finance doesn't require configuration."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test Yahoo Finance connection."""
        try:
            # Test with Apple stock
            result = self.get_stock_info("AAPL")
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected", "test": "passed"},
                    metadata={"source": "yahoo_finance"}
                )
            return result
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get stock information.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "MSFT")

        Returns:
            DataSourceResponse with stock info
        """
        self._log_request("get_stock_info", {"symbol": symbol})

        try:
            url = f"{self.BASE_URL}/quote"
            params = {"symbols": symbol}

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if "quoteResponse" not in data or not data["quoteResponse"].get("result"):
                return DataSourceResponse.error_response(f"No data for symbol {symbol}")

            quote = data["quoteResponse"]["result"][0]

            result = {
                "symbol": quote.get("symbol"),
                "name": quote.get("longName") or quote.get("shortName"),
                "price": quote.get("regularMarketPrice"),
                "change": quote.get("regularMarketChange"),
                "change_percent": quote.get("regularMarketChangePercent"),
                "volume": quote.get("regularMarketVolume"),
                "market_cap": quote.get("marketCap"),
                "pe_ratio": quote.get("trailingPE"),
                "dividend_yield": quote.get("dividendYield"),
                "52w_high": quote.get("fiftyTwoWeekHigh"),
                "52w_low": quote.get("fiftyTwoWeekLow"),
                "currency": quote.get("currency"),
                "exchange": quote.get("fullExchangeName"),
            }

            self._log_success("get_stock_info", 1)
            return DataSourceResponse.success_response(result)

        except Exception as e:
            return self._handle_error("get_stock_info", e)

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get OHLCV kline data.

        Args:
            symbol: Stock symbol
            period: Period (daily/weekly/monthly)
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)

        Returns:
            DataSourceResponse with kline data
        """
        self._log_request("get_klines", {
            "symbol": symbol,
            "period": period,
            "start_date": start_date,
            "end_date": end_date
        })

        try:
            # Convert dates to timestamps
            start_dt = datetime.strptime(start_date, "%Y%m%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_ts = int(start_dt.timestamp())
            end_ts = int(end_dt.timestamp())

            # Map period to Yahoo Finance interval
            interval_map = {
                "daily": "1d",
                "weekly": "1wk",
                "monthly": "1mo"
            }
            interval = interval_map.get(period, "1d")

            url = f"{self.CHART_URL}/{symbol}"
            params = {
                "period1": start_ts,
                "period2": end_ts,
                "interval": interval,
                "events": "div,split"
            }

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if "chart" not in data or not data["chart"].get("result"):
                return DataSourceResponse.error_response(f"No kline data for {symbol}")

            result = data["chart"]["result"][0]
            timestamps = result.get("timestamp", [])
            quotes = result.get("indicators", {}).get("quote", [{}])[0]

            klines = []
            for i, ts in enumerate(timestamps):
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                klines.append({
                    "symbol": symbol,
                    "date": date,
                    "open": quotes.get("open", [])[i] if i < len(quotes.get("open", [])) else None,
                    "high": quotes.get("high", [])[i] if i < len(quotes.get("high", [])) else None,
                    "low": quotes.get("low", [])[i] if i < len(quotes.get("low", [])) else None,
                    "close": quotes.get("close", [])[i] if i < len(quotes.get("close", [])) else None,
                    "volume": quotes.get("volume", [])[i] if i < len(quotes.get("volume", [])) else None,
                })

            self._log_success("get_klines", len(klines))
            return DataSourceResponse.success_response(
                klines,
                metadata={"symbol": symbol, "period": period}
            )

        except Exception as e:
            return self._handle_error("get_klines", e)

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """Get real-time quotes for multiple symbols.

        Args:
            symbols: List of stock symbols

        Returns:
            DataSourceResponse with quote data
        """
        self._log_request("get_realtime_quote", {"symbols": symbols})

        try:
            url = f"{self.BASE_URL}/quote"
            params = {"symbols": ",".join(symbols)}

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if "quoteResponse" not in data:
                return DataSourceResponse.error_response("Invalid response format")

            quotes = {}
            for quote in data["quoteResponse"].get("result", []):
                symbol = quote.get("symbol")
                quotes[symbol] = {
                    "symbol": symbol,
                    "name": quote.get("longName") or quote.get("shortName"),
                    "price": quote.get("regularMarketPrice"),
                    "change": quote.get("regularMarketChange"),
                    "change_percent": quote.get("regularMarketChangePercent"),
                    "volume": quote.get("regularMarketVolume"),
                    "high": quote.get("regularMarketDayHigh"),
                    "low": quote.get("regularMarketDayLow"),
                    "open": quote.get("regularMarketOpen"),
                    "pre_close": quote.get("regularMarketPreviousClose"),
                }

            self._log_success("get_realtime_quote", len(quotes))
            return DataSourceResponse.success_response(quotes)

        except Exception as e:
            return self._handle_error("get_realtime_quote", e)

    def search_symbols(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for stock symbols.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            DataSourceResponse with search results
        """
        self._log_request("search_symbols", {"query": query, "limit": limit})

        try:
            url = "https://query1.finance.yahoo.com/v1/finance/search"
            params = {
                "q": query,
                "quotesCount": limit,
                "newsCount": 0
            }

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            results = []
            for quote in data.get("quotes", [])[:limit]:
                results.append({
                    "symbol": quote.get("symbol"),
                    "name": quote.get("longname") or quote.get("shortname"),
                    "type": quote.get("quoteType"),
                    "exchange": quote.get("exchange"),
                })

            self._log_success("search_symbols", len(results))
            return DataSourceResponse.success_response(results)

        except Exception as e:
            return self._handle_error("search_symbols", e)

    def get_trending(self, region: str = "US") -> DataSourceResponse:
        """Get trending stocks.

        Args:
            region: Region code (US, GB, HK, etc.)

        Returns:
            DataSourceResponse with trending stocks
        """
        self._log_request("get_trending", {"region": region})

        try:
            url = f"https://query1.finance.yahoo.com/v1/finance/trending/{region}"

            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            trending = []
            for quote in data.get("finance", {}).get("result", [{}])[0].get("quotes", []):
                trending.append({
                    "symbol": quote.get("symbol"),
                    "name": quote.get("longName") or quote.get("shortName"),
                })

            self._log_success("get_trending", len(trending))
            return DataSourceResponse.success_response(trending)

        except Exception as e:
            return self._handle_error("get_trending", e)
