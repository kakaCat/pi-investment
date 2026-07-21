"""BP Statistical Review of World Energy data source.
Provides comprehensive global energy statistics. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BPStatisticalReviewSource(EconomicDataSource):
    """BP Statistical Review of World Energy data source.
    Primary energy, oil, gas, coal, renewables, CO2 emissions by country.
    Now published by Energy Institute. Most comprehensive energy dataset."""

    BASE_URL = "https://www.energyinst.org/statistical-review"
    ENERGY_SOURCES = ["oil", "natural_gas", "coal", "nuclear", "hydroelectric",
        "renewables", "solar", "wind", "biofuels", "geothermal"]

    def __init__(self):
        super().__init__(name="BPStatisticalReview", requires_api_key=False)
        self.session = SessionManager.get_session("bp_energy")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/resources/data", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "BP_Energy"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_global_energy_data(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/resources/data", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"url": str(r.url)},
                metadata={"source": "EnergyInstitute", "dataset": "statistical_review"})
        except Exception as e:
            return handle_request_error(e, "BP_Energy", "get_global_energy_data")

    def get_energy_sources(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.ENERGY_SOURCES,
            metadata={"source": "BP_Energy", "count": len(self.ENERGY_SOURCES)})
