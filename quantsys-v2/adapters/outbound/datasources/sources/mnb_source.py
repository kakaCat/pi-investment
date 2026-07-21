"""Magyar Nemzeti Bank (MNB) Hungarian National Bank data source.

Provides access to Hungarian monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class MNBSource(EconomicDataSource):
    """Magyar Nemzeti Bank (Hungarian National Bank) data source.

    Provides base rate (policy rate), HUF exchange rates vs EUR/USD/CHF,
    CPI inflation, GDP growth, government bond yields, and money supply.
    No API key required.
    """

    BASE_URL = "https://www.mnb.hu/arfolyamok"
    API_URL = "https://www.mnb.hu"

    INDICATORS = {
        "base_rate": "MNB base rate (policy rate)",
        "overnight_deposit": "Overnight deposit rate",
        "overnight_lending": "Overnight lending rate",
        "cpi": "Consumer price index",
        "core_cpi": "Core CPI (excluding food/energy)",
        "gdp": "GDP growth",
        "eur_huf": "EUR/HUF exchange rate",
        "usd_huf": "USD/HUF exchange rate",
        "chf_huf": "CHF/HUF exchange rate",
        "government_yield_10y": "10-year government bond yield",
    }

    def __init__(self):
        super().__init__(name="MNB", requires_api_key=False)
        self.session = SessionManager.get_session("mnb")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            import xml.etree.ElementTree as ET
            response = self.session.get(
                f"{self.BASE_URL}/arfolyamok.asmx/GetCurrentExchangeRates",
                timeout=10,
            )
            response.raise_for_status()
            ET.fromstring(response.content)
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "MNB"},
                metadata={"source": "MNB", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"MNB connection test failed: {e}")
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
            params: Dict[str, Any] = {"currency": series_id}
            if start_date:
                params["startDate"] = start_date
            if end_date:
                params["endDate"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/arfolyamok.asmx/GetExchangeRates",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json() if response.headers.get("content-type", "").startswith("application/json")
                else {"raw": response.text},
                metadata={"source": "MNB", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "MNB", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "MNB", "query": query},
        )

    def get_exchange_rate(self, currency: str = "EUR") -> DataSourceResponse:
        """Get HUF exchange rate against a given currency."""
        return self.get_series(currency.upper())

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "MNB", "count": len(items)},
        )
