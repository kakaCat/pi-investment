"""Bank of Israel (BOI) central bank data source.

Provides access to Israeli monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BankOfIsraelSource(EconomicDataSource):
    """Bank of Israel (BOI) central bank data source.

    Provides access to Bank of Israel interest rate, CPI inflation, GDP growth,
    exchange rates (ILS vs USD/EUR), housing price index, and labor market data.
    No API key required.
    """

    BASE_URL = "https://www.boi.org.il/boi_i_api"

    INDICATORS = {
        "interest_rate": "Monetary policy interest rate",
        "cpi": "Consumer price index",
        "gdp": "Gross domestic product",
        "usd_ils": "USD/ILS exchange rate",
        "eur_ils": "EUR/ILS exchange rate",
        "housing_price_index": "Housing price index",
        "unemployment": "Unemployment rate",
        "foreign_reserves": "Foreign exchange reserves",
    }

    def __init__(self):
        super().__init__(name="BankOfIsrael", requires_api_key=False)
        self.session = SessionManager.get_session("boi")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/data?series=INT.RATE&format=json",
                timeout=15,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "BankOfIsrael"},
                metadata={"source": "BankOfIsrael", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"BOI connection test failed: {e}")
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
            params: Dict[str, Any] = {
                "series": series_id,
                "format": "json",
            }
            if start_date:
                params["from"] = start_date
            if end_date:
                params["to"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/data", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "BankOfIsrael", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "BankOfIsrael", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "BankOfIsrael", "query": query},
        )

    def get_interest_rate(self) -> DataSourceResponse:
        """Get Bank of Israel monetary policy rate."""
        return self.get_series("INT.RATE")

    def get_exchange_rate(self, currency: str = "USD") -> DataSourceResponse:
        """Get ILS exchange rate against a given currency."""
        series_map = {"USD": "USD.ILS.SPOT", "EUR": "EUR.ILS.SPOT", "GBP": "GBP.ILS.SPOT"}
        series_id = series_map.get(currency.upper(), "USD.ILS.SPOT")
        return self.get_series(series_id)

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "BankOfIsrael", "count": len(items)},
        )
