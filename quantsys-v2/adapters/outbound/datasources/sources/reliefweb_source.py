"""ReliefWeb humanitarian data source.

Provides access to humanitarian crisis and disaster information worldwide.

API Documentation: https://apidoc.reliefweb.int/
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class ReliefWebSource(EconomicDataSource):
    """ReliefWeb humanitarian data source.

    Provides access to:
    - Disaster reports
    - Humanitarian updates
    - Country information
    - Organization data
    - Job postings
    - Training opportunities

    No API key required.
    """

    BASE_URL = "https://api.reliefweb.int/v1"

    # Resource types
    RESOURCES = [
        "reports", "jobs", "training", "disasters", "countries",
        "sources", "topics", "languages", "formats"
    ]

    def __init__(self):
        """Initialize ReliefWeb data source."""
        super().__init__(name="ReliefWeb", requires_api_key=False)
        self.session = SessionManager.get_session("reliefweb")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to ReliefWeb API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/reports",
                params={"limit": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "ReliefWeb"},
                metadata={"source": "ReliefWeb", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"ReliefWeb connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make request to ReliefWeb API.

        Args:
            resource: Resource type (e.g., 'reports', 'disasters')
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{resource}"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_reports(
        self,
        query: Optional[str] = None,
        country: Optional[str] = None,
        disaster: Optional[str] = None,
        limit: int = 10
    ) -> DataSourceResponse:
        """Get humanitarian reports.

        Args:
            query: Search query
            country: Country ISO3 code
            disaster: Disaster ID
            limit: Maximum number of results

        Returns:
            DataSourceResponse with reports
        """
        try:
            params = {"limit": limit}

            # Build filter
            filters = []
            if query:
                params["query"] = {"value": query}
            if country:
                filters.append({"field": "country.iso3", "value": country})
            if disaster:
                filters.append({"field": "disaster.id", "value": disaster})

            if filters:
                params["filter"] = {"operator": "AND", "conditions": filters}

            data = self._make_request("reports", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "ReliefWeb",
                    "totalCount": data.get("totalCount", 0),
                    "count": data.get("count", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "ReliefWeb", "get_reports")

    def get_disasters(
        self,
        country: Optional[str] = None,
        status: str = "current",
        limit: int = 10
    ) -> DataSourceResponse:
        """Get disaster information.

        Args:
            country: Country ISO3 code
            status: Disaster status ('current', 'past', 'all')
            limit: Maximum number of results

        Returns:
            DataSourceResponse with disaster data
        """
        try:
            params = {"limit": limit}

            filters = []
            if country:
                filters.append({"field": "country.iso3", "value": country})
            if status != "all":
                filters.append({"field": "status", "value": status})

            if filters:
                params["filter"] = {"operator": "AND", "conditions": filters}

            data = self._make_request("disasters", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "ReliefWeb",
                    "totalCount": data.get("totalCount", 0),
                    "status": status
                }
            )
        except Exception as e:
            return handle_request_error(e, "ReliefWeb", "get_disasters")

    def get_countries(self, limit: int = 250) -> DataSourceResponse:
        """Get list of countries.

        Args:
            limit: Maximum number of results

        Returns:
            DataSourceResponse with country list
        """
        try:
            params = {"limit": limit}
            data = self._make_request("countries", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "ReliefWeb",
                    "count": data.get("count", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "ReliefWeb", "get_countries")

    def get_country_info(self, iso3: str) -> DataSourceResponse:
        """Get information for a specific country.

        Args:
            iso3: Country ISO3 code (e.g., 'USA', 'GBR')

        Returns:
            DataSourceResponse with country information
        """
        try:
            data = self._make_request(f"countries/{iso3}")

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "ReliefWeb",
                    "iso3": iso3
                }
            )
        except Exception as e:
            return handle_request_error(e, "ReliefWeb", "get_country_info")

    def search(
        self,
        query: str,
        resource: str = "reports",
        limit: int = 10
    ) -> DataSourceResponse:
        """Search across resources.

        Args:
            query: Search query
            resource: Resource type to search
            limit: Maximum number of results

        Returns:
            DataSourceResponse with search results
        """
        try:
            if resource not in self.RESOURCES:
                return DataSourceResponse.error_response(
                    error=f"Invalid resource: {resource}. Valid: {self.RESOURCES}"
                )

            params = {
                "query": {"value": query},
                "limit": limit
            }

            data = self._make_request(resource, params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "ReliefWeb",
                    "query": query,
                    "resource": resource,
                    "totalCount": data.get("totalCount", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "ReliefWeb", "search")
