"""OpenTable restaurant booking data source.
Provides restaurant reservation trends as a consumer spending proxy. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class OpenTableSource(EconomicDataSource):
    """OpenTable restaurant booking data source.
    Seated diners YoY change, reservation trends by city/state.
    Economic: real-time consumer spending nowcasting, service sector health."""

    STATE_CODES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
        "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
        "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]

    def __init__(self):
        super().__init__(name="OpenTable", requires_api_key=False)
        self.session = SessionManager.get_session("opentable")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get("https://www.opentable.com/state-of-industry", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "OpenTable"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_seated_diners(self, country: str = "US") -> DataSourceResponse:
        try:
            r = self.session.get("https://www.opentable.com/state-of-industry",
                params={"country": country}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"indicator": "seated_diners_yoy"},
                metadata={"source": "OpenTable", "country": country})
        except Exception as e:
            return handle_request_error(e, "OpenTable", "get_seated_diners")

    def get_state_codes(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.STATE_CODES,
            metadata={"source": "OpenTable", "count": len(self.STATE_CODES)})
