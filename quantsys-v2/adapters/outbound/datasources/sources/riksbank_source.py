"""Sveriges Riksbank (Swedish central bank) data source.

Provides access to Swedish monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class RiksbankSource(EconomicDataSource):
    """Sveriges Riksbank (Swedish central bank) data source.

    Provides policy rate (styrränta), SEK exchange rates vs EUR/USD/GBP,
    CPI and CPIF inflation, GDP growth, and housing price indicators.
    No API key required.
    """

    BASE_URL = "https://api.riksbank.se"

    INDICATORS = {
        "policy_rate": "Policy rate (styrränta)",
        "cpi": "Consumer price index (CPI)",
        "cpif": "CPI with fixed interest rate (CPIF, Riksbank target)",
        "gdp": "GDP growth",
        "eur_sek": "EUR/SEK exchange rate",
        "usd_sek": "USD/SEK exchange rate",
        "gbp_sek": "GBP/SEK exchange rate",
        "unemployment": "Unemployment rate",
        "housing_prices": "Housing price index",
        "repo_rate_path": "Projected repo rate path",
    }

    def __init__(self):
        super().__init__(name="Riksbank", requires_api_key=False)
        self.session = SessionManager.get_session("riksbank")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/swea/v1/CalendarDays/2024-01-01",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Riksbank"},
                metadata={"source": "Riksbank", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Riksbank connection test failed: {e}")
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
                params["from"] = start_date
            if end_date:
                params["to"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/swea/v1/{series_id}", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Riksbank", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "Riksbank", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "Riksbank", "query": query},
        )

    def get_exchange_rate(self, currency: str = "EUR") -> DataSourceResponse:
        """Get SEK exchange rate against a given currency."""
        series_map = {
            "EUR": "SEKEURPMI",
            "USD": "SEKUSDPMI",
            "GBP": "SEKGBPPMI",
            "NOK": "SEKNOKPMI",
            "DKK": "SEKDKKPMI",
        }
        series_id = series_map.get(currency.upper(), series_map["EUR"])
        return self.get_series(series_id)

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "Riksbank", "count": len(items)},
        )
