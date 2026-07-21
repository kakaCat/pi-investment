"""Binance cryptocurrency data source.

Provides free access to cryptocurrency market data from Binance.
"""

from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from adapters.outbound.datasources.base import MarketDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import safe_call

logger = logging.getLogger(__name__)


class BinanceSource(MarketDataSource):
    """Binance cryptocurrency data source.

    Provides free access to:
    - Cryptocurrency prices and quotes
    - OHLCV kline data
    - 24h ticker statistics
    - Order book data
    - Trading pairs

    No API key required for public endpoints.
    """

    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self):
        super().__init__(name="Binance", requires_api_key=False)
        self.session = SessionManager.get_session("binance")

    def validate_config(self) -> bool:
        """Binance public API doesn't require configuration."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test Binance API connection."""
        try:
            result = self.get_server_time()
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected", "test": "passed"},
                    metadata={"source": "binance"}
                )
            return result
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_server_time(self) -> DataSourceResponse:
        """Get Binance server time."""
        try:
            url = f"{self.BASE_URL}/time"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response({
                "server_time": data.get("serverTime"),
                "datetime": datetime.fromtimestamp(data.get("serverTime", 0) / 1000).isoformat()
            })
        except Exception as e:
            return self._handle_error("get_server_time", e)

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get cryptocurrency information.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT", "ETHUSDT")

        Returns:
            DataSourceResponse with crypto info
        """
        self._log_request("get_stock_info", {"symbol": symbol})

        try:
            # Get 24h ticker
            url = f"{self.BASE_URL}/ticker/24hr"
            params = {"symbol": symbol.upper()}

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = {
                "symbol": data.get("symbol"),
                "price": float(data.get("lastPrice", 0)),
                "change": float(data.get("priceChange", 0)),
                "change_percent": float(data.get("priceChangePercent", 0)),
                "high_24h": float(data.get("highPrice", 0)),
                "low_24h": float(data.get("lowPrice", 0)),
                "volume_24h": float(data.get("volume", 0)),
                "quote_volume_24h": float(data.get("quoteVolume", 0)),
                "open_price": float(data.get("openPrice", 0)),
                "prev_close": float(data.get("prevClosePrice", 0)),
                "bid_price": float(data.get("bidPrice", 0)),
                "ask_price": float(data.get("askPrice", 0)),
                "trades_count": data.get("count", 0),
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
            symbol: Trading pair (e.g., "BTCUSDT")
            period: Period (1m/5m/15m/1h/4h/daily/weekly/monthly)
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
            # Map period to Binance interval
            interval_map = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "1h": "1h",
                "4h": "4h",
                "daily": "1d",
                "weekly": "1w",
                "monthly": "1M"
            }
            interval = interval_map.get(period, "1d")

            # Convert dates to timestamps
            start_dt = datetime.strptime(start_date, "%Y%m%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_ts = int(start_dt.timestamp() * 1000)
            end_ts = int(end_dt.timestamp() * 1000)

            url = f"{self.BASE_URL}/klines"
            params = {
                "symbol": symbol.upper(),
                "interval": interval,
                "startTime": start_ts,
                "endTime": end_ts,
                "limit": 1000
            }

            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            klines = []
            for kline in data:
                timestamp = kline[0]
                date = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")

                klines.append({
                    "symbol": symbol,
                    "date": date,
                    "timestamp": timestamp,
                    "open": float(kline[1]),
                    "high": float(kline[2]),
                    "low": float(kline[3]),
                    "close": float(kline[4]),
                    "volume": float(kline[5]),
                    "close_time": kline[6],
                    "quote_volume": float(kline[7]),
                    "trades": kline[8],
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
            symbols: List of trading pairs

        Returns:
            DataSourceResponse with quote data
        """
        self._log_request("get_realtime_quote", {"symbols": symbols})

        try:
            url = f"{self.BASE_URL}/ticker/price"

            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Filter for requested symbols
            symbols_upper = [s.upper() for s in symbols]
            quotes = {}

            for ticker in data:
                symbol = ticker.get("symbol")
                if symbol in symbols_upper:
                    quotes[symbol] = {
                        "symbol": symbol,
                        "price": float(ticker.get("price", 0))
                    }

            self._log_success("get_realtime_quote", len(quotes))
            return DataSourceResponse.success_response(quotes)

        except Exception as e:
            return self._handle_error("get_realtime_quote", e)

    def get_all_tickers(self) -> DataSourceResponse:
        """Get all ticker prices.

        Returns:
            DataSourceResponse with all tickers
        """
        self._log_request("get_all_tickers", {})

        try:
            url = f"{self.BASE_URL}/ticker/price"

            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            tickers = [
                {
                    "symbol": ticker.get("symbol"),
                    "price": float(ticker.get("price", 0))
                }
                for ticker in data
            ]

            self._log_success("get_all_tickers", len(tickers))
            return DataSourceResponse.success_response(tickers)

        except Exception as e:
            return self._handle_error("get_all_tickers", e)

    def get_24h_tickers(self) -> DataSourceResponse:
        """Get 24h ticker statistics for all symbols.

        Returns:
            DataSourceResponse with 24h stats
        """
        self._log_request("get_24h_tickers", {})

        try:
            url = f"{self.BASE_URL}/ticker/24hr"

            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            tickers = []
            for ticker in data:
                tickers.append({
                    "symbol": ticker.get("symbol"),
                    "price": float(ticker.get("lastPrice", 0)),
                    "change_percent": float(ticker.get("priceChangePercent", 0)),
                    "volume": float(ticker.get("volume", 0)),
                    "quote_volume": float(ticker.get("quoteVolume", 0)),
                    "high": float(ticker.get("highPrice", 0)),
                    "low": float(ticker.get("lowPrice", 0)),
                })

            self._log_success("get_24h_tickers", len(tickers))
            return DataSourceResponse.success_response(tickers)

        except Exception as e:
            return self._handle_error("get_24h_tickers", e)

    def get_exchange_info(self) -> DataSourceResponse:
        """Get exchange information and trading pairs.

        Returns:
            DataSourceResponse with exchange info
        """
        self._log_request("get_exchange_info", {})

        try:
            url = f"{self.BASE_URL}/exchangeInfo"

            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            symbols = []
            for symbol_info in data.get("symbols", []):
                if symbol_info.get("status") == "TRADING":
                    symbols.append({
                        "symbol": symbol_info.get("symbol"),
                        "base_asset": symbol_info.get("baseAsset"),
                        "quote_asset": symbol_info.get("quoteAsset"),
                        "status": symbol_info.get("status"),
                    })

            result = {
                "timezone": data.get("timezone"),
                "server_time": data.get("serverTime"),
                "symbols_count": len(symbols),
                "symbols": symbols
            }

            self._log_success("get_exchange_info", len(symbols))
            return DataSourceResponse.success_response(result)

        except Exception as e:
            return self._handle_error("get_exchange_info", e)

    def get_order_book(self, symbol: str, limit: int = 100) -> DataSourceResponse:
        """Get order book depth.

        Args:
            symbol: Trading pair
            limit: Depth limit (5, 10, 20, 50, 100, 500, 1000, 5000)

        Returns:
            DataSourceResponse with order book
        """
        self._log_request("get_order_book", {"symbol": symbol, "limit": limit})

        try:
            url = f"{self.BASE_URL}/depth"
            params = {
                "symbol": symbol.upper(),
                "limit": limit
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = {
                "symbol": symbol,
                "last_update_id": data.get("lastUpdateId"),
                "bids": [[float(price), float(qty)] for price, qty in data.get("bids", [])],
                "asks": [[float(price), float(qty)] for price, qty in data.get("asks", [])],
            }

            self._log_success("get_order_book", 1)
            return DataSourceResponse.success_response(result)

        except Exception as e:
            return self._handle_error("get_order_book", e)


# Popular trading pairs
POPULAR_PAIRS = {
    "BTC": ["BTCUSDT", "BTCBUSD", "BTCETH"],
    "ETH": ["ETHUSDT", "ETHBUSD", "ETHBTC"],
    "BNB": ["BNBUSDT", "BNBBUSD", "BNBBTC"],
    "SOL": ["SOLUSDT", "SOLBUSD", "SOLBTC"],
    "XRP": ["XRPUSDT", "XRPBUSD", "XRPBTC"],
}
