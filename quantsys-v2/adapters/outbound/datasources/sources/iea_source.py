"""International Energy Agency (IEA) global energy data source.
Provides global energy statistics, outlooks, and policy data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class InternationalEnergyAgencySource(EconomicDataSource):
    """IEA global energy statistics and outlook data source.
    World Energy Outlook, oil market report, clean energy investment, energy balances."""

    DATA_URL = "https://www.iea.org/api"
    ENERGY_SOURCES = ["oil", "natural_gas", "coal", "nuclear", "hydro", "wind",
        "solar_pv", "bioenergy", "geothermal", "hydrogen"]
    WEO_SCENARIOS = ["STEPS", "APS", "NZE"]

    def __init__(self):
        super().__init__(name="InternationalEnergyAgency", requires_api_key=False)
        self.session = SessionManager.get_session("iea")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.DATA_URL}/statistics", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "IEA"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_energy_statistics(self, country: Optional[str] = None, year: Optional[int] = None) -> DataSourceResponse:
        try:
            params = {}
            if country: params["country"] = country
            if year: params["year"] = year
            r = self.session.get(f"{self.DATA_URL}/statistics", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "IEA", "country": country, "year": year})
        except Exception as e:
            return handle_request_error(e, "IEA", "get_energy_statistics")

    def get_oil_market_report(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.DATA_URL}/omr", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "IEA", "dataset": "oil_market_report"})
        except Exception as e:
            return handle_request_error(e, "IEA", "get_oil_market_report")

    def get_energy_sources(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.ENERGY_SOURCES,
            metadata={"source": "IEA", "count": len(self.ENERGY_SOURCES)})

    def get_weo_scenarios(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.WEO_SCENARIOS,
            metadata={"source": "IEA", "count": len(self.WEO_SCENARIOS)})
