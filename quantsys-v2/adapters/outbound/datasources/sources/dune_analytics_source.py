"""Dune Analytics on-chain crypto data source.
Provides community-created blockchain queries and dashboards. Requires API key.
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class DuneAnalyticsSource(EconomicDataSource):
    """Dune Analytics blockchain data query source.
    SQL queries on blockchain data, protocol metrics, token flows, DEX/NFT activity.
    Economic: on-chain activity monitoring, DeFi protocol health, crypto capital flows."""

    BASE_URL = "https://api.dune.com/api/v1"
    BLOCKCHAINS = ["ethereum", "polygon", "arbitrum", "optimism", "base",
        "bnb", "avalanche_c", "solana", "fantom", "gnosis"]

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="DuneAnalytics", requires_api_key=True)
        self.api_key = api_key or os.getenv("DUNE_API_KEY")
        self.session = SessionManager.get_session("dune")

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Set DUNE_API_KEY env var")
        try:
            r = self.session.get(f"{self.BASE_URL}/query/1/results",
                headers={"X-Dune-API-Key": self.api_key}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "Dune"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def execute_query(self, query_id: int, params: Optional[Dict[str, Any]] = None) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            body = {"params": params} if params else {}
            r = self.session.post(f"{self.BASE_URL}/query/{query_id}/execute", json=body,
                headers={"X-Dune-API-Key": self.api_key}, timeout=120)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "Dune", "query_id": query_id})
        except Exception as e:
            return handle_request_error(e, "Dune", "execute_query")

    def get_blockchains(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.BLOCKCHAINS,
            metadata={"source": "Dune", "count": len(self.BLOCKCHAINS)})
