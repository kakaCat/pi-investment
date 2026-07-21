"""Frankfurter exchange rate data source.

Provides free foreign exchange reference rates from the European Central Bank.
No API key required. Open source (MIT).
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class FrankfurterSource(EconomicDataSource):
    """Frankfurter foreign exchange rate data source.

    ECB-based free currency exchange rate API. Provides current and historical
    rates for 30+ currencies. No API key required. Open source.

    Ideal for: portfolio currency exposure calculation, cross-border
    valuation, and FX risk management.
    """

    BASE_URL = "https://api.frankfurter.dev"

    CURRENCIES = {
        "EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "CNY", "HKD",
        "NZD", "SEK", "NOK", "DKK", "SGD", "KRW", "INR", "MXN", "BRL",
        "ZAR", "TRY", "RUB", "PLN", "CZK", "HUF", "ILS", "PHP", "IDR",
        "MYR", "THB", "RON", "BGN", "ISK", "HRK",
    }

    def __init__(self):
        super().__init__(name="Frankfurter", requires_api_key=False)
        self.session = SessionManager.get_session("frankfurter")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/latest?from=USD&to=EUR",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Frankfurter"},
                metadata={"source": "Frankfurter/ECB", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Frankfurter connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DataSourceResponse:
        """Get time series exchange rates.

        Args:
            series_id: Currency pair as 'FROM-TO' (e.g., 'USD-EUR')
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
        """
        try:
            parts = series_id.upper().split("-")
            base = parts[0] if len(parts) > 0 else "USD"
            target = parts[1] if len(parts) > 1 else "EUR"

            if start_date and end_date:
                url = f"{self.BASE_URL}/{start_date}..{end_date}"
            elif start_date:
                url = f"{self.BASE_URL}/{start_date}"
            else:
                url = f"{self.BASE_URL}/latest"

            response = self.session.get(
                url,
                params={"from": base, "to": target},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Frankfurter", "base": base, "target": target},
            )
        except Exception as e:
            return handle_request_error(e, "Frankfurter", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = sorted([
            c for c in self.CURRENCIES
            if query.upper() in c
        ])
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "Frankfurter", "query": query},
        )

    def get_latest_rates(self, base: str = "USD") -> DataSourceResponse:
        """Get latest exchange rates for all currencies from a base.

        Args:
            base: Base currency (default: USD)
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/latest",
                params={"from": base.upper()},
                timeout=15,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Frankfurter", "base": base.upper()},
            )
        except Exception as e:
            return handle_request_error(e, "Frankfurter", "get_latest_rates")

    def get_historical_rate(
        self, base: str, target: str, date: str
    ) -> DataSourceResponse:
        """Get exchange rate for a specific date.

        Args:
            base: Base currency (e.g., USD)
            target: Target currency (e.g., EUR)
            date: Date in YYYY-MM-DD format
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/{date}",
                params={"from": base.upper(), "to": target.upper()},
                timeout=15,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Frankfurter", "base": base, "target": target},
            )
        except Exception as e:
            return handle_request_error(e, "Frankfurter", "get_historical_rate")

    def get_currencies(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=sorted(self.CURRENCIES),
            metadata={"source": "Frankfurter", "count": len(self.CURRENCIES)},
        )
