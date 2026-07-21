"""BOJ (Bank of Japan) Source.

Provides access to Bank of Japan statistics including:
- Exchange rates
- Interest rates
- Money stock
- Price indexes
- Balance of payments

Inspired by FinceptTerminal's boj_fetcher.py implementation.
No API key required - public BOJ API.
"""

from typing import Optional, List, Dict, Any

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager


class BOJSource(EconomicDataSource):
    """BOJ (Bank of Japan) data source.

    No API key required - uses public BOJ Time-Series Data Search API.
    """

    BASE_URL = "https://www.stat-search.boj.or.jp/ssi/cgi-bin/famecgi2"

    def __init__(self):
        super().__init__(name="BOJ", requires_api_key=False)
        self.session = SessionManager.get_session("boj")

        # Common series codes
        self.series_codes = {
            "exchange_rate_usd": "FXDUS01",
            "exchange_rate_eur": "FXDEU01",
            "policy_rate": "IRSTBP01",
            "money_stock_m2": "MABM2_M",
            "cpi": "PRCPIY_M",
        }

    def validate_config(self) -> bool:
        """Validate BOJ configuration (no API key needed)."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test BOJ API connection."""
        try:
            # Test with USD exchange rate
            result = self.get_exchange_rate(currency="USD")
            if not result.success:
                return DataSourceResponse.error_response(result.error)

            return DataSourceResponse.success_response(
                {"status": "connected", "test": "passed"},
                metadata={"source": "boj"}
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
        # Check if it's a known series code
        if series_id in self.series_codes.values():
            # It's already a BOJ series code
            pass
        elif series_id.upper() in ["USD", "EUR"]:
            return self.get_exchange_rate(series_id, start_date, end_date)

        # Default to USD exchange rate
        return self.get_exchange_rate("USD", start_date, end_date)

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for available series."""
        series = [
            {"id": "FXDUS01", "name": "USD/JPY Exchange Rate", "description": "US Dollar to Japanese Yen"},
            {"id": "FXDEU01", "name": "EUR/JPY Exchange Rate", "description": "Euro to Japanese Yen"},
            {"id": "IRSTBP01", "name": "Policy Rate", "description": "BOJ policy interest rate"},
            {"id": "MABM2_M", "name": "Money Stock M2", "description": "M2 money supply"},
            {"id": "PRCPIY_M", "name": "CPI", "description": "Consumer Price Index"},
        ]

        if query:
            query_lower = query.lower()
            series = [s for s in series if query_lower in s["name"].lower() or query_lower in s["description"].lower()]

        return DataSourceResponse.success_response(series[:limit])

    def get_exchange_rate(
        self,
        currency: str = "USD",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get BOJ exchange rates (JPY as base).

        Args:
            currency: Currency code (e.g., "USD", "EUR")
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)

        Returns:
            DataSourceResponse with exchange rate data
        """
        self._log_request("get_exchange_rate", {"currency": currency})

        try:
            # Get series code
            series_key = f"exchange_rate_{currency.lower()}"
            series_code = self.series_codes.get(series_key, "FXDUS01")

            params = {
                "LANG": "EN",
                "STAT_CODE": series_code,
                "OUT_FORMAT": "CSV"
            }

            if start_date:
                params["START_DATE"] = start_date.replace("-", "")
            if end_date:
                params["END_DATE"] = end_date.replace("-", "")

            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            data = self._parse_csv_response(response.text)

            return DataSourceResponse.success_response(
                data,
                metadata={"currency": currency, "series_code": series_code}
            )

        except Exception as e:
            return self._handle_error("get_exchange_rate", e)

    def get_policy_rate(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get BOJ policy interest rate.

        Args:
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)

        Returns:
            DataSourceResponse with policy rate data
        """
        self._log_request("get_policy_rate", {})

        try:
            series_code = self.series_codes["policy_rate"]

            params = {
                "LANG": "EN",
                "STAT_CODE": series_code,
                "OUT_FORMAT": "CSV"
            }

            if start_date:
                params["START_DATE"] = start_date.replace("-", "")
            if end_date:
                params["END_DATE"] = end_date.replace("-", "")

            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            data = self._parse_csv_response(response.text)

            return DataSourceResponse.success_response(
                data,
                metadata={"series_code": series_code}
            )

        except Exception as e:
            return self._handle_error("get_policy_rate", e)

    def get_money_stock(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get BOJ money stock (M2).

        Args:
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)

        Returns:
            DataSourceResponse with money stock data
        """
        self._log_request("get_money_stock", {})

        try:
            series_code = self.series_codes["money_stock_m2"]

            params = {
                "LANG": "EN",
                "STAT_CODE": series_code,
                "OUT_FORMAT": "CSV"
            }

            if start_date:
                params["START_DATE"] = start_date.replace("-", "")
            if end_date:
                params["END_DATE"] = end_date.replace("-", "")

            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            data = self._parse_csv_response(response.text)

            return DataSourceResponse.success_response(
                data,
                metadata={"series_code": series_code}
            )

        except Exception as e:
            return self._handle_error("get_money_stock", e)

    # Helper methods

    def _parse_csv_response(self, text: str) -> List[Dict[str, Any]]:
        """Parse CSV response from BOJ API."""
        try:
            import csv
            from io import StringIO

            lines = text.strip().split('\n')
            if not lines:
                return []

            # Skip header lines (BOJ CSV has metadata at top)
            data_start = 0
            for i, line in enumerate(lines):
                if line.startswith("Time"):
                    data_start = i
                    break

            if data_start > 0:
                lines = lines[data_start:]

            reader = csv.DictReader(StringIO('\n'.join(lines)))
            data = []
            for row in reader:
                data.append(dict(row))

            return data
        except Exception as e:
            self.logger.warning(f"Failed to parse CSV: {e}")
            return []
