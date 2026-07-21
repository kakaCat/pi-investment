"""Polygon.io data source.

Provides access to US stock market data with free and paid tiers.
"""

from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from adapters.outbound.datasources.base import MarketDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.config import DataSourceConfig

logger = logging.getLogger(__name__)


class PolygonSource(MarketDataSource):
    """Polygon.io data source.

    Provides access to:
    - US stock OHLCV data
    - Real-time and delayed quotes
    - Market aggregates
    - Ticker details
    - Options and crypto (paid tiers)

    Requires API key (free tier available).
    Get your key at: https://polygon.io/
    """

    BASE_URL = "https://api.polygon.io"

    def __init__(self):
        super().__init__(name="Polygon", requires_api_key=True)
        self.api_key = DataSourceConfig.get_api_key("polygon")
        self.session = SessionManager.get_session("polygon")

    def validate_config(self) -> bool:
        """Validate Polygon API key is configured."""
        if not self.api_key:
            self.logger.error(
                "Polygon API key not configured. "
                "Set POLYGON_API_KEY environment variable. "
                "Get your key at: https://polygon.io/"
            )
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test Polygon API connection."""
        if not self.validate_config():
            return DataSourceResponse.error_response("Polygon API key not configured")

        try:
            result = self.get_stock_info("AAPL")
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected", "test": "passed"},
                    metadata={"source": "polygon"}
                )
            return result
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get stock ticker details.

        Args:
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            DataSourceResponse with stock info
        """
        self._log_request("get_stock_info", {"symbol": symbol})

        if not self.validate_config():
            return DataSourceResponse.error_response("API key not configured")

        try:
            url = f"{self.BASE_URL}/v3/reference/tickers/{symbol.upper()}"
            params = {"apiKey": self.api_key}

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or "results" not in data:
                return DataSourceResponse.error_response(f"No data for symbol {symbol}")

            result = data["results"]
            info = {
                "symbol": result.get("ticker"),
                "name": result.get("name"),
                "market": result.get("market"),
                "locale": result.get("locale"),
                "primary_exchange": result.get("primary_exchange"),
                "type": result.get("type"),
                "currency": result.get("currency_name"),
                "cik": result.get("cik"),
                "composite_figi": result.get("composite_figi"),
                "share_class_figi": result.get("share_class_figi"),
            }

            self._log_success("get_stock_info", 1)
            return DataSourceResponse.success_response(info)

        except Exception as e:
            return self._handle_error("get_stock_info", e)

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get OHLCV aggregates (klines).

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

        if not self.validate_config():
            return DataSourceResponse.error_response("API key not configured")

        try:
            # Map period to Polygon timespan
            timespan_map = {
                "daily": "day",
                "weekly": "week",
                "monthly": "month"
            }
            timespan = timespan_map.get(period, "day")

            # Format dates
            start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

            url = f"{self.BASE_URL}/v2/aggs/ticker/{symbol.upper()}/range/1/{timespan}/{start}/{end}"
            params = {
                "adjusted": "true",
                "sort": "asc",
                "limit": 5000,
                "apiKey": self.api_key
            }

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or "results" not in data:
                return DataSourceResponse.error_response(f"No kline data for {symbol}")

            klines = []
            for bar in data["results"]:
                timestamp = bar.get("t")
                date = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")

                klines.append({
                    "symbol": symbol,
                    "date": date,
                    "timestamp": timestamp,
                    "open": bar.get("o"),
                    "high": bar.get("h"),
                    "low": bar.get("l"),
                    "close": bar.get("c"),
                    "volume": bar.get("v"),
                    "vwap": bar.get("vw"),
                    "trades": bar.get("n"),
                })

            self._log_success("get_klines", len(klines))
            return DataSourceResponse.success_response(
                klines,
                metadata={"symbol": symbol, "period": period}
            )

        except Exception as e:
            return self._handle_error("get_klines", e)

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """Get real-time quotes (last trade).

        Args:
            symbols: List of stock symbols

        Returns:
            DataSourceResponse with quote data
        """
        self._log_request("get_realtime_quote", {"symbols": symbols})

        if not self.validate_config():
            return DataSourceResponse.error_response("API key not configured")

        try:
            quotes = {}

            for symbol in symbols:
                url = f"{self.BASE_URL}/v2/last/trade/{symbol.upper()}"
                params = {"apiKey": self.api_key}

                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "OK" and "results" in data:
                    result = data["results"]
                    quotes[symbol] = {
                        "symbol": symbol,
                        "price": result.get("p"),
                        "size": result.get("s"),
                        "exchange": result.get("x"),
                        "timestamp": result.get("t"),
                    }

            self._log_success("get_realtime_quote", len(quotes))
            return DataSourceResponse.success_response(quotes)

        except Exception as e:
            return self._handle_error("get_realtime_quote", e)

    def get_daily_open_close(self, symbol: str, date: str) -> DataSourceResponse:
        """Get daily open/close for a specific date.

        Args:
            symbol: Stock symbol
            date: Date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with OHLC data
        """
        self._log_request("get_daily_open_close", {"symbol": symbol, "date": date})

        if not self.validate_config():
            return DataSourceResponse.error_response("API key not configured")

        try:
            url = f"{self.BASE_URL}/v1/open-close/{symbol.upper()}/{date}"
            params = {"adjusted": "true", "apiKey": self.api_key}

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                return DataSourceResponse.error_response(f"No data for {symbol} on {date}")

            result = {
                "symbol": data.get("symbol"),
                "date": data.get("from"),
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "close": data.get("close"),
                "volume": data.get("volume"),
                "after_hours": data.get("afterHours"),
                "pre_market": data.get("preMarket"),
            }

            self._log_success("get_daily_open_close", 1)
            return DataSourceResponse.success_response(result)

        except Exception as e:
            return self._handle_error("get_daily_open_close", e)

    def get_grouped_daily(self, date: str) -> DataSourceResponse:
        """Get grouped daily bars for all stocks.

        Args:
            date: Date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with all stocks data
        """
        self._log_request("get_grouped_daily", {"date": date})

        if not self.validate_config():
            return DataSourceResponse.error_response("API key not configured")

        try:
            url = f"{self.BASE_URL}/v2/aggs/grouped/locale/us/market/stocks/{date}"
            params = {"adjusted": "true", "apiKey": self.api_key}

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or "results" not in data:
                return DataSourceResponse.error_response(f"No data for date {date}")

            results = []
            for bar in data["results"]:
                results.append({
                    "symbol": bar.get("T"),
                    "open": bar.get("o"),
                    "high": bar.get("h"),
                    "low": bar.get("l"),
                    "close": bar.get("c"),
                    "volume": bar.get("v"),
                    "vwap": bar.get("vw"),
                    "trades": bar.get("n"),
                })

            self._log_success("get_grouped_daily", len(results))
            return DataSourceResponse.success_response(results)

        except Exception as e:
            return self._handle_error("get_grouped_daily", e)

    def get_market_status(self) -> DataSourceResponse:
        """Get current market status.

        Returns:
            DataSourceResponse with market status
        """
        self._log_request("get_market_status", {})

        if not self.validate_config():
            return DataSourceResponse.error_response("API key not configured")

        try:
            url = f"{self.BASE_URL}/v1/marketstatus/now"
            params = {"apiKey": self.api_key}

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            self._log_success("get_market_status", 1)
            return DataSourceResponse.success_response(data)

        except Exception as e:
            return self._handle_error("get_market_status", e)
