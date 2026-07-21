"""UNEP (United Nations Environment Programme) data source.

Provides access to environmental data and statistics.

API Documentation: https://www.unep.org/
No official API - uses public data endpoints.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class UNEPSource(EconomicDataSource):
    """UNEP environmental data source.

    Provides access to:
    - Environmental statistics
    - Climate data
    - Biodiversity indicators
    - Pollution data
    - Sustainability reports
    - Environmental assessments

    No API key required (public data).
    """

    BASE_URL = "https://www.unep.org"
    DATA_URL = "https://data.unep.org"

    # Environmental themes
    THEMES = [
        "Climate Change",
        "Biodiversity",
        "Chemicals and Pollution",
        "Disasters and Conflicts",
        "Ecosystem Management",
        "Environmental Governance",
        "Resource Efficiency",
        "Oceans and Seas"
    ]

    def __init__(self):
        """Initialize UNEP data source."""
        super().__init__(name="UNEP", requires_api_key=False)
        self.session = SessionManager.get_session("unep")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to UNEP website.

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
                data={"status": "connected", "api": "UNEP"},
                metadata={"source": "UNEP", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"UNEP connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_themes(self) -> DataSourceResponse:
        """Get list of environmental themes.

        Returns:
            DataSourceResponse with theme list
        """
        return DataSourceResponse.success_response(
            data=self.THEMES,
            metadata={
                "source": "UNEP",
                "count": len(self.THEMES)
            }
        )

    def get_reports(self) -> DataSourceResponse:
        """Get environmental reports and publications.

        Returns:
            DataSourceResponse with reports information
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/resources/publications",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.BASE_URL}/resources/publications",
                    "note": "HTML parsing required for publication list"
                },
                metadata={
                    "source": "UNEP",
                    "data_type": "reports"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNEP", "get_reports")

    def get_environmental_data(self) -> DataSourceResponse:
        """Get environmental data portal information.

        Returns:
            DataSourceResponse with data portal info
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
                    "description": "UNEP Environmental Data Explorer",
                    "note": "Portal access required for datasets"
                },
                metadata={
                    "source": "UNEP",
                    "data_type": "environmental_data"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNEP", "get_environmental_data")

    def get_climate_data(self) -> DataSourceResponse:
        """Get climate change data and reports.

        Returns:
            DataSourceResponse with climate data info
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/explore-topics/climate-action",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.BASE_URL}/explore-topics/climate-action",
                    "theme": "Climate Change",
                    "note": "HTML parsing required for detailed data"
                },
                metadata={
                    "source": "UNEP",
                    "theme": "climate"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNEP", "get_climate_data")

    def get_biodiversity_data(self) -> DataSourceResponse:
        """Get biodiversity data and reports.

        Returns:
            DataSourceResponse with biodiversity data info
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/explore-topics/biodiversity",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.BASE_URL}/explore-topics/biodiversity",
                    "theme": "Biodiversity",
                    "note": "HTML parsing required for detailed data"
                },
                metadata={
                    "source": "UNEP",
                    "theme": "biodiversity"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNEP", "get_biodiversity_data")
