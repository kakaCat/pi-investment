"""Hrvatska Narodna Banka (HNB) Croatian National Bank data source.

Provides access to Croatian monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class HNBSource(EconomicDataSource):
    """Hrvatska Narodna Banka (Croatian National Bank) data source.

    Provides EUR/HRK and other exchange rates, CPI inflation, GDP growth,
    monetary aggregates, and banking sector statistics.
    No API key required.
    """

    BASE_URL = "https://api.hnb.hr"

    INDICATORS = {
        "exchange_rates": "Daily exchange rate list",
        "exchange_rates_archive": "Historical exchange rates",
        "interest_rates": "Key interest rates",
        "cpi": "Consumer price index",
        "gdp": "GDP growth rate",
        "monetary_aggregates": "Money supply (M1, M2, M3)",
        "balance_of_payments": "Balance of payments",
    }

    def __init__(self):
        super().__init__(name="HNB", requires_api_key=False)
        self.session = SessionManager.get_session("hnb")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/tecajn/v1", timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "HNB"},
                metadata={"source": "HNB", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"HNB connection test failed: {e}")
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
            params: Dict[str, Any] = {}
            if start_date:
                params["date_from"] = start_date
            if end_date:
                params["date_to"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/tecajn/v1", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "HNB", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "HNB", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "HNB", "query": query},
        )

    def get_exchange_rates(self) -> DataSourceResponse:
        """Get HNB daily exchange rate list."""
        return self.get_series("exchange_rates")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "HNB", "count": len(items)},
        )
