"""ENTSO-E (European Network of Transmission System Operators for Electricity) data source.

Provides access to European electricity market data.

API Documentation: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
Requires API key (free registration).
"""

from typing import Optional, Dict, Any, List
import logging
import os
from datetime import datetime

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class ENTSOESource(EconomicDataSource):
    """ENTSO-E European electricity data source.

    Provides access to:
    - Electricity generation by source
    - Load (consumption) data
    - Cross-border flows
    - Day-ahead prices
    - Installed capacity
    - Outages
    - Balancing data

    Requires API key (free registration).
    """

    BASE_URL = "https://web-api.tp.entsoe.eu/api"

    # Document types
    DOC_TYPES = {
        "A65": "System total load",
        "A75": "Actual generation per type",
        "A44": "Price Document",
        "A11": "Installed generation capacity per type",
        "A68": "Installed generation capacity aggregated",
        "A69": "Wind and solar forecast",
        "A71": "Generation forecast",
        "A72": "Reservoir filling information",
        "A73": "Actual generation",
        "A74": "Wind and solar generation"
    }

    # Process types
    PROCESS_TYPES = {
        "A16": "Realised",
        "A18": "Intraday Total",
        "A31": "Day ahead",
        "A33": "Week ahead",
        "A40": "Year ahead"
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize ENTSO-E data source.

        Args:
            api_key: ENTSO-E API key (or set ENTSOE_API_KEY env var)
        """
        super().__init__(name="ENTSOE", requires_api_key=True)
        self.api_key = api_key or os.getenv("ENTSOE_API_KEY")
        self.session = SessionManager.get_session("entsoe")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("ENTSO-E API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to ENTSO-E API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set ENTSOE_API_KEY environment variable."
            )

        try:
            # Test with a simple query (document types)
            response = self.session.get(
                self.BASE_URL,
                params={
                    "securityToken": self.api_key,
                    "documentType": "A65",
                    "processType": "A16",
                    "outBiddingZone_Domain": "10YCZ-CEPS-----N",  # Czech Republic
                    "periodStart": "202401010000",
                    "periodEnd": "202401020000"
                },
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "ENTSOE"},
                metadata={"source": "ENTSOE", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"ENTSO-E connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, params: Dict[str, Any]) -> str:
        """Make request to ENTSO-E API.

        Args:
            params: Query parameters

        Returns:
            XML response text

        Raises:
            Exception: If request fails
        """
        request_params = {"securityToken": self.api_key}
        request_params.update(params)

        response = self.session.get(self.BASE_URL, params=request_params, timeout=30)
        response.raise_for_status()
        return response.text

    def get_load(
        self,
        area_code: str,
        start_date: str,
        end_date: str
    ) -> DataSourceResponse:
        """Get electricity load (consumption) data.

        Args:
            area_code: Bidding zone code (e.g., '10YCZ-CEPS-----N' for Czech Republic)
            start_date: Start date in YYYYMMDDHHmm format
            end_date: End date in YYYYMMDDHHmm format

        Returns:
            DataSourceResponse with load data (XML)
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {
                "documentType": "A65",  # System total load
                "processType": "A16",   # Realised
                "outBiddingZone_Domain": area_code,
                "periodStart": start_date,
                "periodEnd": end_date
            }

            xml_data = self._make_request(params)

            return DataSourceResponse.success_response(
                data={"xml": xml_data, "note": "XML parsing required"},
                metadata={
                    "source": "ENTSOE",
                    "area_code": area_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_type": "load"
                }
            )
        except Exception as e:
            return handle_request_error(e, "ENTSOE", "get_load")

    def get_generation(
        self,
        area_code: str,
        start_date: str,
        end_date: str
    ) -> DataSourceResponse:
        """Get electricity generation by type.

        Args:
            area_code: Bidding zone code
            start_date: Start date in YYYYMMDDHHmm format
            end_date: End date in YYYYMMDDHHmm format

        Returns:
            DataSourceResponse with generation data (XML)
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {
                "documentType": "A75",  # Actual generation per type
                "processType": "A16",   # Realised
                "in_Domain": area_code,
                "periodStart": start_date,
                "periodEnd": end_date
            }

            xml_data = self._make_request(params)

            return DataSourceResponse.success_response(
                data={"xml": xml_data, "note": "XML parsing required"},
                metadata={
                    "source": "ENTSOE",
                    "area_code": area_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_type": "generation"
                }
            )
        except Exception as e:
            return handle_request_error(e, "ENTSOE", "get_generation")

    def get_day_ahead_prices(
        self,
        area_code: str,
        start_date: str,
        end_date: str
    ) -> DataSourceResponse:
        """Get day-ahead electricity prices.

        Args:
            area_code: Bidding zone code
            start_date: Start date in YYYYMMDDHHmm format
            end_date: End date in YYYYMMDDHHmm format

        Returns:
            DataSourceResponse with price data (XML)
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {
                "documentType": "A44",  # Price Document
                "in_Domain": area_code,
                "out_Domain": area_code,
                "periodStart": start_date,
                "periodEnd": end_date
            }

            xml_data = self._make_request(params)

            return DataSourceResponse.success_response(
                data={"xml": xml_data, "note": "XML parsing required"},
                metadata={
                    "source": "ENTSOE",
                    "area_code": area_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_type": "day_ahead_prices"
                }
            )
        except Exception as e:
            return handle_request_error(e, "ENTSOE", "get_day_ahead_prices")

    def get_installed_capacity(
        self,
        area_code: str,
        start_date: str,
        end_date: str
    ) -> DataSourceResponse:
        """Get installed generation capacity.

        Args:
            area_code: Bidding zone code
            start_date: Start date in YYYYMMDDHHmm format
            end_date: End date in YYYYMMDDHHmm format

        Returns:
            DataSourceResponse with capacity data (XML)
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {
                "documentType": "A68",  # Installed capacity aggregated
                "processType": "A33",   # Week ahead
                "in_Domain": area_code,
                "periodStart": start_date,
                "periodEnd": end_date
            }

            xml_data = self._make_request(params)

            return DataSourceResponse.success_response(
                data={"xml": xml_data, "note": "XML parsing required"},
                metadata={
                    "source": "ENTSOE",
                    "area_code": area_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_type": "installed_capacity"
                }
            )
        except Exception as e:
            return handle_request_error(e, "ENTSOE", "get_installed_capacity")

    def get_cross_border_flows(
        self,
        from_area: str,
        to_area: str,
        start_date: str,
        end_date: str
    ) -> DataSourceResponse:
        """Get cross-border electricity flows.

        Args:
            from_area: Source bidding zone code
            to_area: Destination bidding zone code
            start_date: Start date in YYYYMMDDHHmm format
            end_date: End date in YYYYMMDDHHmm format

        Returns:
            DataSourceResponse with flow data (XML)
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {
                "documentType": "A11",  # Aggregated energy data report
                "in_Domain": from_area,
                "out_Domain": to_area,
                "periodStart": start_date,
                "periodEnd": end_date
            }

            xml_data = self._make_request(params)

            return DataSourceResponse.success_response(
                data={"xml": xml_data, "note": "XML parsing required"},
                metadata={
                    "source": "ENTSOE",
                    "from_area": from_area,
                    "to_area": to_area,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_type": "cross_border_flows"
                }
            )
        except Exception as e:
            return handle_request_error(e, "ENTSOE", "get_cross_border_flows")
