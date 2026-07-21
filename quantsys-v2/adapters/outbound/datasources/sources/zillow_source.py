"""Zillow real estate market data source.
Provides U.S. housing market trends, home values, and rental data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class ZillowRealEstateSource(EconomicDataSource):
    """Zillow real estate market data source.
    ZHVI home values, ZORI rent index, inventory, days on market, affordability.
    Economic: housing cycle, wealth effect, mortgage market analysis."""

    BASE_URL = "https://files.zillowstatic.com/research/public_csvs"
    METRICS = ["zhvi", "zori", "inventory", "pending", "days_on_market", "price_cut", "sale_to_list"]
    GEO_LEVELS = ["national", "state", "metro", "county", "zip"]

    def __init__(self):
        super().__init__(name="ZillowRealEstate", requires_api_key=False)
        self.session = SessionManager.get_session("zillow")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/zhvi", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "Zillow"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_home_value_index(self, region_type: str = "metro") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/zhvi/{region_type}", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"url": str(r.url), "indicator": "ZHVI"},
                metadata={"source": "Zillow", "region_type": region_type})
        except Exception as e:
            return handle_request_error(e, "Zillow", "get_home_value_index")

    def get_rent_index(self, region_type: str = "metro") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/zori/{region_type}", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"url": str(r.url), "indicator": "ZORI"},
                metadata={"source": "Zillow", "region_type": region_type})
        except Exception as e:
            return handle_request_error(e, "Zillow", "get_rent_index")

    def get_metrics(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.METRICS,
            metadata={"source": "Zillow", "count": len(self.METRICS)})
