"""Czech National Bank (CNB) central bank data source.

Provides access to Czech monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CNBSource(EconomicDataSource):
    """Czech National Bank (CNB) central bank data source.

    Provides CNB 2-week repo rate (policy rate), CZK exchange rates,
    CPI inflation, GDP, money supply, and financial stability indicators.
    No API key required.
    """

    BASE_URL = "https://www.cnb.cz/en/financial-markets"

    INDICATORS = {
        "policy_rate": "2W repo rate (CNB policy rate)",
        "discount_rate": "Discount rate",
        "lombard_rate": "Lombard rate",
        "cpi": "Consumer price index",
        "gdp": "GDP growth rate",
        "eur_czk": "EUR/CZK exchange rate",
        "usd_czk": "USD/CZK exchange rate",
        "money_supply_m2": "M2 money supply",
        "unemployment": "Unemployment rate",
    }

    def __init__(self):
        super().__init__(name="CNB", requires_api_key=False)
        self.session = SessionManager.get_session("cnb")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/foreign-exchange-market/central-bank-exchange-rate-fixing/daily.txt",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "CNB"},
                metadata={"source": "CNB", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"CNB connection test failed: {e}")
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
                f"{self.BASE_URL}/api/{series_id}", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "CNB", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "CNB", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "CNB", "query": query},
        )

    def get_exchange_rate(self, currency: str = "EUR") -> DataSourceResponse:
        """Get CZK exchange rate. Most commonly EUR/CZK."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/foreign-exchange-market/central-bank-exchange-rate-fixing/daily.txt",
                timeout=30,
            )
            response.raise_for_status()
            lines = response.text.strip().split("\n")
            rates = []
            for line in lines[2:]:
                parts = line.split("|")
                if len(parts) >= 5:
                    rates.append({
                        "country": parts[0].strip(),
                        "currency": parts[1].strip(),
                        "amount": int(parts[2].strip()),
                        "code": parts[3].strip(),
                        "rate": float(parts[4].strip()),
                    })
            return DataSourceResponse.success_response(
                data=rates,
                metadata={"source": "CNB", "date": lines[0] if lines else ""},
            )
        except Exception as e:
            return handle_request_error(e, "CNB", "get_exchange_rate")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "CNB", "count": len(items)},
        )
