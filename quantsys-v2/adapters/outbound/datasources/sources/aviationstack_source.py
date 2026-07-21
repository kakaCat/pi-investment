"""AviationStack flight tracking data source.
Provides real-time flight tracking, schedules, and aviation data. Requires API key.
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class AviationStackSource(EconomicDataSource):
    """AviationStack flight data source.
    Real-time flight tracking, schedules, routes, airports, airlines.
    Economic: air travel demand proxy, tourism nowcasting, cargo monitoring."""

    BASE_URL = "https://api.aviationstack.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="AviationStack", requires_api_key=True)
        self.api_key = api_key or os.getenv("AVIATIONSTACK_API_KEY")
        self.session = SessionManager.get_session("aviationstack")

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Set AVIATIONSTACK_API_KEY env var")
        try:
            r = self.session.get(f"{self.BASE_URL}/airports",
                params={"access_key": self.api_key, "limit": 1}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "AviationStack"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_flights(self, flight_status: Optional[str] = None, dep_iata: Optional[str] = None,
        arr_iata: Optional[str] = None, limit: int = 100) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            params: Dict[str, Any] = {"access_key": self.api_key, "limit": limit}
            if flight_status: params["flight_status"] = flight_status
            if dep_iata: params["dep_iata"] = dep_iata
            if arr_iata: params["arr_iata"] = arr_iata
            r = self.session.get(f"{self.BASE_URL}/flights", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(), metadata={"source": "AviationStack"})
        except Exception as e:
            return handle_request_error(e, "AviationStack", "get_flights")

    def get_airports(self, country: Optional[str] = None, limit: int = 100) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            params: Dict[str, Any] = {"access_key": self.api_key, "limit": limit}
            if country: params["country_iso2"] = country
            r = self.session.get(f"{self.BASE_URL}/airports", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(), metadata={"source": "AviationStack"})
        except Exception as e:
            return handle_request_error(e, "AviationStack", "get_airports")
