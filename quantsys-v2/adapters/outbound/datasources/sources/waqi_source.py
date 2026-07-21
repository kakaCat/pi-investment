"""WAQI (World Air Quality Index) data source.

Provides access to real-time air quality data from monitoring stations worldwide.

API Documentation: https://aqicn.org/api/
Requires API key: https://aqicn.org/data-platform/token/
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class WAQISource(EconomicDataSource):
    """World Air Quality Index data source.

    Provides access to:
    - Real-time air quality data
    - AQI (Air Quality Index) values
    - Pollutant measurements (PM2.5, PM10, O3, NO2, SO2, CO)
    - Station information
    - Geographic search

    Requires API key.
    """

    BASE_URL = "https://api.waqi.info"

    # AQI levels
    AQI_LEVELS = {
        "good": (0, 50),
        "moderate": (51, 100),
        "unhealthy_sensitive": (101, 150),
        "unhealthy": (151, 200),
        "very_unhealthy": (201, 300),
        "hazardous": (301, 500)
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize WAQI data source.

        Args:
            api_key: WAQI API key (or set WAQI_API_KEY env var)
        """
        super().__init__(name="WAQI", requires_api_key=True)
        self.api_key = api_key or os.getenv("WAQI_API_KEY")
        self.session = SessionManager.get_session("waqi")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("WAQI API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to WAQI API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set WAQI_API_KEY environment variable."
            )

        try:
            # Test with Beijing station
            response = self.session.get(
                f"{self.BASE_URL}/feed/beijing/",
                params={"token": self.api_key},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                return DataSourceResponse.success_response(
                    data={"status": "connected", "api": "WAQI"},
                    metadata={"source": "WAQI", "base_url": self.BASE_URL}
                )
            else:
                return DataSourceResponse.error_response(
                    error=f"API returned status: {data.get('status')}"
                )
        except Exception as e:
            logger.error(f"WAQI connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to WAQI API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        request_params = {"token": self.api_key}
        if params:
            request_params.update(params)

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_city_feed(self, city: str) -> DataSourceResponse:
        """Get air quality data for a city.

        Args:
            city: City name (e.g., 'beijing', 'london', 'new york')

        Returns:
            DataSourceResponse with air quality data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured"
            )

        try:
            data = self._make_request(f"feed/{city}/")

            if data.get("status") == "ok":
                return DataSourceResponse.success_response(
                    data=data.get("data", {}),
                    metadata={
                        "source": "WAQI",
                        "city": city
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error=f"API returned status: {data.get('status')}"
                )
        except Exception as e:
            return handle_request_error(e, "WAQI", "get_city_feed")

    def get_station_feed(self, station_id: int) -> DataSourceResponse:
        """Get air quality data for a specific station.

        Args:
            station_id: Station ID number

        Returns:
            DataSourceResponse with air quality data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured"
            )

        try:
            data = self._make_request(f"feed/@{station_id}/")

            if data.get("status") == "ok":
                return DataSourceResponse.success_response(
                    data=data.get("data", {}),
                    metadata={
                        "source": "WAQI",
                        "station_id": station_id
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error=f"API returned status: {data.get('status')}"
                )
        except Exception as e:
            return handle_request_error(e, "WAQI", "get_station_feed")

    def get_geo_feed(self, lat: float, lon: float) -> DataSourceResponse:
        """Get air quality data for geographic coordinates.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            DataSourceResponse with air quality data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured"
            )

        try:
            data = self._make_request(f"feed/geo:{lat};{lon}/")

            if data.get("status") == "ok":
                return DataSourceResponse.success_response(
                    data=data.get("data", {}),
                    metadata={
                        "source": "WAQI",
                        "lat": lat,
                        "lon": lon
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error=f"API returned status: {data.get('status')}"
                )
        except Exception as e:
            return handle_request_error(e, "WAQI", "get_geo_feed")

    def search_stations(self, keyword: str) -> DataSourceResponse:
        """Search for monitoring stations by keyword.

        Args:
            keyword: Search keyword (city name, station name, etc.)

        Returns:
            DataSourceResponse with search results
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured"
            )

        try:
            data = self._make_request(f"search/", params={"keyword": keyword})

            if data.get("status") == "ok":
                return DataSourceResponse.success_response(
                    data=data.get("data", []),
                    metadata={
                        "source": "WAQI",
                        "keyword": keyword,
                        "count": len(data.get("data", []))
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error=f"API returned status: {data.get('status')}"
                )
        except Exception as e:
            return handle_request_error(e, "WAQI", "search_stations")

    def get_map_bounds(
        self,
        lat_min: float,
        lon_min: float,
        lat_max: float,
        lon_max: float
    ) -> DataSourceResponse:
        """Get all stations within geographic bounds.

        Args:
            lat_min: Minimum latitude
            lon_min: Minimum longitude
            lat_max: Maximum latitude
            lon_max: Maximum longitude

        Returns:
            DataSourceResponse with stations in bounds
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured"
            )

        try:
            data = self._make_request(
                f"map/bounds/",
                params={
                    "latlng": f"{lat_min},{lon_min},{lat_max},{lon_max}"
                }
            )

            if data.get("status") == "ok":
                return DataSourceResponse.success_response(
                    data=data.get("data", []),
                    metadata={
                        "source": "WAQI",
                        "bounds": {
                            "lat_min": lat_min,
                            "lon_min": lon_min,
                            "lat_max": lat_max,
                            "lon_max": lon_max
                        },
                        "count": len(data.get("data", []))
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error=f"API returned status: {data.get('status')}"
                )
        except Exception as e:
            return handle_request_error(e, "WAQI", "get_map_bounds")

    @staticmethod
    def interpret_aqi(aqi: int) -> str:
        """Interpret AQI value into health category.

        Args:
            aqi: AQI value

        Returns:
            Health category string
        """
        if aqi <= 50:
            return "Good"
        elif aqi <= 100:
            return "Moderate"
        elif aqi <= 150:
            return "Unhealthy for Sensitive Groups"
        elif aqi <= 200:
            return "Unhealthy"
        elif aqi <= 300:
            return "Very Unhealthy"
        else:
            return "Hazardous"
