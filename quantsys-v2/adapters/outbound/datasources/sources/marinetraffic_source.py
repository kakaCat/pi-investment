"""MarineTraffic maritime data source.

Provides access to global vessel tracking, port data, and maritime analytics.

API Documentation: https://www.marinetraffic.com/en/ais-api-services
Requires API key.
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class MarineTrafficSource(EconomicDataSource):
    """MarineTraffic maritime data source.

    Provides access to:
    - Real-time vessel positions
    - Vessel details and history
    - Port data and calls
    - Voyage information
    - Maritime analytics
    - Fleet tracking

    Requires API key.
    """

    BASE_URL = "https://services.marinetraffic.com/api"

    # Vessel types
    VESSEL_TYPES = [
        "Cargo", "Tanker", "Passenger", "Fishing", "Tug", "Pleasure",
        "High-Speed", "Sailing", "Military", "Law Enforcement", "Medical",
        "Special Purpose", "Generic"
    ]

    def __init__(self, api_key: Optional[str] = None):
        """Initialize MarineTraffic data source.

        Args:
            api_key: MarineTraffic API key (or set MARINETRAFFIC_API_KEY env var)
        """
        super().__init__(name="MarineTraffic", requires_api_key=True)
        self.api_key = api_key or os.getenv("MARINETRAFFIC_API_KEY")
        self.session = SessionManager.get_session("marinetraffic")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("MarineTraffic API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to MarineTraffic API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set MARINETRAFFIC_API_KEY environment variable."
            )

        try:
            response = self.session.get(
                f"{self.BASE_URL}/exportvessels/v:8/",
                params={
                    "api_key": self.api_key,
                    "prot": "json"
                },
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "MarineTraffic"},
                metadata={"source": "MarineTraffic", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"MarineTraffic connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        version: str = "v:8"
    ) -> Dict[str, Any]:
        """Make request to MarineTraffic API.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            version: API version

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}/{version}/"
        request_params = {"api_key": self.api_key, "prot": "json"}
        if params:
            request_params.update(params)

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_vessel_positions(
        self,
        timespan: int = 20,
        mmsi: Optional[str] = None
    ) -> DataSourceResponse:
        """Get vessel positions.

        Args:
            timespan: Minutes of recent data (default: 20, max: 1440)
            mmsi: Specific vessel MMSI (optional)

        Returns:
            DataSourceResponse with vessel positions
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"timespan": min(timespan, 1440)}
            if mmsi:
                params["mmsi"] = mmsi

            data = self._make_request("exportvessels", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "MarineTraffic",
                    "timespan": timespan,
                    "mmsi": mmsi
                }
            )
        except Exception as e:
            return handle_request_error(e, "MarineTraffic", "get_vessel_positions")

    def get_vessel_info(self, mmsi: str) -> DataSourceResponse:
        """Get detailed vessel information.

        Args:
            mmsi: Vessel MMSI number

        Returns:
            DataSourceResponse with vessel details
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request("exportvessel", params={"mmsi": mmsi}, version="v:8")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "MarineTraffic",
                    "mmsi": mmsi
                }
            )
        except Exception as e:
            return handle_request_error(e, "MarineTraffic", "get_vessel_info")

    def get_port_calls(
        self,
        port_id: Optional[str] = None,
        port_name: Optional[str] = None,
        timespan: int = 1440
    ) -> DataSourceResponse:
        """Get port call data.

        Args:
            port_id: Port UN/LOCODE (optional)
            port_name: Port name (optional)
            timespan: Minutes of recent data (max 2880)

        Returns:
            DataSourceResponse with port call data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"timespan": min(timespan, 2880)}
            if port_id:
                params["portid"] = port_id
            if port_name:
                params["port"] = port_name

            data = self._make_request("exportportcalls", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "MarineTraffic",
                    "port_id": port_id,
                    "port_name": port_name,
                    "timespan": timespan
                }
            )
        except Exception as e:
            return handle_request_error(e, "MarineTraffic", "get_port_calls")

    def get_area_positions(
        self,
        lat_min: float,
        lon_min: float,
        lat_max: float,
        lon_max: float
    ) -> DataSourceResponse:
        """Get vessel positions within geographic bounds.

        Args:
            lat_min: Minimum latitude
            lon_min: Minimum longitude
            lat_max: Maximum latitude
            lon_max: Maximum longitude

        Returns:
            DataSourceResponse with vessels in area
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {
                "minlat": lat_min,
                "minlon": lon_min,
                "maxlat": lat_max,
                "maxlon": lon_max
            }

            data = self._make_request("exportvesselsinarea", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "MarineTraffic",
                    "bounds": {
                        "lat_min": lat_min, "lon_min": lon_min,
                        "lat_max": lat_max, "lon_max": lon_max
                    }
                }
            )
        except Exception as e:
            return handle_request_error(e, "MarineTraffic", "get_area_positions")

    def get_vessel_types(self) -> DataSourceResponse:
        """Get list of vessel types.

        Returns:
            DataSourceResponse with vessel types
        """
        return DataSourceResponse.success_response(
            data=self.VESSEL_TYPES,
            metadata={
                "source": "MarineTraffic",
                "count": len(self.VESSEL_TYPES)
            }
        )
