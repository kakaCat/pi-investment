"""UNDP (United Nations Development Programme) data source.

Provides access to human development data and statistics.

API Documentation: https://hdr.undp.org/
No official API - uses public data endpoints.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class UNDPSource(EconomicDataSource):
    """UNDP human development data source.

    Provides access to:
    - Human Development Index (HDI)
    - Inequality-adjusted HDI
    - Gender Development Index
    - Multidimensional Poverty Index
    - Country development data
    - Development reports

    No API key required (public data).
    """

    BASE_URL = "https://hdr.undp.org"
    DATA_URL = "https://hdr.undp.org/data-center"

    # HDI components
    HDI_COMPONENTS = [
        "Life Expectancy",
        "Education",
        "GNI per capita"
    ]

    def __init__(self):
        """Initialize UNDP data source."""
        super().__init__(name="UNDP", requires_api_key=False)
        self.session = SessionManager.get_session("undp")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to UNDP website.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "UNDP"},
                metadata={"source": "UNDP", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"UNDP connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_hdi_components(self) -> DataSourceResponse:
        """Get HDI component information.

        Returns:
            DataSourceResponse with HDI components
        """
        return DataSourceResponse.success_response(
            data=self.HDI_COMPONENTS,
            metadata={
                "source": "UNDP",
                "count": len(self.HDI_COMPONENTS)
            }
        )

    def get_data_center(self) -> DataSourceResponse:
        """Get UNDP data center information.

        Returns:
            DataSourceResponse with data center info
        """
        try:
            response = self.session.get(
                self.DATA_URL,
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": self.DATA_URL,
                    "description": "Human Development Data Center",
                    "note": "Portal access required for datasets"
                },
                metadata={
                    "source": "UNDP",
                    "data_type": "data_center"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNDP", "get_data_center")

    def get_hdi_rankings(self) -> DataSourceResponse:
        """Get HDI rankings information.

        Returns:
            DataSourceResponse with HDI rankings info
        """
        try:
            response = self.session.get(
                f"{self.DATA_URL}/human-development-index",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.DATA_URL}/human-development-index",
                    "description": "Human Development Index Rankings",
                    "note": "HTML parsing or CSV download required for data"
                },
                metadata={
                    "source": "UNDP",
                    "indicator": "HDI"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNDP", "get_hdi_rankings")

    def get_reports(self) -> DataSourceResponse:
        """Get Human Development Reports.

        Returns:
            DataSourceResponse with reports information
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/reports",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.BASE_URL}/reports",
                    "description": "Human Development Reports",
                    "note": "HTML parsing required for report list"
                },
                metadata={
                    "source": "UNDP",
                    "data_type": "reports"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNDP", "get_reports")

    def get_country_profiles(self) -> DataSourceResponse:
        """Get country profile information.

        Returns:
            DataSourceResponse with country profiles info
        """
        try:
            response = self.session.get(
                f"{self.DATA_URL}/country-profiles",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.DATA_URL}/country-profiles",
                    "description": "Country Development Profiles",
                    "note": "Portal access required for country data"
                },
                metadata={
                    "source": "UNDP",
                    "data_type": "country_profiles"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNDP", "get_country_profiles")

    def get_gender_index(self) -> DataSourceResponse:
        """Get Gender Development Index information.

        Returns:
            DataSourceResponse with GDI info
        """
        try:
            response = self.session.get(
                f"{self.DATA_URL}/gender-development-index",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.DATA_URL}/gender-development-index",
                    "description": "Gender Development Index",
                    "note": "HTML parsing or CSV download required for data"
                },
                metadata={
                    "source": "UNDP",
                    "indicator": "GDI"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNDP", "get_gender_index")

    def get_poverty_index(self) -> DataSourceResponse:
        """Get Multidimensional Poverty Index information.

        Returns:
            DataSourceResponse with MPI info
        """
        try:
            response = self.session.get(
                f"{self.DATA_URL}/multidimensional-poverty-index",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.DATA_URL}/multidimensional-poverty-index",
                    "description": "Multidimensional Poverty Index",
                    "note": "HTML parsing or CSV download required for data"
                },
                metadata={
                    "source": "UNDP",
                    "indicator": "MPI"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNDP", "get_poverty_index")
