"""OSCAR (Observing Systems Capability Analysis and Review) WMO data source.

Provides access to global meteorological and earth observation station metadata.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class OSCARSource(EconomicDataSource):
    """WMO OSCAR meteorological observing systems data source.

    Provides access to global weather station inventory (surface, upper-air,
    marine), satellite instrument metadata, WIGOS station identifiers, and
    observing system requirements.

    Economic relevance: weather forecast network density assessment,
    insurance/risk modeling, aviation/marine route planning,
    climate monitoring infrastructure analysis, agricultural data availability.
    No API key required.
    """

    BASE_URL = "https://oscar.wmo.int"
    API_URL = "https://oscar.wmo.int/surface/rest/api"

    STATION_TYPES = [
        "land_surface", "land_upper_air", "marine_platform",
        "aircraft", "radiation", "lightning", "weather_radar",
        "atmospheric_comp",
    ]

    def __init__(self):
        super().__init__(name="OSCAR", requires_api_key=False)
        self.session = SessionManager.get_session("oscar")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.API_URL}/stations", params={"limit": 1}, timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "OSCAR_WMO"},
                metadata={"source": "OSCAR", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"OSCAR connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_stations(
        self,
        station_type: Optional[str] = None,
        country: Optional[str] = None,
        limit: int = 100,
    ) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {"limit": limit}
            if station_type:
                if station_type not in self.STATION_TYPES:
                    return DataSourceResponse.error_response(
                        error=f"Invalid type: {station_type}. Use get_station_types()."
                    )
                params["type"] = station_type
            if country:
                params["country"] = country
            response = self.session.get(
                f"{self.API_URL}/stations", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={
                    "source": "OSCAR_WMO", "station_type": station_type,
                    "country": country, "limit": limit,
                },
            )
        except Exception as e:
            return handle_request_error(e, "OSCAR", "get_stations")

    def get_station_detail(self, wigos_id: str) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.API_URL}/stations/{wigos_id}", timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "OSCAR_WMO", "wigos_id": wigos_id},
            )
        except Exception as e:
            return handle_request_error(e, "OSCAR", "get_station_detail")

    def get_station_types(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=self.STATION_TYPES,
            metadata={"source": "OSCAR", "count": len(self.STATION_TYPES)},
        )

    def get_network_coverage(
        self, country: str, station_type: Optional[str] = None
    ) -> DataSourceResponse:
        try:
            params = {"country": country}
            if station_type:
                params["type"] = station_type
            response = self.session.get(
                f"{self.API_URL}/stations/count", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={
                    "source": "OSCAR_WMO", "country": country,
                    "station_type": station_type, "indicator": "network_density",
                },
            )
        except Exception as e:
            return handle_request_error(e, "OSCAR", "get_network_coverage")

    def get_observing_requirements(
        self, application_area: Optional[str] = None
    ) -> DataSourceResponse:
        try:
            params = {}
            if application_area:
                params["application"] = application_area
            response = self.session.get(
                f"{self.API_URL}/requirements", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "OSCAR_WMO", "application_area": application_area},
            )
        except Exception as e:
            return handle_request_error(e, "OSCAR", "get_observing_requirements")
