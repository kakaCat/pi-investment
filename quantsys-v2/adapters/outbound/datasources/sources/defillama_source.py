"""DefiLlama DeFi total value locked and protocol data source.
Provides cross-chain DeFi TVL, protocol rankings, and yield data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class DefiLlamaSource(EconomicDataSource):
    """DefiLlama DeFi analytics data source.
    TVL across 200+ chains, protocol rankings, yields, stablecoins, hacks database."""

    BASE_URL = "https://api.llama.fi"

    def __init__(self):
        super().__init__(name="DefiLlama", requires_api_key=False)
        self.session = SessionManager.get_session("defillama")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/tvl/ethereum", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "DefiLlama"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_global_tvl(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/charts", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "DefiLlama", "indicator": "global_tvl"})
        except Exception as e:
            return handle_request_error(e, "DefiLlama", "get_global_tvl")

    def get_chain_tvl(self, chain: str = "ethereum") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/tvl/{chain}", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "DefiLlama", "chain": chain})
        except Exception as e:
            return handle_request_error(e, "DefiLlama", "get_chain_tvl")

    def get_protocols(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/protocols", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "DefiLlama", "type": "protocols"})
        except Exception as e:
            return handle_request_error(e, "DefiLlama", "get_protocols")

    def get_stablecoins(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/stablecoins", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "DefiLlama", "type": "stablecoins"})
        except Exception as e:
            return handle_request_error(e, "DefiLlama", "get_stablecoins")
