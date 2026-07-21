"""ADB (Asian Development Bank) data source.

Provides access to economic and development data for Asia-Pacific region.

API Documentation: https://data.adb.org/
No API key required for public data.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class ADBSource(EconomicDataSource):
    """Asian Development Bank data source.

    Provides access to:
    - Economic indicators (GDP, inflation, trade)
    - Development indicators
    - Social indicators (poverty, education, health)
    - Infrastructure data
    - Climate and environment data
    - Regional cooperation data

    No API key required.
    """

    BASE_URL = "https://data.adb.org/api/3/action"

    # Common indicator codes
    INDICATORS = {
        "gdp_growth": "SNA.GDP.GRTH",
        "gdp_per_capita": "SNA.GDP.PCAP",
        "inflation": "PRC.CPI.INFL",
        "unemployment": "LBR.UNEM.RATE",
        "poverty": "POV.HDCNT.190",
        "life_expectancy": "HLT.LIFE.EXPC",
        "literacy": "EDU.LIT.RATE",
        "co2_emissions": "ENV.CO2.EMIS",
    }

    def __init__(self):
        """Initialize ADB data source."""
        super().__init__(name="ADB", requires_api_key=False)
        self.session = SessionManager.get_session("adb")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to ADB API.

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
                    data={"status": "connected", "api": "ADB"},
                    metadata={"source": "ADB", "base_url": self.BASE_URL}
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            logger.error(f"ADB connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to ADB API.

        Args:
            action: API action (e.g., 'package_list', 'datastore_search')
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
                        "source": "ADB",
                        "count": len(data.get("result", []))
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            return handle_request_error(e, "ADB", "get_packages")

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
                        "source": "ADB",
                        "package_id": package_id
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            return handle_request_error(e, "ADB", "get_package")

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
                        "source": "ADB",
                        "query": query,
                        "count": result.get("count", 0)
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            return handle_request_error(e, "ADB", "search_datasets")

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
                        "source": "ADB",
                        "resource_id": resource_id,
                        "total": result.get("total", 0)
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error="API returned success=false"
                )
        except Exception as e:
            return handle_request_error(e, "ADB", "get_datastore")

    def get_economic_indicator(
        self,
        indicator: str,
        country: Optional[str] = None,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None
    ) -> DataSourceResponse:
        """Get economic indicator data.

        Args:
            indicator: Indicator code (e.g., 'SNA.GDP.GRTH')
            country: Country code (optional)
            year_start: Start year (optional)
            year_end: End year (optional)

        Returns:
            DataSourceResponse with indicator data
        """
        try:
            # Build search query
            query = f"indicator:{indicator}"
            if country:
                query += f" country:{country}"

            # Search for the indicator dataset
            search_result = self.search_datasets(query, limit=1)

            if not search_result.success or not search_result.data:
                return DataSourceResponse.error_response(
                    error=f"Indicator {indicator} not found"
                )

            # Get the first resource from the dataset
            dataset = search_result.data[0]
            resources = dataset.get("resources", [])

            if not resources:
                return DataSourceResponse.error_response(
                    error="No resources found for indicator"
                )

            resource_id = resources[0].get("id")

            # Build filters
            filters = {}
            if year_start:
                filters["year"] = {">=": year_start}
            if year_end:
                if "year" in filters:
                    filters["year"]["<="] = year_end
                else:
                    filters["year"] = {"<=": year_end}

            # Get the data
            return self.get_datastore(resource_id, limit=1000, filters=filters if filters else None)

        except Exception as e:
            return handle_request_error(e, "ADB", "get_economic_indicator")
