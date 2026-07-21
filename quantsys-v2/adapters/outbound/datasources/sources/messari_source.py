"""Messari cryptocurrency research data source.

Provides access to crypto asset profiles, metrics, news, and research reports.

API Documentation: https://messari.io/api/docs
Requires API key for full access: https://messari.io/account/api
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class MessariSource(EconomicDataSource):
    """Messari cryptocurrency research data source.

    Provides access to:
    - Asset profiles and metrics
    - Market data (price, volume, market cap)
    - News and research reports
    - Timeseries data
    - Qualitative information

    API key optional (free tier available).
    """

    BASE_URL = "https://data.messari.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Messari data source.

        Args:
            api_key: Messari API key (optional, or set MESSARI_API_KEY env var)
        """
        super().__init__(name="Messari", requires_api_key=False)
        self.api_key = api_key or os.getenv("MESSARI_API_KEY")
        self.session = SessionManager.get_session("messari")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (API key is optional)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Messari API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            headers = {}
            if self.api_key:
                headers["x-messari-api-key"] = self.api_key

            response = self.session.get(
                f"{self.BASE_URL}/assets",
                headers=headers,
                params={"limit": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Messari", "authenticated": bool(self.api_key)},
                metadata={"source": "Messari", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Messari connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to Messari API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {}
        if self.api_key:
            headers["x-messari-api-key"] = self.api_key

        response = self.session.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_assets(self, limit: int = 100, fields: Optional[str] = None) -> DataSourceResponse:
        """Get list of all assets.

        Args:
            limit: Maximum number of assets to return
            fields: Comma-separated list of fields to return

        Returns:
            DataSourceResponse with asset list
        """
        try:
            params = {"limit": limit}
            if fields:
                params["fields"] = fields

            data = self._make_request("assets", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Messari",
                    "limit": limit
                }
            )
        except Exception as e:
            return handle_request_error(e, "Messari", "get_assets")

    def get_asset(self, asset_key: str, fields: Optional[str] = None) -> DataSourceResponse:
        """Get detailed information for a specific asset.

        Args:
            asset_key: Asset identifier (e.g., 'btc', 'eth', 'bitcoin')
            fields: Comma-separated list of fields to return

        Returns:
            DataSourceResponse with asset details
        """
        try:
            params = {}
            if fields:
                params["fields"] = fields

            data = self._make_request(f"assets/{asset_key}", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Messari",
                    "asset_key": asset_key
                }
            )
        except Exception as e:
            return handle_request_error(e, "Messari", "get_asset")

    def get_asset_metrics(self, asset_key: str) -> DataSourceResponse:
        """Get quantitative metrics for an asset.

        Args:
            asset_key: Asset identifier (e.g., 'btc', 'eth')

        Returns:
            DataSourceResponse with asset metrics
        """
        try:
            data = self._make_request(f"assets/{asset_key}/metrics")

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Messari",
                    "asset_key": asset_key
                }
            )
        except Exception as e:
            return handle_request_error(e, "Messari", "get_asset_metrics")

    def get_asset_profile(self, asset_key: str) -> DataSourceResponse:
        """Get qualitative profile for an asset.

        Args:
            asset_key: Asset identifier (e.g., 'btc', 'eth')

        Returns:
            DataSourceResponse with asset profile
        """
        try:
            data = self._make_request(f"assets/{asset_key}/profile")

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Messari",
                    "asset_key": asset_key
                }
            )
        except Exception as e:
            return handle_request_error(e, "Messari", "get_asset_profile")

    def get_asset_timeseries(
        self,
        asset_key: str,
        metric: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: str = "1d"
    ) -> DataSourceResponse:
        """Get timeseries data for an asset metric.

        Args:
            asset_key: Asset identifier (e.g., 'btc', 'eth')
            metric: Metric name (e.g., 'price', 'volume', 'marketcap')
            start: Start date (ISO 8601 format)
            end: End date (ISO 8601 format)
            interval: Data interval ('1d', '1h', '5m')

        Returns:
            DataSourceResponse with timeseries data
        """
        try:
            params = {"interval": interval}
            if start:
                params["start"] = start
            if end:
                params["end"] = end

            data = self._make_request(
                f"assets/{asset_key}/metrics/{metric}/time-series",
                params=params
            )

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "Messari",
                    "asset_key": asset_key,
                    "metric": metric,
                    "interval": interval
                }
            )
        except Exception as e:
            return handle_request_error(e, "Messari", "get_asset_timeseries")

    def get_news(self, limit: int = 50, fields: Optional[str] = None) -> DataSourceResponse:
        """Get latest crypto news.

        Args:
            limit: Maximum number of news items to return
            fields: Comma-separated list of fields to return

        Returns:
            DataSourceResponse with news data
        """
        try:
            params = {"limit": limit}
            if fields:
                params["fields"] = fields

            data = self._make_request("news", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Messari",
                    "limit": limit
                }
            )
        except Exception as e:
            return handle_request_error(e, "Messari", "get_news")

    def get_markets(self, asset_key: str) -> DataSourceResponse:
        """Get market data for an asset across exchanges.

        Args:
            asset_key: Asset identifier (e.g., 'btc', 'eth')

        Returns:
            DataSourceResponse with market data
        """
        try:
            data = self._make_request(f"assets/{asset_key}/markets")

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "Messari",
                    "asset_key": asset_key
                }
            )
        except Exception as e:
            return handle_request_error(e, "Messari", "get_markets")
