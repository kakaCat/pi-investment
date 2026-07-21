"""Polymarket prediction market data source.

Provides access to Polymarket Gamma API for prediction market data including
markets, order books, price history, and real-time quotes.

No API key required for public endpoints.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import MarketDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class PolymarketSource(MarketDataSource):
    """Polymarket prediction market data source.

    Polymarket is the world's largest decentralized prediction market
    built on Polygon. The Gamma API provides public access to:
    - Market listings with filtering by tag, volume, liquidity
    - Individual market details with outcomes and probabilities
    - Order book depth per token
    - Historical price time series

    No API key is required for public endpoints.
    """

    BASE_URL = "https://gamma-api.polymarket.com"

    CATEGORIES = {
        "politics": "Political events, elections",
        "economics": "Economic indicators, Fed decisions",
        "crypto": "Cryptocurrency price predictions",
        "sports": "Sports outcomes",
        "science": "Scientific/technology predictions",
        "world": "Global events, conflicts",
    }

    def __init__(self):
        """Initialize Polymarket data source."""
        super().__init__(name="Polymarket", requires_api_key=False)
        self.session = SessionManager.get_session("polymarket")

    def validate_config(self) -> bool:
        """Validate configuration. No API key needed."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection by fetching a single market."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/markets",
                params={"limit": 1, "active": "true"},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Polymarket", "sample": data},
                metadata={"source": "Polymarket", "base_url": self.BASE_URL}
            )
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_markets(
        self,
        limit: int = 100,
        tag: Optional[str] = None,
        active: bool = True
    ) -> DataSourceResponse:
        """Get list of prediction markets.

        Args:
            limit: Maximum number of markets (default 100)
            tag: Filter by tag/category (e.g., 'politics', 'crypto', 'sports')
            active: Only return active markets (default True)

        Returns:
            DataSourceResponse with list of markets
        """
        self._log_request("get_markets", {"limit": limit, "tag": tag, "active": active})
        try:
            params: Dict[str, Any] = {"limit": limit}
            if active:
                params["active"] = "true"
            if tag:
                params["tag"] = tag

            response = self.session.get(
                f"{self.BASE_URL}/markets",
                params=params,
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            self._log_success("get_markets", len(data) if isinstance(data, list) else 1)
            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "Polymarket", "limit": limit, "tag": tag, "active": active}
            )
        except Exception as e:
            return handle_request_error(e, "Polymarket", "get_markets")

    def get_market(self, market_id: str) -> DataSourceResponse:
        """Get single market details by ID/condition-id.

        Args:
            market_id: Polymarket market ID (condition ID or slug)

        Returns:
            DataSourceResponse with market details
        """
        self._log_request("get_market", {"market_id": market_id})
        try:
            response = self.session.get(
                f"{self.BASE_URL}/markets/{market_id}",
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            self._log_success("get_market", 1)
            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "Polymarket", "market_id": market_id}
            )
        except Exception as e:
            return handle_request_error(e, "Polymarket", "get_market")

    def get_order_book(self, token_id: str) -> DataSourceResponse:
        """Get order book for a specific outcome token.

        Args:
            token_id: Polymarket CLOB token ID

        Returns:
            DataSourceResponse with bids and asks
        """
        self._log_request("get_order_book", {"token_id": token_id})
        try:
            response = self.session.get(
                f"{self.BASE_URL}/orderbooks",
                params={"token_id": token_id},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            self._log_success("get_order_book", 1)
            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "Polymarket", "token_id": token_id}
            )
        except Exception as e:
            return handle_request_error(e, "Polymarket", "get_order_book")

    def get_price_history(
        self,
        market_id: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        interval: str = "1d"
    ) -> DataSourceResponse:
        """Get historical price data for a market.

        Args:
            market_id: Polymarket market ID
            start_ts: Start timestamp (Unix seconds)
            end_ts: End timestamp (Unix seconds)
            interval: Time interval ('1h', '6h', '1d', '1w', 'max')

        Returns:
            DataSourceResponse with price history
        """
        self._log_request("get_price_history", {
            "market_id": market_id, "start_ts": start_ts,
            "end_ts": end_ts, "interval": interval
        })
        try:
            params: Dict[str, Any] = {"interval": interval}
            if start_ts is not None:
                params["startTs"] = start_ts
            if end_ts is not None:
                params["endTs"] = end_ts

            response = self.session.get(
                f"{self.BASE_URL}/markets/{market_id}/prices",
                params=params,
                timeout=20
            )
            response.raise_for_status()
            data = response.json()
            self._log_success("get_price_history", len(data) if isinstance(data, list) else 1)
            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Polymarket", "market_id": market_id,
                    "interval": interval, "start_ts": start_ts, "end_ts": end_ts
                }
            )
        except Exception as e:
            return handle_request_error(e, "Polymarket", "get_price_history")

    def get_markets_by_category(
        self, category: str = "economics", limit: int = 20
    ) -> DataSourceResponse:
        """Get active markets by category tag.

        Args:
            category: Category tag (politics, economics, crypto, sports, science, world)
            limit: Maximum number of markets

        Returns:
            DataSourceResponse with filtered markets
        """
        return self.get_markets(limit=limit, tag=category, active=True)

    def get_categories(self) -> DataSourceResponse:
        """Get available market categories."""
        items = [{"id": k, "description": v} for k, v in self.CATEGORIES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "Polymarket", "count": len(items)},
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
        """Get OHLCV-like kline data from market price history.

        Args:
            symbol: Polymarket market ID (used as symbol)
            period: 'hourly', 'daily', 'weekly', 'monthly'
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
            interval_map = {
                "hourly": "1h", "6h": "6h", "daily": "1d",
                "weekly": "1w", "monthly": "max"
            }
            interval = interval_map.get(period, "1d")

            import datetime
            try:
                start_dt = datetime.datetime.strptime(start_date, "%Y%m%d")
                end_dt = datetime.datetime.strptime(end_date, "%Y%m%d")
                start_ts = int(start_dt.timestamp())
                end_ts = int(end_dt.timestamp())
            except (ValueError, TypeError):
                start_ts = None
                end_ts = None

            price_result = self.get_price_history(symbol, start_ts, end_ts, interval)
            if not price_result.success:
                return price_result

            price_data = price_result.data
            klines = []
            if isinstance(price_data, list):
                for entry in price_data:
                    if isinstance(entry, dict):
                        price_val = entry.get("price", 0)
                        ts = entry.get("t", entry.get("timestamp", 0))
                        klines.append({
                            "timestamp": ts,
                            "open": price_val,
                            "high": price_val,
                            "low": price_val,
                            "close": price_val,
                            "volume": entry.get("volume", 0),
                            "probability": price_val,
                        })

            return DataSourceResponse.success_response(
                data=klines,
                metadata={
                    "source": "Polymarket", "market_id": symbol,
                    "period": period, "interval": interval,
                    "type": "prediction_market_klines"
                }
            )
        except Exception as e:
            return self._handle_error("get_klines", e)

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """Get real-time quotes for market IDs.

        Args:
            symbols: List of Polymarket market IDs

        Returns:
            DataSourceResponse with real-time quotes
        """
        self._log_request("get_realtime_quote", {"symbols": symbols})
        try:
            quotes = {}
            for market_id in symbols:
                try:
                    result = self.get_market(market_id)
                    if result.success and isinstance(result.data, dict):
                        market_data = result.data
                        outcomes = market_data.get("outcomes", [])
                        outcome_prices = {}
                        for outcome in outcomes:
                            if isinstance(outcome, dict):
                                name = outcome.get("outcome") or outcome.get("title", "")
                                price = outcome.get("price") or outcome.get("lastTradePrice", 0)
                                outcome_prices[name] = price
                        quotes[market_id] = {
                            "question": market_data.get("question", ""),
                            "outcomes": outcome_prices,
                            "volume": market_data.get("volumeNum", market_data.get("volume24hr", 0)),
                            "updated": market_data.get("updatedAt", market_data.get("endDate", "")),
                        }
                    else:
                        quotes[market_id] = {"error": "Failed to fetch market data"}
                except Exception as e:
                    logger.warning(f"Failed to fetch quote for {market_id}: {e}")
                    quotes[market_id] = {"error": str(e)}

            return DataSourceResponse.success_response(
                data=quotes,
                metadata={
                    "source": "Polymarket", "count": len(symbols),
                    "successful": sum(1 for q in quotes.values() if "error" not in q)
                }
            )
        except Exception as e:
            return self._handle_error("get_realtime_quote", e)
