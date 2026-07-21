"""Apple Mobility Trends data source.
Provides mobility and transit usage data from Apple Maps. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class AppleMobilitySource(EconomicDataSource):
    """Apple Mobility Trends data source.
    Driving, walking, transit usage vs baseline.
    Economic: real-time activity proxy, transport demand, retail footfall."""

    BASE_URL = "https://covid19-static.cdn-apple.com/covid19-mobility-data/current"
    TRANSPORT_TYPES = ["driving", "walking", "transit"]

    def __init__(self):
        super().__init__(name="AppleMobility", requires_api_key=False)
        self.session = SessionManager.get_session("apple_mobility")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/v5/en-us/applemobilitytrends.csv", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "Apple"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_mobility_data(self, country: Optional[str] = None, transport_type: Optional[str] = None) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/v5/en-us/applemobilitytrends.csv", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"csv_data": r.text[:3000]},
                metadata={"source": "AppleMobility"})
        except Exception as e:
            return handle_request_error(e, "AppleMobility", "get_mobility_data")

    def get_transport_types(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.TRANSPORT_TYPES,
            metadata={"source": "Apple", "count": len(self.TRANSPORT_TYPES)})
