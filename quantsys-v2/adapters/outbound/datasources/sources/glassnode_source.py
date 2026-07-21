"""Glassnode on-chain data source.

Provides access to blockchain analytics and on-chain metrics for Bitcoin,
Ethereum, and other cryptocurrencies.

API Documentation: https://docs.glassnode.com/
Requires API key: https://studio.glassnode.com/settings/api
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class GlassnodeSource(EconomicDataSource):
    """Glassnode on-chain data source.

    Provides access to:
    - On-chain metrics (active addresses, transaction volume, etc.)
    - Market indicators (MVRV, NVT, Puell Multiple, etc.)
    - Mining data (hash rate, difficulty, miner revenue)
    - Exchange flows (inflows, outflows, reserves)
    - Derivatives data (futures, options)

    Requires API key.
    """

    BASE_URL = "https://api.glassnode.com/v1/metrics"

    # Supported assets
    ASSETS = ["BTC", "ETH", "LTC", "XRP", "BCH", "BSV", "EOS", "XTZ", "ADA", "LINK"]

    # Common metrics
    METRICS = {
        "active_addresses": "addresses/active_count",
        "transaction_count": "transactions/count",
        "transaction_volume": "transactions/transfers_volume_sum",
        "hash_rate": "mining/hash_rate_mean",
        "difficulty": "mining/difficulty_latest",
        "mvrv": "indicators/mvrv",
        "nvt": "indicators/nvt",
        "sopr": "indicators/sopr",
        "exchange_inflow": "transactions/transfers_to_exchanges_sum",
        "exchange_outflow": "transactions/transfers_from_exchanges_sum",
        "exchange_balance": "distribution/balance_exchanges",
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Glassnode data source.

        Args:
            api_key: Glassnode API key (or set GLASSNODE_API_KEY env var)
        """
        super().__init__(name="Glassnode", requires_api_key=True)
        self.api_key = api_key or os.getenv("GLASSNODE_API_KEY")
        self.session = SessionManager.get_session("glassnode")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("Glassnode API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Glassnode API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set GLASSNODE_API_KEY environment variable."
            )

        try:
            # Test with a simple metric
            response = self.session.get(
                f"{self.BASE_URL}/addresses/active_count",
                params={"a": "BTC", "api_key": self.api_key},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Glassnode"},
                metadata={"source": "Glassnode", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Glassnode connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(
        self,
        metric: str,
        asset: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make request to Glassnode API.

        Args:
            metric: Metric path (e.g., 'addresses/active_count')
            asset: Asset symbol (e.g., 'BTC')
            params: Additional query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{metric}"
        request_params = {"a": asset, "api_key": self.api_key}
        if params:
            request_params.update(params)

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_metric(
        self,
        metric: str,
        asset: str = "BTC",
        since: Optional[str] = None,
        until: Optional[str] = None,
        interval: str = "24h"
    ) -> DataSourceResponse:
        """Get on-chain metric data.

        Args:
            metric: Metric path (e.g., 'addresses/active_count')
            asset: Asset symbol (default: 'BTC')
            since: Start timestamp (Unix or ISO 8601)
            until: End timestamp (Unix or ISO 8601)
            interval: Data interval ('1h', '24h', '1w', '1month')

        Returns:
            DataSourceResponse with metric data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured"
            )

        try:
            params = {"i": interval}
            if since:
                params["s"] = since
            if until:
                params["u"] = until

            data = self._make_request(metric, asset, params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Glassnode",
                    "metric": metric,
                    "asset": asset,
                    "interval": interval
                }
            )
        except Exception as e:
            return handle_request_error(e, "Glassnode", "get_metric")

    def get_active_addresses(
        self,
        asset: str = "BTC",
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> DataSourceResponse:
        """Get active addresses count.

        Args:
            asset: Asset symbol (default: 'BTC')
            since: Start timestamp
            until: End timestamp

        Returns:
            DataSourceResponse with active addresses data
        """
        return self.get_metric(
            metric=self.METRICS["active_addresses"],
            asset=asset,
            since=since,
            until=until
        )

    def get_transaction_volume(
        self,
        asset: str = "BTC",
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> DataSourceResponse:
        """Get transaction volume.

        Args:
            asset: Asset symbol (default: 'BTC')
            since: Start timestamp
            until: End timestamp

        Returns:
            DataSourceResponse with transaction volume data
        """
        return self.get_metric(
            metric=self.METRICS["transaction_volume"],
            asset=asset,
            since=since,
            until=until
        )

    def get_hash_rate(
        self,
        asset: str = "BTC",
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> DataSourceResponse:
        """Get mining hash rate.

        Args:
            asset: Asset symbol (default: 'BTC')
            since: Start timestamp
            until: End timestamp

        Returns:
            DataSourceResponse with hash rate data
        """
        return self.get_metric(
            metric=self.METRICS["hash_rate"],
            asset=asset,
            since=since,
            until=until
        )

    def get_mvrv(
        self,
        asset: str = "BTC",
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> DataSourceResponse:
        """Get MVRV (Market Value to Realized Value) ratio.

        Args:
            asset: Asset symbol (default: 'BTC')
            since: Start timestamp
            until: End timestamp

        Returns:
            DataSourceResponse with MVRV data
        """
        return self.get_metric(
            metric=self.METRICS["mvrv"],
            asset=asset,
            since=since,
            until=until
        )

    def get_exchange_flows(
        self,
        asset: str = "BTC",
        flow_type: str = "inflow",
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> DataSourceResponse:
        """Get exchange inflow/outflow data.

        Args:
            asset: Asset symbol (default: 'BTC')
            flow_type: 'inflow' or 'outflow'
            since: Start timestamp
            until: End timestamp

        Returns:
            DataSourceResponse with exchange flow data
        """
        if flow_type == "inflow":
            metric = self.METRICS["exchange_inflow"]
        elif flow_type == "outflow":
            metric = self.METRICS["exchange_outflow"]
        else:
            return DataSourceResponse.error_response(
                error=f"Invalid flow_type: {flow_type}. Use 'inflow' or 'outflow'."
            )

        return self.get_metric(
            metric=metric,
            asset=asset,
            since=since,
            until=until
        )
