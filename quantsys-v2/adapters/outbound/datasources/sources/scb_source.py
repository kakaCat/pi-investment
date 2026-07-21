"""SCB (Statistics Sweden) data source.

Provides access to Swedish statistical data including population, economy,
labor market, prices, and social statistics.

API Documentation: https://www.scb.se/en/services/open-data-api/
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class SCBSource(EconomicDataSource):
    """Statistics Sweden (SCB) data source.

    Provides access to:
    - Population statistics
    - Labor market data
    - National accounts (GDP)
    - Price indices (CPI, PPI)
    - Energy statistics
    - Education and research
    - Healthcare statistics

    No API key required.
    """

    BASE_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd"

    # Common table paths
    TABLES = {
        "population": "BE/BE0101/BE0101A/BefolkningNy",
        "gdp": "NR/NR0103/NR0103A/NR0103ENS2010T01Kv",
        "employment": "AM/AM0201/AM0201A/ArbStatusM",
        "unemployment": "AM/AM0401/AM0401A/AKUArblosaMv",
        "cpi": "PR/PR0101/PR0101A/KPIFastM2",
        "ppi": "PR/PR0301/PR0301A/PPI2015M",
    }

    def __init__(self):
        """Initialize SCB data source."""
        super().__init__(name="SCB", requires_api_key=False)
        self.session = SessionManager.get_session("scb")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to SCB API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/BE/BE0101",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "SCB"},
                metadata={"source": "SCB", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"SCB connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make request to SCB API.

        Args:
            endpoint: API endpoint path
            method: HTTP method ('GET' or 'POST')
            json_data: JSON data for POST requests

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"

        if method == "POST":
            response = self.session.post(url, json=json_data, timeout=30)
        else:
            response = self.session.get(url, timeout=30)

        response.raise_for_status()
        return response.json()

    def get_table_metadata(self, table_path: str) -> DataSourceResponse:
        """Get metadata for a specific table.

        Args:
            table_path: Table path (e.g., 'BE/BE0101/BE0101A/BefolkningNy')

        Returns:
            DataSourceResponse with table metadata
        """
        try:
            data = self._make_request(table_path)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "SCB",
                    "table_path": table_path
                }
            )
        except Exception as e:
            return handle_request_error(e, "SCB", "get_table_metadata")

    def get_table_data(
        self,
        table_path: str,
        query: Dict[str, Any]
    ) -> DataSourceResponse:
        """Get data from a specific table with query.

        Args:
            table_path: Table path
            query: Query specification (variables, values, time periods)

        Returns:
            DataSourceResponse with table data
        """
        try:
            data = self._make_request(table_path, method="POST", json_data=query)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "SCB",
                    "table_path": table_path
                }
            )
        except Exception as e:
            return handle_request_error(e, "SCB", "get_table_data")

    def get_population(
        self,
        years: Optional[List[str]] = None
    ) -> DataSourceResponse:
        """Get Swedish population statistics.

        Args:
            years: List of years to retrieve (e.g., ['2020', '2021'])

        Returns:
            DataSourceResponse with population data
        """
        try:
            # Build query
            query = {
                "query": [
                    {
                        "code": "Region",
                        "selection": {
                            "filter": "vs:RegionRiket99",
                            "values": ["00"]
                        }
                    },
                    {
                        "code": "Alder",
                        "selection": {
                            "filter": "vs:ÅlderTot",
                            "values": ["tot"]
                        }
                    }
                ],
                "response": {
                    "format": "json"
                }
            }

            if years:
                query["query"].append({
                    "code": "Tid",
                    "selection": {
                        "filter": "item",
                        "values": years
                    }
                })

            return self.get_table_data(self.TABLES["population"], query)
        except Exception as e:
            return handle_request_error(e, "SCB", "get_population")

    def get_gdp(
        self,
        quarters: Optional[List[str]] = None
    ) -> DataSourceResponse:
        """Get Swedish GDP data.

        Args:
            quarters: List of quarters (e.g., ['2020Q1', '2020Q2'])

        Returns:
            DataSourceResponse with GDP data
        """
        try:
            query = {
                "query": [
                    {
                        "code": "ContentsCode",
                        "selection": {
                            "filter": "item",
                            "values": ["NR0103ENS2010T01"]
                        }
                    }
                ],
                "response": {
                    "format": "json"
                }
            }

            if quarters:
                query["query"].append({
                    "code": "Tid",
                    "selection": {
                        "filter": "item",
                        "values": quarters
                    }
                })

            return self.get_table_data(self.TABLES["gdp"], query)
        except Exception as e:
            return handle_request_error(e, "SCB", "get_gdp")

    def get_cpi(
        self,
        months: Optional[List[str]] = None
    ) -> DataSourceResponse:
        """Get Swedish Consumer Price Index.

        Args:
            months: List of months (e.g., ['2020M01', '2020M02'])

        Returns:
            DataSourceResponse with CPI data
        """
        try:
            query = {
                "query": [
                    {
                        "code": "ContentsCode",
                        "selection": {
                            "filter": "item",
                            "values": ["000004VU"]
                        }
                    }
                ],
                "response": {
                    "format": "json"
                }
            }

            if months:
                query["query"].append({
                    "code": "Tid",
                    "selection": {
                        "filter": "item",
                        "values": months
                    }
                })

            return self.get_table_data(self.TABLES["cpi"], query)
        except Exception as e:
            return handle_request_error(e, "SCB", "get_cpi")

    def get_unemployment(
        self,
        months: Optional[List[str]] = None
    ) -> DataSourceResponse:
        """Get Swedish unemployment data.

        Args:
            months: List of months (e.g., ['2020M01', '2020M02'])

        Returns:
            DataSourceResponse with unemployment data
        """
        try:
            query = {
                "query": [
                    {
                        "code": "Kon",
                        "selection": {
                            "filter": "item",
                            "values": ["1+2"]
                        }
                    }
                ],
                "response": {
                    "format": "json"
                }
            }

            if months:
                query["query"].append({
                    "code": "Tid",
                    "selection": {
                        "filter": "item",
                        "values": months
                    }
                })

            return self.get_table_data(self.TABLES["unemployment"], query)
        except Exception as e:
            return handle_request_error(e, "SCB", "get_unemployment")
