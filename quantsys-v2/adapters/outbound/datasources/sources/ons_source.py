"""UK Office for National Statistics (ONS) data source.

Provides access to UK economic statistics including GDP, CPI, unemployment,
trade, population, and housing data.

API Documentation: https://developer.ons.gov.uk/
No API key required for public data.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class ONSSource(EconomicDataSource):
    """UK Office for National Statistics data source.

    Provides access to:
    - GDP (quarterly and annual)
    - Consumer Price Index (CPI)
    - Labour market statistics
    - Trade data
    - Population statistics
    - Housing data

    No API key required.
    """

    BASE_URL = "https://api.ons.gov.uk/v1"

    # Common dataset and timeseries IDs
    DATASETS = {
        "gdp": "qna",
        "cpi": "mm23",
        "labour": "lms",
        "trade": "ots",
        "population": "mid-year-pop-est",
        "housing": "hpssa"
    }

    TIMESERIES = {
        "gdp_quarterly": {"dataset": "qna", "id": "ABMI"},
        "cpi_all_items": {"dataset": "mm23", "id": "D7G7"},
        "unemployment_rate": {"dataset": "lms", "id": "MGSX"},
        "exports_goods": {"dataset": "ots", "id": "BOKH"},
        "imports_goods": {"dataset": "ots", "id": "BOKJ"}
    }

    def __init__(self):
        """Initialize ONS data source."""
        super().__init__(name="ONS", requires_api_key=False)
        self.session = SessionManager.get_session("ons")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to ONS API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/datasets",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "ONS"},
                metadata={"source": "ONS", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"ONS connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to ONS API.

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

    def get_datasets(self) -> DataSourceResponse:
        """Get list of available datasets.

        Returns:
            DataSourceResponse with dataset list
        """
        try:
            data = self._make_request("datasets")
            return DataSourceResponse.success_response(
                data=data.get("items", []),
                metadata={"source": "ONS", "endpoint": "datasets"}
            )
        except Exception as e:
            return handle_request_error(e, "ONS", "get_datasets")

    def get_timeseries(
        self,
        dataset_id: str,
        timeseries_id: str,
        start_year: Optional[str] = None,
        end_year: Optional[str] = None
    ) -> DataSourceResponse:
        """Get timeseries data.

        Args:
            dataset_id: Dataset identifier (e.g., 'qna' for GDP)
            timeseries_id: Timeseries identifier (e.g., 'ABMI')
            start_year: Start year (YYYY format)
            end_year: End year (YYYY format)

        Returns:
            DataSourceResponse with timeseries data
        """
        try:
            endpoint = f"datasets/{dataset_id}/timeseries/{timeseries_id}/data"
            params = {}
            if start_year:
                params["startYear"] = start_year
            if end_year:
                params["endYear"] = end_year

            data = self._make_request(endpoint, params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "ONS",
                    "dataset": dataset_id,
                    "timeseries": timeseries_id,
                    "start_year": start_year,
                    "end_year": end_year
                }
            )
        except Exception as e:
            return handle_request_error(e, "ONS", "get_timeseries")

    def get_gdp(
        self,
        frequency: str = "quarterly",
        start_year: str = "2020",
        end_year: str = "2024"
    ) -> DataSourceResponse:
        """Get UK GDP data.

        Args:
            frequency: Data frequency ('quarterly' or 'annual')
            start_year: Start year (YYYY)
            end_year: End year (YYYY)

        Returns:
            DataSourceResponse with GDP data
        """
        ts = self.TIMESERIES["gdp_quarterly"]
        return self.get_timeseries(
            dataset_id=ts["dataset"],
            timeseries_id=ts["id"],
            start_year=start_year,
            end_year=end_year
        )

    def get_cpi(
        self,
        category: str = "all_items",
        start_year: str = "2020",
        end_year: str = "2024"
    ) -> DataSourceResponse:
        """Get UK Consumer Price Index data.

        Args:
            category: CPI category ('all_items' supported)
            start_year: Start year (YYYY)
            end_year: End year (YYYY)

        Returns:
            DataSourceResponse with CPI data
        """
        ts = self.TIMESERIES["cpi_all_items"]
        return self.get_timeseries(
            dataset_id=ts["dataset"],
            timeseries_id=ts["id"],
            start_year=start_year,
            end_year=end_year
        )

    def get_unemployment(
        self,
        measure: str = "rate",
        start_year: str = "2020",
        end_year: str = "2024"
    ) -> DataSourceResponse:
        """Get UK unemployment data.

        Args:
            measure: Unemployment measure ('rate' supported)
            start_year: Start year (YYYY)
            end_year: End year (YYYY)

        Returns:
            DataSourceResponse with unemployment data
        """
        ts = self.TIMESERIES["unemployment_rate"]
        return self.get_timeseries(
            dataset_id=ts["dataset"],
            timeseries_id=ts["id"],
            start_year=start_year,
            end_year=end_year
        )

    def get_trade(
        self,
        trade_type: str = "exports",
        start_year: str = "2020",
        end_year: str = "2024"
    ) -> DataSourceResponse:
        """Get UK trade data.

        Args:
            trade_type: Trade type ('exports' or 'imports')
            start_year: Start year (YYYY)
            end_year: End year (YYYY)

        Returns:
            DataSourceResponse with trade data
        """
        if trade_type == "exports":
            ts = self.TIMESERIES["exports_goods"]
        elif trade_type == "imports":
            ts = self.TIMESERIES["imports_goods"]
        else:
            return DataSourceResponse.error_response(
                error=f"Invalid trade_type: {trade_type}. Use 'exports' or 'imports'."
            )

        return self.get_timeseries(
            dataset_id=ts["dataset"],
            timeseries_id=ts["id"],
            start_year=start_year,
            end_year=end_year
        )

    def search(self, query: str) -> DataSourceResponse:
        """Search ONS datasets and timeseries.

        Args:
            query: Search query string

        Returns:
            DataSourceResponse with search results
        """
        try:
            data = self._make_request("search", params={"q": query})
            return DataSourceResponse.success_response(
                data=data.get("items", []),
                metadata={
                    "source": "ONS",
                    "query": query,
                    "count": data.get("count", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "ONS", "search")
