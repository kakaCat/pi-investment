"""AfDB (African Development Bank) data source.

Provides access to economic and development data for African countries.

API Documentation: https://dataportal.afdb.org/
No API key required for public data.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class AfDBSource(EconomicDataSource):
    """African Development Bank data source.

    Provides access to:
    - Economic indicators (GDP, inflation, trade)
    - Development indicators
    - Infrastructure data
    - Social indicators (poverty, education, health)
    - Climate and environment data
    - Country statistics

    No API key required.
    """

    BASE_URL = "https://dataportal.afdb.org/api/3/action"

    # Common indicator categories
    CATEGORIES = {
        "economic": "Economic Statistics",
        "social": "Social Statistics",
        "infrastructure": "Infrastructure",
        "environment": "Environment and Climate",
        "governance": "Governance",
        "finance": "Financial Sector"
    }

    def __init__(self):
        """Initialize AfDB data source."""
        super().__init__(name="AfDB", requires_api_key=False)
        self.session = SessionManager.get_session("afdb")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to AfDB API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/package_list",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                return DataSourceResponse.success_response(
                    data={"status": "connected", "api": "AfDB"},
                    metadata={"source": "AfDB", "base_url": self.BASE_URL}
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            logger.error(f"AfDB connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to AfDB API.

        Args:
            action: API action
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{action}"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_packages(self, limit: int = 100) -> DataSourceResponse:
        """Get list of available data packages.

        Args:
            limit: Maximum number of packages to return

        Returns:
            DataSourceResponse with package list
        """
        try:
            data = self._make_request("package_list", params={"limit": limit})

            if data.get("success"):
                return DataSourceResponse.success_response(
                    data=data.get("result", []),
                    metadata={
                        "source": "AfDB",
                        "count": len(data.get("result", []))
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            return handle_request_error(e, "AfDB", "get_packages")

    def get_package(self, package_id: str) -> DataSourceResponse:
        """Get details of a specific package.

        Args:
            package_id: Package identifier

        Returns:
            DataSourceResponse with package details
        """
        try:
            data = self._make_request("package_show", params={"id": package_id})

            if data.get("success"):
                return DataSourceResponse.success_response(
                    data=data.get("result", {}),
                    metadata={
                        "source": "AfDB",
                        "package_id": package_id
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            return handle_request_error(e, "AfDB", "get_package")

    def search_datasets(
        self,
        query: str,
        limit: int = 100
    ) -> DataSourceResponse:
        """Search for datasets.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            DataSourceResponse with search results
        """
        try:
            data = self._make_request(
                "package_search",
                params={"q": query, "rows": limit}
            )

            if data.get("success"):
                result = data.get("result", {})
                return DataSourceResponse.success_response(
                    data=result.get("results", []),
                    metadata={
                        "source": "AfDB",
                        "query": query,
                        "count": result.get("count", 0)
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            return handle_request_error(e, "AfDB", "search_datasets")

    def get_datastore(
        self,
        resource_id: str,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> DataSourceResponse:
        """Get data from a datastore resource.

        Args:
            resource_id: Resource identifier
            limit: Maximum number of records
            filters: Filter conditions

        Returns:
            DataSourceResponse with datastore data
        """
        try:
            params = {"resource_id": resource_id, "limit": limit}
            if filters:
                params["filters"] = filters

            data = self._make_request("datastore_search", params=params)

            if data.get("success"):
                result = data.get("result", {})
                return DataSourceResponse.success_response(
                    data=result.get("records", []),
                    metadata={
                        "source": "AfDB",
                        "resource_id": resource_id,
                        "total": result.get("total", 0)
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            return handle_request_error(e, "AfDB", "get_datastore")

    def get_country_data(
        self,
        country: str,
        category: Optional[str] = None
    ) -> DataSourceResponse:
        """Get data for a specific African country.

        Args:
            country: Country name or code
            category: Data category (optional)

        Returns:
            DataSourceResponse with country data
        """
        try:
            query = f"country:{country}"
            if category:
                query += f" {category}"

            return self.search_datasets(query, limit=50)
        except Exception as e:
            return handle_request_error(e, "AfDB", "get_country_data")
