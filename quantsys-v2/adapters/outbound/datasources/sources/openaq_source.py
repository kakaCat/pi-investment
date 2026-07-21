"""OpenAQ global air quality data source.
Provides real-time and historical air quality measurements. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class OpenAQSource(EconomicDataSource):
    """OpenAQ global air quality data source.
    PM2.5, PM10, O3, NO2, SO2, CO measurements from 150+ countries.
    Economic: pollution impact on health costs, industrial activity proxy."""

    BASE_URL = "https://api.openaq.org/v3"
    POLLUTANTS = {"pm25": "PM2.5", "pm10": "PM10", "o3": "Ozone",
        "no2": "Nitrogen dioxide", "so2": "Sulfur dioxide", "co": "Carbon monoxide"}

    def __init__(self):
        super().__init__(name="OpenAQ", requires_api_key=False)
        self.session = SessionManager.get_session("openaq")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/locations", params={"limit": 1}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "OpenAQ"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_latest(self, country: Optional[str] = None, parameter: str = "pm25",
        limit: int = 100) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {"parameter": parameter, "limit": limit}
            if country: params["country"] = country
            r = self.session.get(f"{self.BASE_URL}/locations", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "OpenAQ", "country": country})
        except Exception as e:
            return handle_request_error(e, "OpenAQ", "get_latest")

    def get_pollutants(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"code": c, "description": d} for c, d in self.POLLUTANTS.items()],
            metadata={"source": "OpenAQ", "count": len(self.POLLUTANTS)})
