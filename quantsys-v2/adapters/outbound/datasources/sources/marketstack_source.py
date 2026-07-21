"""Marketstack financial data source.

Provides access to real-time and historical stock market data for 70+ exchanges.

API Documentation: https://marketstack.com/documentation
Requires API key: https://marketstack.com/signup/free
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class MarketstackSource(EconomicDataSource):
    """Marketstack stock market data source.

    Provides access to:
    - Real-time stock prices
    - Historical EOD data
    - Intraday data
    - Splits and dividends
    - Exchange information
    - 70+ global exchanges

    Requires API key.
    """

    BASE_URL = "http://api.marketstack.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Marketstack data source.

        Args:
            api_key: Marketstack API key (or set MARKETSTACK_API_KEY env var)
        """
        super().__init__(name="Marketstack", requires_api_key=True)
        self.api_key = api_key or os.getenv("MARKETSTACK_API_KEY")
        self.session = SessionManager.get_session("marketstack")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("Marketstack API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Marketstack API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set MARKETSTACK_API_KEY environment variable."
            )

        try:
            response = self.session.get(
                f"{self.BASE_URL}/exchanges",
                params={"access_key": self.api_key, "limit": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Marketstack"},
                metadata={"source": "Marketstack", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Marketstack connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to Marketstack API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        request_params = {"access_key": self.api_key}
        if params:
            request_params.update(params)

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_eod_data(
        self,
        symbols: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100
    ) -> DataSourceResponse:
        """Get end-of-day stock data.

        Args:
            symbols: Stock symbol(s), comma-separated
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit: Maximum number of results

        Returns:
            DataSourceResponse with EOD data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"symbols": symbols, "limit": limit}
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to

            data = self._make_request("eod", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Marketstack",
                    "symbols": symbols,
                    "pagination": data.get("pagination", {})
                }
            )
        except Exception as e:
            return handle_request_error(e, "Marketstack", "get_eod_data")

    def get_intraday_data(
        self,
        symbols: str,
        interval: str = "1min",
        limit: int = 100
    ) -> DataSourceResponse:
        """Get intraday stock data.

        Args:
            symbols: Stock symbol(s), comma-separated
            interval: Time interval ('1min', '5min', '15min', '30min', '1hour')
            limit: Maximum number of results

        Returns:
            DataSourceResponse with intraday data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"symbols": symbols, "interval": interval, "limit": limit}
            data = self._make_request("intraday", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Marketstack",
                    "symbols": symbols,
                    "interval": interval
                }
            )
        except Exception as e:
            return handle_request_error(e, "Marketstack", "get_intraday_data")

    def get_exchanges(self, limit: int = 100) -> DataSourceResponse:
        """Get list of supported exchanges.

        Args:
            limit: Maximum number of results

        Returns:
            DataSourceResponse with exchange list
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"limit": limit}
            data = self._make_request("exchanges", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Marketstack",
                    "count": len(data.get("data", []))
                }
            )
        except Exception as e:
            return handle_request_error(e, "Marketstack", "get_exchanges")

    def get_tickers(
        self,
        exchange: Optional[str] = None,
        limit: int = 100
    ) -> DataSourceResponse:
        """Get list of tickers.

        Args:
            exchange: Exchange MIC code (optional)
            limit: Maximum number of results

        Returns:
            DataSourceResponse with ticker list
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"limit": limit}
            if exchange:
                params["exchange"] = exchange

            data = self._make_request("tickers", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Marketstack",
                    "exchange": exchange,
                    "count": len(data.get("data", []))
                }
            )
        except Exception as e:
            return handle_request_error(e, "Marketstack", "get_tickers")

    def get_splits(
        self,
        symbols: str,
        limit: int = 100
    ) -> DataSourceResponse:
        """Get stock splits data.

        Args:
            symbols: Stock symbol(s), comma-separated
            limit: Maximum number of results

        Returns:
            DataSourceResponse with splits data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"symbols": symbols, "limit": limit}
            data = self._make_request("splits", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Marketstack",
                    "symbols": symbols
                }
            )
        except Exception as e:
            return handle_request_error(e, "Marketstack", "get_splits")

    def get_dividends(
        self,
        symbols: str,
        limit: int = 100
    ) -> DataSourceResponse:
        """Get dividends data.

        Args:
            symbols: Stock symbol(s), comma-separated
            limit: Maximum number of results

        Returns:
            DataSourceResponse with dividends data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"symbols": symbols, "limit": limit}
            data = self._make_request("dividends", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Marketstack",
                    "symbols": symbols
                }
            )
        except Exception as e:
            return handle_request_error(e, "Marketstack", "get_dividends")
