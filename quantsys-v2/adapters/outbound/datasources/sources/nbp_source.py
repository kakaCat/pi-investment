"""Narodowy Bank Polski (NBP) central bank data source.

Provides access to Polish monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class NBPSource(EconomicDataSource):
    """Narodowy Bank Polski (NBP) central bank data source.

    Provides NBP reference rate (policy rate), PLN exchange rates (EUR/PLN,
    USD/PLN, CHF/PLN, GBP/PLN), CPI inflation, GDP growth, WIBOR interbank
    rates, and NBP bill yields.
    No API key required. Uses NBP Web API.
    """

    BASE_URL = "https://api.nbp.pl/api"

    INDICATORS = {
        "reference_rate": "NBP reference rate (stopa referencyjna)",
        "lombard_rate": "Lombard rate",
        "deposit_rate": "Deposit rate",
        "rediscount_rate": "Rediscount rate",
        "cpi": "Consumer price index",
        "gdp": "GDP growth",
        "eur_pln": "EUR/PLN exchange rate",
        "usd_pln": "USD/PLN exchange rate",
        "chf_pln": "CHF/PLN exchange rate",
        "gbp_pln": "GBP/PLN exchange rate",
        "wibor_3m": "WIBOR 3-month interbank rate",
    }

    def __init__(self):
        super().__init__(name="NBP", requires_api_key=False)
        self.session = SessionManager.get_session("nbp")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/exchangerates/tables/A/?format=json",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "NBP"},
                metadata={"source": "NBP", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"NBP connection test failed: {e}")
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
            url = f"{self.BASE_URL}/exchangerates/tables/A/"
            if start_date and end_date:
                url += f"{start_date}/{end_date}/"
            url += "?format=json"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "NBP", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "NBP", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "NBP", "query": query},
        )

    def get_exchange_rates(self) -> DataSourceResponse:
        """Get current NBP exchange rate table A (mid-rates)."""
        return self.get_series("table_a")

    def get_exchange_rate(self, currency: str) -> DataSourceResponse:
        """Get PLN exchange rate for a specific currency.

        Args:
            currency: Currency code (EUR, USD, CHF, GBP)
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/exchangerates/rates/A/{currency.lower()}/?format=json",
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "NBP", "currency": currency.upper()},
            )
        except Exception as e:
            return handle_request_error(e, "NBP", "get_exchange_rate")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "NBP", "count": len(items)},
        )
