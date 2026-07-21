"""Swiss National Bank (SNB) central bank data source.

Provides access to Swiss monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class SNBSource(EconomicDataSource):
    """Swiss National Bank (SNB) central bank data source.

    Provides SNB policy rate, CHF exchange rates (EUR/CHF, USD/CHF, GBP/CHF),
    CPI inflation, GDP growth, sight deposits (liquidity indicator), and SNB
    foreign exchange reserves.
    No API key required.
    """

    BASE_URL = "https://data.snb.ch/api"

    INDICATORS = {
        "policy_rate": "SNB policy rate (Leitzins)",
        "sight_deposits": "Sight deposits (liquidity measure)",
        "cpi": "Consumer price index",
        "gdp": "GDP growth rate",
        "eur_chf": "EUR/CHF exchange rate",
        "usd_chf": "USD/CHF exchange rate",
        "gbp_chf": "GBP/CHF exchange rate",
        "fx_reserves": "Foreign exchange reserves",
        "mortgage_rate": "Mortgage benchmark rate",
        "m3_money_supply": "M3 money supply",
    }

    def __init__(self):
        super().__init__(name="SNB", requires_api_key=False)
        self.session = SessionManager.get_session("snb")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/cube/zimoma/data/json/en",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "SNB"},
                metadata={"source": "SNB", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"SNB connection test failed: {e}")
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
                f"{self.BASE_URL}/cube/{series_id}/data/json/en",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "SNB", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "SNB", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "SNB", "query": query},
        )

    def get_exchange_rate(self, currency: str = "EUR") -> DataSourceResponse:
        """Get CHF exchange rate against a given currency."""
        return self.get_series(f"rendblo-{currency.lower()}chf")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "SNB", "count": len(items)},
        )
