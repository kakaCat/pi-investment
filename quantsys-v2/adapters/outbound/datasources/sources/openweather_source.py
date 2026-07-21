"""OpenWeatherMap weather data source.
Provides real-time and forecast weather data for economic analysis. Requires API key.
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class OpenWeatherSource(EconomicDataSource):
    """OpenWeatherMap weather data source.
    Current weather, 5-day forecast, air pollution, UV index, weather alerts.
    Economic: energy demand (HDD/CDD), agriculture, retail, insurance."""

    BASE_URL = "https://api.openweathermap.org"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="OpenWeather", requires_api_key=True)
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.session = SessionManager.get_session("openweather")

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Set OPENWEATHER_API_KEY env var")
        try:
            r = self.session.get(f"{self.BASE_URL}/data/2.5/weather",
                params={"q": "London", "appid": self.api_key}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "OWM"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_current_weather(self, city: Optional[str] = None,
        lat: Optional[float] = None, lon: Optional[float] = None) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            params: Dict[str, Any] = {"appid": self.api_key}
            if city: params["q"] = city
            elif lat is not None and lon is not None:
                params["lat"] = lat; params["lon"] = lon
            else:
                return DataSourceResponse.error_response(error="Provide city or lat/lon")
            r = self.session.get(f"{self.BASE_URL}/data/2.5/weather", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(), metadata={"source": "OWM"})
        except Exception as e:
            return handle_request_error(e, "OpenWeather", "get_current_weather")

    def get_air_pollution(self, lat: float, lon: float) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            r = self.session.get(f"{self.BASE_URL}/data/2.5/air_pollution",
                params={"lat": lat, "lon": lon, "appid": self.api_key}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(), metadata={"source": "OWM", "type": "air"})
        except Exception as e:
            return handle_request_error(e, "OpenWeather", "get_air_pollution")
