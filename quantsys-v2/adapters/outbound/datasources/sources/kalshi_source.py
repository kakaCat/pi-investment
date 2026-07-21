"""Kalshi prediction market data source.

Provides access to Kalshi Trade API v2 for prediction market data including
markets, order books, trades, candlestick history, and events.

API Documentation: https://trading-api.kalshi.com/trade-api/v2

No API key required for public market data.
"""

import os
from typing import Optional, Dict, Any, List
import logging
import time

from adapters.outbound.datasources.base import MarketDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class KalshiSource(MarketDataSource):
    """Kalshi prediction market data source.

    Kalshi is a CFTC-regulated prediction market exchange.
    The Trade API v2 provides access to:
    - Market listings and details
    - Event information
    - Order book depth
    - Candlestick price history
    - Recent trades

    Authentication with RSA key pair is optional for elevated access.
    """

    BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"

    CATEGORIES = {
        "economics": "Economic indicators (CPI, NFP, GDP, Fed decisions)",
        "weather": "Weather events (temperature ranges, hurricanes)",
        "politics": "Policy outcomes, legislation, government",
        "crypto": "Cryptocurrency price ranges",
        "equities": "Stock index and price targets",
        "entertainment": "Entertainment and cultural events",
    }

    def __init__(
        self,
        api_key_id: Optional[str] = None,
        api_key_private: Optional[str] = None
    ):
        """Initialize Kalshi data source.

        Args:
            api_key_id: Kalshi API key ID (or set KALSHI_KEY_ID env var)
            api_key_private: Path to RSA private key file (or set KALSHI_PRIVATE_KEY_PATH env var)
        """
        super().__init__(name="Kalshi", requires_api_key=True)
        self.api_key_id = api_key_id or os.getenv("KALSHI_KEY_ID")
        self.private_key_path = api_key_private or os.getenv("KALSHI_PRIVATE_KEY_PATH")
        self._private_key_pem: Optional[str] = None
        self.session = SessionManager.get_session("kalshi")

    def _load_private_key(self) -> Optional[str]:
        """Load private key from file path."""
        if self._private_key_pem is not None:
            return self._private_key_pem
        if self.private_key_path and os.path.exists(self.private_key_path):
            try:
                with open(self.private_key_path, "r") as f:
                    self._private_key_pem = f.read()
            except Exception as e:
                logger.warning(f"Failed to load private key: {e}")
                return None
        return self._private_key_pem

    def validate_config(self) -> bool:
        """Validate configuration. Public endpoints work without auth."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection using exchange status endpoint."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/exchange/status",
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Kalshi", "exchange_status": data},
                metadata={"source": "Kalshi", "base_url": self.BASE_URL}
            )
        except Exception as e:
            return self._handle_error("test_connection", e)

    def _sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Create RSA SHA256 signature for authenticated requests."""
        headers: Dict[str, str] = {}
        if not self.api_key_id:
            return headers

        private_key_pem = self._load_private_key()
        if not private_key_pem:
            return headers

        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding, rsa
            from cryptography.hazmat.backends import default_backend
            import base64

            private_key = serialization.load_pem_private_key(
                private_key_pem.encode("utf-8"),
                password=None,
                backend=default_backend()
            )

            current_time_ms = int(time.time() * 1000)
            timestamp_str = str(current_time_ms)
            message = timestamp_str + method + path + body

            if isinstance(private_key, rsa.RSAPrivateKey):
                signature = private_key.sign(
                    message.encode("utf-8"),
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                signature_b64 = base64.b64encode(signature).decode("utf-8")
                headers["KS-TS"] = timestamp_str
                headers["Authorization"] = f"Kalshi {self.api_key_id}:{signature_b64}"
        except ImportError:
            logger.warning("cryptography library not installed. Install with: pip install cryptography")
        except Exception as e:
            logger.error(f"Failed to sign request: {e}")

        return headers

    def get_markets(
        self,
        limit: int = 100,
        status: str = "open",
        event_ticker: Optional[str] = None
    ) -> DataSourceResponse:
        """Get list of markets.

        Args:
            limit: Maximum number of markets (default 100)
            status: Market status ('open', 'closed', 'settled')
            event_ticker: Filter by event ticker

        Returns:
            DataSourceResponse with list of markets
        """
        self._log_request("get_markets", {
            "limit": limit, "status": status, "event_ticker": event_ticker
        })
        try:
            params: Dict[str, Any] = {"limit": limit, "status": status}
            if event_ticker:
                params["event_ticker"] = event_ticker

            path = "/trade-api/v2/markets"
            headers = self._sign_request("GET", path)

            response = self.session.get(
                f"{self.BASE_URL}/markets",
                params=params,
                headers=headers,
                timeout=20
            )
            response.raise_for_status()
            data = response.json()

            markets = data.get("markets", []) if isinstance(data, dict) else data
            count = len(markets) if isinstance(markets, list) else 1
            self._log_success("get_markets", count)
            return DataSourceResponse.success_response(
                data=markets,
                metadata={
                    "source": "Kalshi", "limit": limit,
                    "status": status, "event_ticker": event_ticker
                }
            )
        except Exception as e:
            return handle_request_error(e, "Kalshi", "get_markets")

    def get_market(self, ticker: str) -> DataSourceResponse:
        """Get single market details by ticker.

        Args:
            ticker: Kalshi market ticker

        Returns:
            DataSourceResponse with market details
        """
        self._log_request("get_market", {"ticker": ticker})
        try:
            path = f"/trade-api/v2/markets/{ticker}"
            headers = self._sign_request("GET", path)

            response = self.session.get(
                f"{self.BASE_URL}/markets/{ticker}",
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            market_data = data.get("market", data) if isinstance(data, dict) else data
            self._log_success("get_market", 1)
            return DataSourceResponse.success_response(
                data=market_data,
                metadata={"source": "Kalshi", "ticker": ticker}
            )
        except Exception as e:
            return handle_request_error(e, "Kalshi", "get_market")

    def get_order_book(self, ticker: str, depth: int = 10) -> DataSourceResponse:
        """Get order book for a market.

        Args:
            ticker: Kalshi market ticker
            depth: Order book depth (default 10)

        Returns:
            DataSourceResponse with bids and asks
        """
        self._log_request("get_order_book", {"ticker": ticker, "depth": depth})
        try:
            path = f"/trade-api/v2/markets/{ticker}/orderbook"
            headers = self._sign_request("GET", path)
            params = {"depth": depth}

            response = self.session.get(
                f"{self.BASE_URL}/markets/{ticker}/orderbook",
                params=params,
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            ob_data = data.get("orderbook", data) if isinstance(data, dict) else data
            self._log_success("get_order_book", 1)
            return DataSourceResponse.success_response(
                data=ob_data,
                metadata={"source": "Kalshi", "ticker": ticker, "depth": depth}
            )
        except Exception as e:
            return handle_request_error(e, "Kalshi", "get_order_book")

    def get_trades(self, ticker: str, limit: int = 100) -> DataSourceResponse:
        """Get recent trades for a market.

        Args:
            ticker: Kalshi market ticker
            limit: Maximum number of trades (default 100)

        Returns:
            DataSourceResponse with recent trades
        """
        self._log_request("get_trades", {"ticker": ticker, "limit": limit})
        try:
            path = f"/trade-api/v2/markets/{ticker}/trades"
            headers = self._sign_request("GET", path)
            params = {"limit": limit}

            response = self.session.get(
                f"{self.BASE_URL}/markets/{ticker}/trades",
                params=params,
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            trades = data.get("trades", []) if isinstance(data, dict) else data
            count = len(trades) if isinstance(trades, list) else 1
            self._log_success("get_trades", count)
            return DataSourceResponse.success_response(
                data=trades,
                metadata={"source": "Kalshi", "ticker": ticker, "limit": limit}
            )
        except Exception as e:
            return handle_request_error(e, "Kalshi", "get_trades")

    def get_event(self, event_ticker: str) -> DataSourceResponse:
        """Get event details by ticker.

        Args:
            event_ticker: Kalshi event ticker

        Returns:
            DataSourceResponse with event details
        """
        self._log_request("get_event", {"event_ticker": event_ticker})
        try:
            path = f"/trade-api/v2/events/{event_ticker}"
            headers = self._sign_request("GET", path)

            response = self.session.get(
                f"{self.BASE_URL}/events/{event_ticker}",
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            event_data = data.get("event", data) if isinstance(data, dict) else data
            self._log_success("get_event", 1)
            return DataSourceResponse.success_response(
                data=event_data,
                metadata={"source": "Kalshi", "event_ticker": event_ticker}
            )
        except Exception as e:
            return handle_request_error(e, "Kalshi", "get_event")

    def get_price_history(
        self,
        ticker: str,
        start_ts: int,
        end_ts: int
    ) -> DataSourceResponse:
        """Get candlestick price history for a market.

        Args:
            ticker: Kalshi market ticker
            start_ts: Start timestamp (Unix seconds)
            end_ts: End timestamp (Unix seconds)

        Returns:
            DataSourceResponse with candlestick data
        """
        self._log_request("get_price_history", {
            "ticker": ticker, "start_ts": start_ts, "end_ts": end_ts
        })
        try:
            path = f"/trade-api/v2/markets/{ticker}/candlesticks"
            headers = self._sign_request("GET", path)
            params = {"start_ts": start_ts, "end_ts": end_ts}

            response = self.session.get(
                f"{self.BASE_URL}/markets/{ticker}/candlesticks",
                params=params,
                headers=headers,
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            candles = data.get("candlesticks", []) if isinstance(data, dict) else data
            count = len(candles) if isinstance(candles, list) else 1
            self._log_success("get_price_history", count)
            return DataSourceResponse.success_response(
                data=candles,
                metadata={
                    "source": "Kalshi", "ticker": ticker,
                    "start_ts": start_ts, "end_ts": end_ts
                }
            )
        except Exception as e:
            return handle_request_error(e, "Kalshi", "get_price_history")

    def get_markets_by_category(
        self, category: str = "economics", limit: int = 20
    ) -> DataSourceResponse:
        """Get active Kalshi markets by category.

        Args:
            category: One of economics, weather, politics, crypto, equities, entertainment
            limit: Maximum number of markets
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/markets",
                params={"category": category, "limit": limit, "status": "open"},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Kalshi", "category": category},
            )
        except Exception as e:
            return handle_request_error(e, "Kalshi", "get_markets_by_category")

    def get_categories(self) -> DataSourceResponse:
        """Get available market categories."""
        items = [{"id": k, "description": v} for k, v in self.CATEGORIES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "Kalshi", "count": len(items)},
        )

    # ---- MarketDataSource abstract methods ----

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Not applicable for prediction markets."""
        return DataSourceResponse.error_response(
            error="Not applicable for prediction markets. Use get_market() for market data."
        )

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get OHLCV-like kline data from market candlestick history.

        Args:
            symbol: Kalshi market ticker
            period: Time period (unused, Kalshi uses its own resolution)
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)

        Returns:
            DataSourceResponse with kline-like data
        """
        self._log_request("get_klines", {
            "symbol": symbol, "period": period,
            "start_date": start_date, "end_date": end_date
        })
        try:
            import datetime
            try:
                start_dt = datetime.datetime.strptime(start_date, "%Y%m%d")
                end_dt = datetime.datetime.strptime(end_date, "%Y%m%d")
                start_ts = int(start_dt.timestamp())
                end_ts = int(end_dt.timestamp())
            except (ValueError, TypeError):
                start_ts = 0
                end_ts = int(time.time())

            candle_result = self.get_price_history(symbol, start_ts, end_ts)
            if not candle_result.success:
                return candle_result

            candle_data = candle_result.data
            klines = []
            if isinstance(candle_data, list):
                for entry in candle_data:
                    if isinstance(entry, dict):
                        klines.append({
                            "timestamp": entry.get("ts", entry.get("start_ts", 0)),
                            "open": entry.get("open", 0),
                            "high": entry.get("high", 0),
                            "low": entry.get("low", 0),
                            "close": entry.get("close", 0),
                            "volume": entry.get("volume", 0),
                            "probability": entry.get("close", 0),
                        })

            return DataSourceResponse.success_response(
                data=klines,
                metadata={
                    "source": "Kalshi", "ticker": symbol,
                    "period": period, "type": "prediction_market_klines"
                }
            )
        except Exception as e:
            return self._handle_error("get_klines", e)

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """Get real-time quotes for market tickers.

        Args:
            symbols: List of Kalshi market tickers

        Returns:
            DataSourceResponse with real-time quotes
        """
        self._log_request("get_realtime_quote", {"symbols": symbols})
        try:
            quotes = {}
            for ticker in symbols:
                try:
                    result = self.get_market(ticker)
                    if result.success and isinstance(result.data, dict):
                        market_data = result.data
                        quotes[ticker] = {
                            "title": market_data.get("title", ""),
                            "subtitle": market_data.get("subtitle", ""),
                            "yes_bid": market_data.get("yes_bid", 0),
                            "yes_ask": market_data.get("yes_ask", 0),
                            "no_bid": market_data.get("no_bid", 0),
                            "no_ask": market_data.get("no_ask", 0),
                            "last_price": market_data.get("last_price", 0),
                            "volume": market_data.get("volume", 0),
                            "status": market_data.get("status", ""),
                        }
                    else:
                        quotes[ticker] = {"error": "Failed to fetch market data"}
                except Exception as e:
                    logger.warning(f"Failed to fetch quote for {ticker}: {e}")
                    quotes[ticker] = {"error": str(e)}

            return DataSourceResponse.success_response(
                data=quotes,
                metadata={
                    "source": "Kalshi", "count": len(symbols),
                    "successful": sum(1 for q in quotes.values() if "error" not in q)
                }
            )
        except Exception as e:
            return self._handle_error("get_realtime_quote", e)
