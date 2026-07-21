"""USDA agricultural data source.
Provides agricultural production, supply/demand, and trade forecasts. No API key required.
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class USDAAgriculturalSource(EconomicDataSource):
    """USDA agricultural data source.
    WASDE report, crop production, grain stocks, export sales, livestock statistics."""

    BASE_URL = "https://quickstats.nass.usda.gov/api"
    FAS_URL = "https://apps.fas.usda.gov/psdonline/api"
    COMMODITY_GROUPS = ["corn", "soybeans", "wheat", "cotton", "rice", "sorghum",
        "oats", "barley", "cattle", "hogs", "poultry", "dairy"]

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="USDA", requires_api_key=True)
        self.api_key = api_key or os.getenv("USDA_NASS_API_KEY")
        self.session = SessionManager.get_session("usda")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.FAS_URL}/commodities", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "USDA"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_wasde_report(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.FAS_URL}/wasde", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "USDA_WASDE"})
        except Exception as e:
            return handle_request_error(e, "USDA", "get_wasde_report")

    def get_crop_production(self, commodity: str = "corn", year: Optional[int] = None) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {"commodity_desc": commodity.upper(), "statisticcat_desc": "PRODUCTION"}
            if year: params["year"] = year
            r = self.session.get(f"{self.BASE_URL}/api_GET", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "USDA_NASS", "commodity": commodity})
        except Exception as e:
            return handle_request_error(e, "USDA", "get_crop_production")

    def get_commodity_groups(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.COMMODITY_GROUPS,
            metadata={"source": "USDA", "count": len(self.COMMODITY_GROUPS)})
