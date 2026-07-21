"""IRENA (International Renewable Energy Agency) data source.

Provides global renewable energy capacity, generation, and cost data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class IRENASource(EconomicDataSource):
    """IRENA (International Renewable Energy Agency) data source.

    Provides global renewable energy statistics including installed capacity
    by technology (solar, wind, hydro, bioenergy, geothermal) and country,
    generation data, investment trends, and renewable cost data.

    Essential for energy transition investment analysis, clean energy sector
    allocation, and climate policy assessment.

    No API key required.
    """

    BASE_URL = "https://api.irena.org/api"

    TECHNOLOGIES = {
        "total_renewables": "Total renewable energy",
        "solar_pv": "Solar photovoltaic",
        "concentrated_solar": "Concentrated solar power (CSP)",
        "onshore_wind": "Onshore wind",
        "offshore_wind": "Offshore wind",
        "hydro": "Hydropower",
        "bioenergy": "Bioenergy",
        "geothermal": "Geothermal",
        "marine": "Marine/ocean energy",
    }

    INDICATORS = {
        "installed_capacity": "Installed capacity (MW)",
        "generation": "Electricity generation (GWh)",
        "investment": "Annual investment (USD)",
        "lcoe": "Levelized cost of electricity ($/kWh)",
        "employment": "Renewable energy jobs",
    }

    def __init__(self):
        super().__init__(name="IRENA", requires_api_key=False)
        self.session = SessionManager.get_session("irena")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/capacity",
                params={"limit": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "IRENA"},
                metadata={"source": "IRENA", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"IRENA connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {"technology": series_id}
            if start_date:
                params["year_from"] = start_date
            if end_date:
                params["year_to"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/capacity", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "IRENA", "technology": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "IRENA", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.TECHNOLOGIES.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "IRENA", "query": query},
        )

    def get_capacity_by_tech(self, tech: str = "solar_pv") -> DataSourceResponse:
        """Get global installed capacity for a renewable technology."""
        if tech not in self.TECHNOLOGIES:
            return DataSourceResponse.error_response(
                error=f"Invalid technology: {tech}. Use get_technologies()."
            )
        return self.get_series(tech)

    def get_technologies(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.TECHNOLOGIES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "IRENA", "count": len(items)},
        )
