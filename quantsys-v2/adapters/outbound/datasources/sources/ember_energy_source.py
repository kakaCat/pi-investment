"""Ember global energy data source.

Provides open data on global electricity generation, capacity, emissions,
and the clean energy transition. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EmberEnergySource(EconomicDataSource):
    """Ember global energy and electricity data source.

    Provides country-level electricity generation by fuel type (coal, gas,
    nuclear, hydro, solar, wind, bioenergy), installed capacity, carbon
    intensity of electricity, and clean energy transition metrics.

    Ember's Global Electricity Review and European Electricity Review are
    widely cited by energy analysts, policymakers, and investors.

    No API key required. Open data. https://ember-energy.org
    """

    BASE_URL = "https://api.ember-energy.org/v1"

    FUEL_TYPES = [
        "coal", "gas", "nuclear", "hydro", "solar",
        "wind", "bioenergy", "other_renewables", "other_fossil",
    ]

    def __init__(self):
        super().__init__(name="EmberEnergy", requires_api_key=False)
        self.session = SessionManager.get_session("ember")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/generation", params={"limit": 1}, timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Ember"},
                metadata={"source": "Ember", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Ember connection test failed: {e}")
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
            params: Dict[str, Any] = {"country": series_id}
            if start_date:
                params["year_from"] = int(start_date[:4]) if len(start_date) >= 4 else 2015
            if end_date:
                params["year_to"] = int(end_date[:4]) if len(end_date) >= 4 else 2025

            response = self.session.get(
                f"{self.BASE_URL}/generation", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Ember", "country": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "EmberEnergy", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        return self.get_series(query)

    def get_generation_mix(self, country: str = "global") -> DataSourceResponse:
        """Get electricity generation mix by fuel type for a country.

        Args:
            country: Country code or 'global' for world total
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/generation",
                params={"country": country, "year_from": 2020},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Ember", "country": country},
            )
        except Exception as e:
            return handle_request_error(e, "EmberEnergy", "get_generation_mix")

    def get_carbon_intensity(self, country: str = "global") -> DataSourceResponse:
        """Get carbon intensity of electricity generation (gCO2/kWh)."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/carbon-intensity",
                params={"country": country},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Ember", "country": country, "metric": "carbon_intensity"},
            )
        except Exception as e:
            return handle_request_error(e, "EmberEnergy", "get_carbon_intensity")

    def get_fuel_types(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=self.FUEL_TYPES,
            metadata={"source": "Ember", "count": len(self.FUEL_TYPES)},
        )
