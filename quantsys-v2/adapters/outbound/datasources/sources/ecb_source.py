"""ECB (European Central Bank) Source.

Provides access to ECB statistical data including:
- Exchange rates
- Interest rates
- Monetary aggregates
- Balance of payments
- Government finance statistics

Inspired by FinceptTerminal's ecb_data.py implementation.
No API key required - public ECB SDMX API.
"""

from typing import Optional, List, Dict, Any

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager


class ECBSource(EconomicDataSource):
    """ECB (European Central Bank) data source.

    No API key required - uses public ECB SDMX 2.1 API.
    """

    BASE_URL = "https://data-api.ecb.europa.eu/service/data"

    def __init__(self):
        super().__init__(name="ECB", requires_api_key=False)
        self.session = SessionManager.get_session("ecb")

        # Dataset codes
        self.datasets = {
            "exchange_rates": "EXR",
            "interest_rates": "FM",
            "monetary_aggregates": "BSI",
            "balance_of_payments": "BOP",
            "government_finance": "GFS",
        }

    def validate_config(self) -> bool:
        """Validate ECB configuration (no API key needed)."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test ECB API connection."""
        try:
            # Test with EUR/USD exchange rate
            result = self.get_exchange_rates(currencies="USD", frequency="D")
            if not result.success:
                return DataSourceResponse.error_response(result.error)

            return DataSourceResponse.success_response(
                {"status": "connected", "test": "passed"},
                metadata={"source": "ecb"}
            )
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get time series data (generic interface)."""
        # Default to exchange rates
        return self.get_exchange_rates(
            currencies=series_id if series_id else "USD",
            frequency="D",
            start_date=start_date,
            end_date=end_date
        )

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for available series."""
        datasets = [
            {"id": "EXR", "name": "Exchange Rates", "description": "EUR exchange rates"},
            {"id": "FM", "name": "Interest Rates", "description": "ECB interest rates"},
            {"id": "BSI", "name": "Monetary Aggregates", "description": "Money supply data"},
        ]

        if query:
            query_lower = query.lower()
            datasets = [d for d in datasets if query_lower in d["name"].lower()]

        return DataSourceResponse.success_response(datasets[:limit])

    def get_exchange_rates(
        self,
        currencies: Optional[str] = None,
        frequency: str = "D",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get ECB exchange rates (EUR as base).

        Args:
            currencies: Comma-separated currency codes (e.g., "USD,GBP,JPY")
            frequency: "D" (daily), "M" (monthly)
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)

        Returns:
            DataSourceResponse with exchange rate data
        """
        self._log_request("get_exchange_rates", {
            "currencies": currencies,
            "frequency": frequency
        })

        try:
            if not currencies:
                currencies = "USD"

            # Build dataflow key
            currency_list = currencies.split(",")
            currency_param = "+".join([c.strip() for c in currency_list])

            dataset = self.datasets["exchange_rates"]
            url = f"{self.BASE_URL}/{dataset}/{frequency}.{currency_param}.EUR.SP00.A"

            params = {"format": "csvdata"}
            if start_date:
                params["startPeriod"] = start_date
            if end_date:
                params["endPeriod"] = end_date

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = self._parse_csv_response(response.text)

            return DataSourceResponse.success_response(
                data,
                metadata={"currencies": currencies, "frequency": frequency}
            )

        except Exception as e:
            return self._handle_error("get_exchange_rates", e)

    def get_interest_rates(
        self,
        rate_type: str = "deposit",
        frequency: str = "D",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get ECB interest rates.

        Args:
            rate_type: "deposit", "lending", "marginal"
            frequency: "D" (daily), "M" (monthly)
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)

        Returns:
            DataSourceResponse with interest rate data
        """
        self._log_request("get_interest_rates", {"rate_type": rate_type})

        try:
            dataset = self.datasets["interest_rates"]
            url = f"{self.BASE_URL}/{dataset}"

            params = {"format": "csvdata"}
            if start_date:
                params["startPeriod"] = start_date
            if end_date:
                params["endPeriod"] = end_date

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = self._parse_csv_response(response.text)

            return DataSourceResponse.success_response(
                data,
                metadata={"rate_type": rate_type, "frequency": frequency}
            )

        except Exception as e:
            return self._handle_error("get_interest_rates", e)

    # Helper methods

    def _parse_csv_response(self, text: str) -> List[Dict[str, Any]]:
        """Parse CSV response from ECB API."""
        try:
            import csv
            from io import StringIO

            lines = text.strip().split('\n')
            if not lines:
                return []

            reader = csv.DictReader(StringIO(text))
            data = []
            for row in reader:
                data.append(dict(row))

            return data
        except Exception as e:
            self.logger.warning(f"Failed to parse CSV: {e}")
            return []
