"""DeBank DeFi analytics and protocol data source.
Provides DeFi total value locked, protocol metrics, and wallet analytics. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class DeBankSource(EconomicDataSource):
    """DeBank DeFi protocol analytics data source.
    TVL by chain/protocol, wallet tracking, gas fees, bridge metrics.
    Economic: DeFi sector growth, blockchain adoption, crypto liquidity."""

    OPEN_URL = "https://openapi.debank.com/v1"
    CHAINS = ["eth", "bsc", "polygon", "arbitrum", "optimism",
        "avax", "fantom", "solana", "tron", "aptos", "sui", "base"]

    def __init__(self):
        super().__init__(name="DeBank", requires_api_key=False)
        self.session = SessionManager.get_session("debank")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.OPEN_URL}/protocol/list", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "DeBank"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_tvl(self, chain: Optional[str] = None) -> DataSourceResponse:
        try:
            params = {}
            if chain: params["chain"] = chain
            r = self.session.get(f"{self.OPEN_URL}/protocol/list", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "DeBank", "indicator": "TVL"})
        except Exception as e:
            return handle_request_error(e, "DeBank", "get_tvl")

    def get_gas_tracker(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.OPEN_URL}/gas/current", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "DeBank", "indicator": "gas_fees"})
        except Exception as e:
            return handle_request_error(e, "DeBank", "get_gas_tracker")

    def get_chains(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.CHAINS,
            metadata={"source": "DeBank", "count": len(self.CHAINS)})
