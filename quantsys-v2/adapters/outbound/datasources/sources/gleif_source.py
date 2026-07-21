"""GLEIF (Global Legal Entity Identifier Foundation) data source.

Provides access to Legal Entity Identifier (LEI) reference data.

API Documentation: https://www.gleif.org/en/lei-data/gleif-concatenated-file/download
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class GLEIFSource(EconomicDataSource):
    """GLEIF Legal Entity Identifier data source.

    Provides access to:
    - Legal Entity Identifier (LEI) records
    - Entity information (legal name, status, address)
    - Relationship data (parent-child, branch)
    - Registration status
    - Historical LEI data

    No API key required.
    """

    BASE_URL = "https://api.gleif.org/api/v1"

    def __init__(self):
        """Initialize GLEIF data source."""
        super().__init__(name="GLEIF", requires_api_key=False)
        self.session = SessionManager.get_session("gleif")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to GLEIF API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/lei-records",
                params={"page[size]": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "GLEIF"},
                metadata={"source": "GLEIF", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"GLEIF connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to GLEIF API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_lei_record(self, lei: str) -> DataSourceResponse:
        """Get LEI record for a specific legal entity.

        Args:
            lei: LEI code (20-character alphanumeric)

        Returns:
            DataSourceResponse with LEI record
        """
        try:
            if len(lei) != 20:
                return DataSourceResponse.error_response(
                    error=f"Invalid LEI: {lei}. Must be 20 characters."
                )

            data = self._make_request(f"lei-records/{lei}")

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "GLEIF",
                    "lei": lei
                }
            )
        except Exception as e:
            return handle_request_error(e, "GLEIF", "get_lei_record")

    def search_lei(
        self,
        entity_name: Optional[str] = None,
        country: Optional[str] = None,
        page_size: int = 50
    ) -> DataSourceResponse:
        """Search for LEI records.

        Args:
            entity_name: Legal entity name to search
            country: Country code (ISO 3166-1 alpha-2)
            page_size: Records per page

        Returns:
            DataSourceResponse with LEI records
        """
        try:
            params = {"page[size]": page_size}

            filters = []
            if entity_name:
                filters.append({"field": "entity.legalName", "operator": "CONTAINS", "value": entity_name})
            if country:
                filters.append({"field": "entity.legalAddress.country", "operator": "=", "value": country})

            if filters:
                params["filter"] = filters

            data = self._make_request("lei-records", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "GLEIF",
                    "entity_name": entity_name,
                    "country": country,
                    "total": data.get("meta", {}).get("pagination", {}).get("total", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "GLEIF", "search_lei")

    def get_parent_relationship(self, lei: str) -> DataSourceResponse:
        """Get parent entity relationship.

        Args:
            lei: LEI code

        Returns:
            DataSourceResponse with parent relationship
        """
        try:
            data = self._make_request(f"lei-records/{lei}/direct-parent-relationship")

            return DataSourceResponse.success_response(
                data=data.get("data", {}),
                metadata={
                    "source": "GLEIF",
                    "lei": lei,
                    "relationship": "direct_parent"
                }
            )
        except Exception as e:
            return handle_request_error(e, "GLEIF", "get_parent_relationship")

    def get_isin_mapping(self, lei: str) -> DataSourceResponse:
        """Get ISIN-to-LEI mapping.

        Args:
            lei: LEI code

        Returns:
            DataSourceResponse with ISIN mapping
        """
        try:
            data = self._make_request(f"lei-records/{lei}/isins")

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "GLEIF",
                    "lei": lei
                }
            )
        except Exception as e:
            return handle_request_error(e, "GLEIF", "get_isin_mapping")
