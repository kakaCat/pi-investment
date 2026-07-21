"""AISStream vessel tracking data source.

Provides real-time and historical maritime vessel position data via AIS
(Automatic Identification System). No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class AISStreamSource(EconomicDataSource):
    """AISStream maritime vessel tracking data source.

    Provides AIS vessel position data (MMSI, lat, lon, speed, heading, draught,
    destination), vessel metadata (name, type, flag, IMO), and port call
    analytics. Covers 200K+ vessels globally.

    Investment applications:
    - Oil tanker tracking → crude oil supply/demand inference
    - Container ship tracking → trade volume proxy
    - LNG carrier tracking → natural gas market intelligence
    - Dry bulk tracking → commodity trade monitoring

    No API key required. Uses public AIS data streams.
    """

    BASE_URL = "https://aisstream.io/api/v1"

    VESSEL_TYPES = {
        "tanker": "Oil/chemical tanker",
        "cargo": "Cargo vessel",
        "container": "Container ship",
        "lng": "LNG tanker",
        "bulk": "Bulk carrier",
        "passenger": "Passenger vessel",
        "fishing": "Fishing vessel",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="AISStream", requires_api_key=False)
        self.api_key = api_key or os.getenv("AISSTREAM_API_KEY", "")
        self.session = SessionManager.get_session("aisstream")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/status", timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "AISStream"},
                metadata={"source": "AISStream", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"AISStream connection test failed: {e}")
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
            params: Dict[str, Any] = {"mmsi": series_id}
            if start_date:
                params["from"] = start_date
            if end_date:
                params["to"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/vessel/track", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "AISStream", "mmsi": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "AISStream", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/vessel/search",
                params={"q": query, "limit": limit},
                timeout=15,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "AISStream", "query": query},
            )
        except Exception as e:
            return handle_request_error(e, "AISStream", "search_series")

    def get_vessels_by_type(
        self, vessel_type: str = "tanker", limit: int = 50
    ) -> DataSourceResponse:
        """Get vessels currently at sea by type.

        Args:
            vessel_type: One of tanker, cargo, container, lng, bulk, passenger, fishing
            limit: Maximum number of vessels to return
        """
        try:
            if vessel_type not in self.VESSEL_TYPES:
                return DataSourceResponse.error_response(
                    error=f"Unknown vessel type: {vessel_type}. Use get_vessel_types()."
                )
            response = self.session.get(
                f"{self.BASE_URL}/vessels",
                params={"type": vessel_type, "limit": limit},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "AISStream", "vessel_type": vessel_type},
            )
        except Exception as e:
            return handle_request_error(e, "AISStream", "get_vessels_by_type")

    def get_vessel_types(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.VESSEL_TYPES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "AISStream", "count": len(items)},
        )
