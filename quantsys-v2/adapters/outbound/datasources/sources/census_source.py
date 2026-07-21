"""US Census Bureau economic data source.

Provides access to US economic census, business patterns, housing,
construction, retail trade, and international trade statistics.
No API key required for basic endpoints.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CensusSource(EconomicDataSource):
    """US Census Bureau economic data source.

    Provides Economic Census, County Business Patterns, construction spending
    (housing starts, building permits), retail and wholesale trade, manufacturers'
    shipments, and international trade (exports/imports by commodity/country).
    No API key required.
    """

    BASE_URL = "https://api.census.gov/data"

    DATASETS = {
        "construction": "Construction spending, housing starts, building permits",
        "retail_trade": "Monthly and annual retail trade survey",
        "wholesale_trade": "Monthly wholesale trade survey",
        "manufacturing": "Manufacturers' shipments, inventories, orders",
        "international_trade": "US international trade in goods and services",
        "cbp": "County Business Patterns (establishments, employment, payroll)",
        "economic_census": "Economic Census (every 5 years)",
    }

    INDICATORS = {
        "housing_starts": "New residential construction (housing starts)",
        "building_permits": "Building permits authorized",
        "construction_spending": "Value of construction put in place",
        "retail_sales": "Advance monthly retail sales",
        "manufacturing_orders": "Manufacturers' new orders (durable goods)",
        "trade_balance": "US international trade balance",
        "homeownership_rate": "Homeownership rate",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="Census", requires_api_key=False)
        self.api_key = api_key or os.getenv("CENSUS_API_KEY", "")
        self.session = SessionManager.get_session("census")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/2022/zbp",
                params={"get": "ESTAB", "for": "us:1", "NAICS2017": "00"},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "USCensus"},
                metadata={"source": "USCensus", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Census connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {"get": series_id, "for": "us:1"}
            if self.api_key:
                params["key"] = self.api_key
            response = self.session.get(
                f"{self.BASE_URL}/timeseries/econ/construction",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "USCensus", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "Census", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "USCensus", "query": query},
        )

    def get_datasets(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.DATASETS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "USCensus", "count": len(items)},
        )

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "USCensus", "count": len(items)},
        )
