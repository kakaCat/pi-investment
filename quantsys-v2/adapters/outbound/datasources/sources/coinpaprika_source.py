"""Coinpaprika cryptocurrency data source.

Provides access to 7000+ cryptocurrencies with market data, OHLCV,
exchanges, events, and more.

API Documentation: https://api.coinpaprika.com/
No API key required for public endpoints.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CoinpaprikaSource(EconomicDataSource):
    """Coinpaprika cryptocurrency data source.

    Provides access to:
    - 7000+ cryptocurrencies
    - Market data (price, volume, market cap)
    - OHLCV historical data
    - Exchange information
    - Events and news
    - Global market overview

    No API key required.
    """

    BASE_URL = "https://api.coinpaprika.com/v1"

    def __init__(self):
        """Initialize Coinpaprika data source."""
        super().__init__(name="Coinpaprika", requires_api_key=False)
        self.session = SessionManager.get_session("coinpaprika")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Coinpaprika API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(f"{self.BASE_URL}/global", timeout=10)
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Coinpaprika"},
                metadata={"source": "Coinpaprika", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Coinpaprika connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make request to Coinpaprika API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_global_market(self) -> DataSourceResponse:
        """Get global cryptocurrency market overview.

        Returns:
            DataSourceResponse with global market data
        """
        try:
            data = self._make_request("global")

            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "Coinpaprika"}
            )
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_global_market")

    def get_coins(self, limit: int = 100) -> DataSourceResponse:
        """Get list of all coins.

        Args:
            limit: Maximum number of coins to return

        Returns:
            DataSourceResponse with coin list
        """
        try:
            data = self._make_request("coins")

            if isinstance(data, list):
                coins = data[:limit]
                return DataSourceResponse.success_response(
                    data=coins,
                    metadata={
                        "source": "Coinpaprika",
                        "total_count": len(data),
                        "returned_count": len(coins)
                    }
                )

            return DataSourceResponse.success_response(data=data)
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_coins")

    def get_coin(self, coin_id: str) -> DataSourceResponse:
        """Get detailed information for a specific coin.

        Args:
            coin_id: Coin identifier (e.g., 'btc-bitcoin', 'eth-ethereum')

        Returns:
            DataSourceResponse with coin details
        """
        try:
            data = self._make_request(f"coins/{coin_id}")

            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "Coinpaprika", "coin_id": coin_id}
            )
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_coin")

    def get_coin_ohlcv(
        self,
        coin_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 365
    ) -> DataSourceResponse:
        """Get OHLCV historical data for a coin.

        Args:
            coin_id: Coin identifier (e.g., 'btc-bitcoin')
            start: Start date (YYYY-MM-DD format)
            end: End date (YYYY-MM-DD format)
            limit: Maximum number of data points (max 366)

        Returns:
            DataSourceResponse with OHLCV data
        """
        try:
            params = {"limit": min(limit, 366)}
            if start:
                params["start"] = start
            if end:
                params["end"] = end

            data = self._make_request(f"coins/{coin_id}/ohlcv/historical", params=params)

            if isinstance(data, list):
                return DataSourceResponse.success_response(
                    data=data,
                    metadata={
                        "source": "Coinpaprika",
                        "coin_id": coin_id,
                        "count": len(data)
                    }
                )

            return DataSourceResponse.success_response(data=data)
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_coin_ohlcv")

    def get_coin_today_ohlcv(self, coin_id: str, quote: str = "usd") -> DataSourceResponse:
        """Get today's OHLCV for a coin.

        Args:
            coin_id: Coin identifier (e.g., 'btc-bitcoin')
            quote: Quote currency (default: 'usd')

        Returns:
            DataSourceResponse with today's OHLCV
        """
        try:
            params = {"quote": quote}
            data = self._make_request(f"coins/{coin_id}/ohlcv/today", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Coinpaprika",
                    "coin_id": coin_id,
                    "quote": quote
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_coin_today_ohlcv")

    def get_exchanges(self) -> DataSourceResponse:
        """Get list of all exchanges.

        Returns:
            DataSourceResponse with exchange list
        """
        try:
            data = self._make_request("exchanges")

            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "Coinpaprika", "count": len(data) if isinstance(data, list) else 0}
            )
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_exchanges")

    def get_exchange(self, exchange_id: str) -> DataSourceResponse:
        """Get detailed information for a specific exchange.

        Args:
            exchange_id: Exchange identifier (e.g., 'binance')

        Returns:
            DataSourceResponse with exchange details
        """
        try:
            data = self._make_request(f"exchanges/{exchange_id}")

            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "Coinpaprika", "exchange_id": exchange_id}
            )
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_exchange")

    def get_tickers(self, limit: int = 100) -> DataSourceResponse:
        """Get ticker data for all coins.

        Args:
            limit: Maximum number of tickers to return

        Returns:
            DataSourceResponse with ticker data
        """
        try:
            data = self._make_request("tickers")

            if isinstance(data, list):
                tickers = data[:limit]
                return DataSourceResponse.success_response(
                    data=tickers,
                    metadata={
                        "source": "Coinpaprika",
                        "total_count": len(data),
                        "returned_count": len(tickers)
                    }
                )

            return DataSourceResponse.success_response(data=data)
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_tickers")

    def get_ticker(self, coin_id: str, quotes: str = "USD") -> DataSourceResponse:
        """Get ticker data for a specific coin.

        Args:
            coin_id: Coin identifier (e.g., 'btc-bitcoin')
            quotes: Quote currencies (comma-separated, e.g., 'USD,BTC')

        Returns:
            DataSourceResponse with ticker data
        """
        try:
            params = {"quotes": quotes}
            data = self._make_request(f"tickers/{coin_id}", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Coinpaprika",
                    "coin_id": coin_id,
                    "quotes": quotes
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "get_ticker")

    def search(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for coins, exchanges, or people.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            DataSourceResponse with search results
        """
        try:
            params = {"q": query, "limit": limit}
            data = self._make_request("search", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Coinpaprika",
                    "query": query,
                    "limit": limit
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinpaprika", "search")
