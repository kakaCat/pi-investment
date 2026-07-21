"""Baltic Exchange maritime shipping rates data source.
Provides dry bulk, tanker, and container shipping rate indices. Requires API key.
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BalticExchangeSource(EconomicDataSource):
    """Baltic Exchange shipping rate indices data source.
    Baltic Dry Index (BDI), Capesize, Panamax, tanker indices, FFA pricing.
    Critical: global trade activity nowcasting, commodity demand proxy."""

    BASE_URL = "https://www.balticexchange.com/api/v1"
    INDICES = {"BDI": "Baltic Dry Index", "BCI": "Capesize", "BPI": "Panamax",
        "BSI": "Supramax", "BHSI": "Handysize", "BDTI": "Dirty Tanker", "BCTI": "Clean Tanker"}

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="BalticExchange", requires_api_key=True)
        self.api_key = api_key or os.getenv("BALTIC_API_KEY")
        self.session = SessionManager.get_session("baltic")

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Set BALTIC_API_KEY env var")
        try:
            r = self.session.get(f"{self.BASE_URL}/indices/BDI",
                headers={"X-API-Key": self.api_key}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "Baltic"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_index(self, index_code: str = "BDI") -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            r = self.session.get(f"{self.BASE_URL}/indices/{index_code}",
                headers={"X-API-Key": self.api_key}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "BalticExchange", "index": index_code})
        except Exception as e:
            return handle_request_error(e, "BalticExchange", "get_index")

    def get_indices(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"code": c, "description": d} for c, d in self.INDICES.items()],
            metadata={"source": "BalticExchange", "count": len(self.INDICES)})
