"""Statistics Canada national statistical data source.
Provides Canadian economic, social, and demographic data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class StatisticsCanadaSource(EconomicDataSource):
    """Statistics Canada (StatCan) data source.
    GDP, CPI, labour force, merchandise trade, retail, housing starts, population."""

    BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"
    KEY_VECTORS = {"gdp_monthly": "v65201210", "cpi_all_items": "v41690973",
        "unemployment": "v2062815", "employment": "v2062811", "retail_trade": "v52366955",
        "housing_starts": "v107744", "trade_balance": "v6475252"}

    def __init__(self):
        super().__init__(name="StatisticsCanada", requires_api_key=False)
        self.session = SessionManager.get_session("statcan")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/getFullTableDownloadCSV/3610043401-en", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "StatCan"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_vector(self, vector_id: str) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/getDataFromVectorByReferencePeriodRange",
                params={"vectorIds": vector_id}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "StatCan", "vector_id": vector_id})
        except Exception as e:
            return handle_request_error(e, "StatCan", "get_vector")

    def get_cpi(self) -> DataSourceResponse:
        return self.get_vector("v41690973")

    def get_gdp(self) -> DataSourceResponse:
        return self.get_vector("v65201210")

    def get_key_vectors(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "vector": v} for n, v in self.KEY_VECTORS.items()],
            metadata={"source": "StatCan", "count": len(self.KEY_VECTORS)})
