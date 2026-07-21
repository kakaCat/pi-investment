"""UN Population Division demographic data source.
Provides global population projections, fertility, mortality, and migration data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class UNPopulationSource(EconomicDataSource):
    """UN Population Division demographic data source.
    Population projections, fertility, life expectancy, migration, urbanization.
    Economic: long-term GDP modeling, labor force, pensions, consumer markets."""

    BASE_URL = "https://population.un.org/dataportal/api/v1"
    INDICATORS = {"pop_total": "Total population", "fertility": "Total fertility rate",
        "life_expectancy": "Life expectancy", "median_age": "Median age",
        "dependency_ratio": "Age dependency ratio", "urban_population": "Urban %",
        "pop_growth": "Population growth rate"}
    SCENARIOS = ["medium", "high", "low", "constant_fertility", "instant_replacement"]

    def __init__(self):
        super().__init__(name="UNPopulation", requires_api_key=False)
        self.session = SessionManager.get_session("un_population")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/data/indicators", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "UNPopulation"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_population(self, country: str = "900", year: Optional[int] = None) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {"locationCode": country}
            if year: params["year"] = year
            r = self.session.get(f"{self.BASE_URL}/data/population", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "UNPopulation", "country": country})
        except Exception as e:
            return handle_request_error(e, "UNPopulation", "get_population")

    def get_indicators(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"code": c, "description": d} for c, d in self.INDICATORS.items()],
            metadata={"source": "UNPopulation", "count": len(self.INDICATORS)})

    def get_scenarios(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.SCENARIOS,
            metadata={"source": "UNPopulation", "count": len(self.SCENARIOS)})
