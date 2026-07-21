"""Coinglass cryptocurrency derivatives data source.

Provides access to crypto derivatives data including futures, options,
liquidations, funding rates, and open interest.

API Documentation: https://coinglass.github.io/API-Reference/
No API key required for public endpoints.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CoinglassSource(EconomicDataSource):
    """Coinglass cryptocurrency derivatives data source.

    Provides access to:
    - Futures open interest
    - Liquidation data
    - Funding rates
    - Long/short ratios
    - Options data
    - Exchange data

    No API key required for public endpoints.
    """

    BASE_URL = "https://open-api.coinglass.com/public/v2"

    # Supported exchanges
    EXCHANGES = ["Binance", "OKX", "Bybit", "Bitget", "dYdX", "Huobi", "Kraken"]

    # Supported symbols
    SYMBOLS = ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "DOGE", "MATIC", "DOT", "AVAX"]

    def __init__(self):
        """Initialize Coinglass data source."""
        super().__init__(name="Coinglass", requires_api_key=False)
        self.session = SessionManager.get_session("coinglass")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Coinglass API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/indicator/global-long-short-account-ratio",
                params={"symbol": "BTC"},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Coinglass"},
                metadata={"source": "Coinglass", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Coinglass connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to Coinglass API.

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

    def get_open_interest(
        self,
        symbol: str = "BTC",
        interval: str = "0"
    ) -> DataSourceResponse:
        """Get futures open interest data.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
            interval: Time interval ('0' for latest, '1' for 24h, '2' for 7d)

        Returns:
            DataSourceResponse with open interest data
        """
        try:
            data = self._make_request(
                "indicator/open-interest",
                params={"symbol": symbol, "interval": interval}
            )

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Coinglass",
                    "symbol": symbol,
                    "interval": interval
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinglass", "get_open_interest")

    def get_liquidations(
        self,
        symbol: str = "BTC",
        interval: str = "1"
    ) -> DataSourceResponse:
        """Get liquidation data.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
            interval: Time interval ('1' for 24h, '2' for 7d, '3' for 30d)

        Returns:
            DataSourceResponse with liquidation data
        """
        try:
            data = self._make_request(
                "indicator/liquidation",
                params={"symbol": symbol, "interval": interval}
            )

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Coinglass",
                    "symbol": symbol,
                    "interval": interval
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinglass", "get_liquidations")

    def get_funding_rate(
        self,
        symbol: str = "BTC",
        exchange: Optional[str] = None
    ) -> DataSourceResponse:
        """Get funding rate data.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
            exchange: Exchange name (optional, returns all if not specified)

        Returns:
            DataSourceResponse with funding rate data
        """
        try:
            params = {"symbol": symbol}
            if exchange:
                params["exchange"] = exchange

            data = self._make_request("indicator/funding-rate", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Coinglass",
                    "symbol": symbol,
                    "exchange": exchange
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinglass", "get_funding_rate")

    def get_long_short_ratio(
        self,
        symbol: str = "BTC",
        interval: str = "0"
    ) -> DataSourceResponse:
        """Get long/short account ratio.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
            interval: Time interval ('0' for latest, '1' for 24h)

        Returns:
            DataSourceResponse with long/short ratio data
        """
        try:
            data = self._make_request(
                "indicator/global-long-short-account-ratio",
                params={"symbol": symbol, "interval": interval}
            )

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Coinglass",
                    "symbol": symbol,
                    "interval": interval
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinglass", "get_long_short_ratio")

    def get_exchange_open_interest(
        self,
        symbol: str = "BTC"
    ) -> DataSourceResponse:
        """Get open interest by exchange.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')

        Returns:
            DataSourceResponse with exchange open interest data
        """
        try:
            data = self._make_request(
                "indicator/open-interest-aggregated-exchange",
                params={"symbol": symbol}
            )

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Coinglass",
                    "symbol": symbol
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinglass", "get_exchange_open_interest")

    def get_options_volume(
        self,
        symbol: str = "BTC"
    ) -> DataSourceResponse:
        """Get options trading volume.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')

        Returns:
            DataSourceResponse with options volume data
        """
        try:
            data = self._make_request(
                "indicator/options-volume",
                params={"symbol": symbol}
            )

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Coinglass",
                    "symbol": symbol
                }
            )
        except Exception as e:
            return handle_request_error(e, "Coinglass", "get_options_volume")
