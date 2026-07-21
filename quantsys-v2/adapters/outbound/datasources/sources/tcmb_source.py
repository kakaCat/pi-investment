"""Türkiye Cumhuriyet Merkez Bankası (TCMB) central bank data source.

Provides access to Turkish monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class TCMBSource(EconomicDataSource):
    """Türkiye Cumhuriyet Merkez Bankası (Turkish Central Bank) data source.

    Provides policy rate (one-week repo), USD/TRY and EUR/TRY exchange rates,
    CPI inflation (headline and core), GDP growth, and international reserves.
    No API key required.
    """

    BASE_URL = "https://evds2.tcmb.gov.tr/service/evds"

    INDICATORS = {
        "policy_rate": "One-week repo rate (policy rate)",
        "overnight_lending": "Overnight lending rate",
        "overnight_borrowing": "Overnight borrowing rate",
        "cpi": "Consumer price index",
        "core_cpi": "Core CPI (special aggregates)",
        "gdp": "GDP growth",
        "usd_try": "USD/TRY exchange rate (buying)",
        "eur_try": "EUR/TRY exchange rate (buying)",
        "industrial_production": "Industrial production index",
        "reserves": "International reserves (gross)",
        "unemployment": "Unemployment rate",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="TCMB", requires_api_key=True)
        self.api_key = api_key or os.getenv("TCMB_API_KEY", "")
        self.session = SessionManager.get_session("tcmb")

    def validate_config(self) -> bool:
        if self.requires_api_key and not self.api_key:
            logger.warning("TCMB API key not configured. Register at https://evds2.tcmb.gov.tr")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/series=TP.DK.USD.A",
                params={"key": self.api_key, "type": "json"},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "TCMB_EVDS"},
                metadata={"source": "TCMB", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"TCMB connection test failed: {e}")
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
                "key": self.api_key,
                "type": "json",
            }
            if start_date:
                params["startDate"] = start_date
            if end_date:
                params["endDate"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/series={series_id}", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "TCMB", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "TCMB", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "TCMB", "query": query},
        )

    def get_exchange_rate(self, currency: str = "USD") -> DataSourceResponse:
        """Get TRY exchange rate against a given currency."""
        series_map = {
            "USD": "TP.DK.USD.A",
            "EUR": "TP.DK.EUR.A",
            "GBP": "TP.DK.GBP.A",
        }
        series_id = series_map.get(currency.upper(), series_map["USD"])
        return self.get_series(series_id)

    def get_inflation(self) -> DataSourceResponse:
        """Get Turkish CPI inflation data."""
        return self.get_series("TP.FG.J0")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "TCMB", "count": len(items)},
        )
