"""N2YO satellite tracking and space data source.

Provides real-time satellite position data, pass predictions, and orbital information.

API Documentation: https://www.n2yo.com/api/
Requires API key (free tier: 1000 requests/hour).
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class N2YOSource(EconomicDataSource):
    """N2YO satellite tracking data source.

    Provides access to:
    - Real-time satellite positions (latitude, longitude, altitude)
    - Satellite pass predictions (visible and radio)
    - Two-Line Element (TLE) data
    - Satellite catalog and search
    - ISS and major constellation tracking

    Economic relevance: satellite broadband coverage, Starlink availability,
    GPS/GNSS constellation health, earth observation revisit rates.
    Requires API key (free tier available).
    """

    BASE_URL = "https://api.n2yo.com/rest/v1/satellite"

    SATELLITE_CATEGORIES = {
        "ISS": 25544,
        "GPS_IIR-1": 24876,
        "STARLINK_LEADER": 44235,
        "ONEWEB_LEADER": 44057,
        "PLANET_SCOPE": 40715,
        "SENTINEL_1A": 39634,
        "SENTINEL_2A": 40697,
        "LANDSAT_9": 49260,
        "GOES_16": 41866,
        "HIMAWARI_9": 41836,
    }

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="N2YO", requires_api_key=True)
        self.api_key = api_key or os.getenv("N2YO_API_KEY")
        self.session = SessionManager.get_session("n2yo")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.error("N2YO API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set N2YO_API_KEY environment variable."
            )
        try:
            response = self.session.get(
                f"{self.BASE_URL}/tle/25544",
                params={"apiKey": self.api_key},
                timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "N2YO"},
                metadata={"source": "N2YO", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"N2YO connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        params["apiKey"] = self.api_key
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_tle(self, norad_id: int = 25544) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            data = self._make_request(f"tle/{norad_id}", {})
            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "N2YO", "norad_id": norad_id}
            )
        except Exception as e:
            return handle_request_error(e, "N2YO", "get_tle")

    def get_positions(
        self,
        norad_id: int = 25544,
        observer_lat: float = 40.7128,
        observer_lng: float = -74.0060,
        observer_alt: float = 0,
        seconds: int = 2
    ) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            data = self._make_request(
                f"positions/{norad_id}/{observer_lat}/{observer_lng}/{observer_alt}/{seconds}",
                {}
            )
            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "N2YO",
                    "norad_id": norad_id,
                    "observer": {"lat": observer_lat, "lng": observer_lng}
                }
            )
        except Exception as e:
            return handle_request_error(e, "N2YO", "get_positions")

    def get_visual_passes(
        self,
        norad_id: int = 25544,
        observer_lat: float = 40.7128,
        observer_lng: float = -74.0060,
        observer_alt: float = 0,
        days: int = 7,
        min_visibility: int = 300
    ) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            data = self._make_request(
                f"visualpasses/{norad_id}/{observer_lat}/{observer_lng}/{observer_alt}/{days}/{min_visibility}",
                {}
            )
            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "N2YO", "norad_id": norad_id, "days": days}
            )
        except Exception as e:
            return handle_request_error(e, "N2YO", "get_visual_passes")

    def get_radio_passes(
        self,
        norad_id: int = 25544,
        observer_lat: float = 40.7128,
        observer_lng: float = -74.0060,
        observer_alt: float = 0,
        days: int = 7,
        min_elevation: int = 10
    ) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            data = self._make_request(
                f"radiopasses/{norad_id}/{observer_lat}/{observer_lng}/{observer_alt}/{days}/{min_elevation}",
                {}
            )
            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "N2YO", "norad_id": norad_id, "days": days}
            )
        except Exception as e:
            return handle_request_error(e, "N2YO", "get_radio_passes")

    def get_satellite_categories(self) -> DataSourceResponse:
        cats = [
            {"name": name, "norad_id": norad_id}
            for name, norad_id in self.SATELLITE_CATEGORIES.items()
        ]
        return DataSourceResponse.success_response(
            data=cats,
            metadata={"source": "N2YO", "count": len(cats)}
        )
