"""NGFS climate scenario and transition risk data source.
Provides central bank climate stress test scenarios and transition pathways. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class NGFSClimateSource(EconomicDataSource):
    """NGFS climate scenario data source.
    Net Zero 2050, Delayed Transition, carbon prices, energy mix, GDP impact.
    Used by 100+ central banks for climate stress testing. No API key required."""

    BASE_URL = "https://data.ene.iiasa.ac.at/ngfs"
    SCENARIOS = {"net_zero_2050": "Net Zero 2050", "below_2c": "Below 2°C",
        "delayed_transition": "Delayed transition", "current_policies": "Current policies",
        "ndcs": "NDCs", "fragmented_world": "Fragmented world"}
    KEY_VARIABLES = ["carbon_price", "primary_energy", "emissions", "gdp_impact",
        "renewable_share", "electricity_generation", "coal_demand", "oil_demand"]

    def __init__(self):
        super().__init__(name="NGFSClimate", requires_api_key=False)
        self.session = SessionManager.get_session("ngfs")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/scenarios", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "NGFS"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_scenarios(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "description": d} for n, d in self.SCENARIOS.items()],
            metadata={"source": "NGFS", "count": len(self.SCENARIOS)})

    def get_carbon_prices(self, scenario: str = "net_zero_2050", region: str = "World") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/carbon-price",
                params={"scenario": scenario, "region": region}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "NGFS", "scenario": scenario, "region": region})
        except Exception as e:
            return handle_request_error(e, "NGFS", "get_carbon_prices")

    def get_gdp_impact(self, scenario: str = "current_policies", region: str = "World") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/macroeconomic-impact",
                params={"scenario": scenario, "region": region}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "NGFS", "scenario": scenario})
        except Exception as e:
            return handle_request_error(e, "NGFS", "get_gdp_impact")

    def get_variables(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.KEY_VARIABLES,
            metadata={"source": "NGFS", "count": len(self.KEY_VARIABLES)})
