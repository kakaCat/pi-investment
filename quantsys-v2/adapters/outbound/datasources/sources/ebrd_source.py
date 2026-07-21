"""EBRD (European Bank for Reconstruction and Development) data source.

Provides access to economic and development data for emerging markets
in Europe, Central Asia, and beyond.

API Documentation: https://www.ebrd.com/what-we-do/economic-research-and-data
No API key required for public data.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EBRDSource(EconomicDataSource):
    """European Bank for Reconstruction and Development data source.

    Provides access to:
    - Economic indicators (GDP, inflation, trade)
    - Transition indicators
    - Investment data
    - Country forecasts
    - Regional economic outlook

    No API key required.
    """

    BASE_URL = "https://www.ebrd.com"

    # EBRD regions
    REGIONS = [
        "Central Europe and the Baltic states",
        "South-eastern Europe",
        "Eastern Europe and the Caucasus",
        "Central Asia",
        "Southern and eastern Mediterranean",
        "Turkey"
    ]

    def __init__(self):
        """Initialize EBRD data source."""
        super().__init__(name="EBRD", requires_api_key=False)
        self.session = SessionManager.get_session("ebrd")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to EBRD website.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/what-we-do/economic-research-and-data",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "EBRD"},
                metadata={"source": "EBRD", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"EBRD connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_regions(self) -> DataSourceResponse:
        """Get list of EBRD regions.

        Returns:
            DataSourceResponse with region list
        """
        return DataSourceResponse.success_response(
            data=self.REGIONS,
            metadata={
                "source": "EBRD",
                "count": len(self.REGIONS)
            }
        )

    def get_transition_report(self) -> DataSourceResponse:
        """Get latest Transition Report.

        Returns:
            DataSourceResponse with report info
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/transition-report",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "message": "EBRD Transition Report available",
                    "url": f"{self.BASE_URL}/transition-report",
                    "note": "Report parsing required for structured data"
                },
                metadata={
                    "source": "EBRD",
                    "data_type": "transition_report"
                }
            )
        except Exception as e:
            return handle_request_error(e, "EBRD", "get_transition_report")

    def get_regional_outlook(self) -> DataSourceResponse:
        """Get Regional Economic Prospects.

        Returns:
            DataSourceResponse with outlook info
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/publications/regional-economic-prospects",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "message": "Regional Economic Prospects available",
                    "url": f"{self.BASE_URL}/publications/regional-economic-prospects",
                    "note": "Report parsing required for structured data"
                },
                metadata={
                    "source": "EBRD",
                    "data_type": "regional_outlook"
                }
            )
        except Exception as e:
            return handle_request_error(e, "EBRD", "get_regional_outlook")
