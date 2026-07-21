"""Norges Bank (Norway's central bank) data source.

Provides access to Norwegian monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class NorgesBankSource(EconomicDataSource):
    """Norges Bank (Norwegian central bank) data source.

    Provides key policy rate (styringsrente), NOK exchange rates vs EUR/USD/GBP,
    CPI and core inflation, GDP mainland Norway, oil price in NOK, and
    sovereign wealth fund (GPFG) market value.
    No API key required.
    """

    BASE_URL = "https://data.norges-bank.no/api"

    INDICATORS = {
        "policy_rate": "Key policy rate (styringsrente)",
        "cpi": "Consumer price index",
        "cpi_ate": "CPI-ATE (core inflation, excl. energy/taxes)",
        "gdp_mainland": "GDP mainland Norway",
        "eur_nok": "EUR/NOK exchange rate",
        "usd_nok": "USD/NOK exchange rate",
        "gbp_nok": "GBP/NOK exchange rate",
        "oil_price_nok": "Brent crude in NOK",
        "unemployment": "Unemployment rate (LFS)",
        "gpfg_market_value": "Govt Pension Fund Global market value",
    }

    def __init__(self):
        super().__init__(name="NorgesBank", requires_api_key=False)
        self.session = SessionManager.get_session("norges")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/data/EXCHANGE/EXR.PS.EUR.NOK.SP",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "NorgesBank"},
                metadata={"source": "NorgesBank", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Norges Bank connection test failed: {e}")
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
            params: Dict[str, Any] = {"format": "json"}
            if start_date:
                params["startPeriod"] = start_date
            if end_date:
                params["endPeriod"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/data/{series_id}", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "NorgesBank", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "NorgesBank", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "NorgesBank", "query": query},
        )

    def get_exchange_rate(self, currency: str = "EUR") -> DataSourceResponse:
        """Get NOK exchange rate against a given currency.

        Args:
            currency: Currency code (EUR, USD, GBP)
        """
        series_map = {
            "EUR": "EXR.PS.EUR.NOK.SP",
            "USD": "EXR.PS.USD.NOK.SP",
            "GBP": "EXR.PS.GBP.NOK.SP",
            "SEK": "EXR.PS.SEK.NOK.SP",
            "DKK": "EXR.PS.DKK.NOK.SP",
        }
        series_id = series_map.get(currency.upper(), series_map["EUR"])
        return self.get_series(series_id)

    def get_policy_rate(self) -> DataSourceResponse:
        """Get Norges Bank key policy rate."""
        return self.get_series("IR.KPRA")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "NorgesBank", "count": len(items)},
        )
