"""BIS (Bank for International Settlements) Source.

Provides access to BIS statistics including:
- Credit statistics
- Debt securities statistics
- Derivatives statistics
- Exchange rates
- Property prices

Inspired by FinceptTerminal's bis_data.py implementation.
No API key required - public BIS API.
"""

from typing import Optional, List, Dict, Any

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager


class BISSource(EconomicDataSource):
    """BIS (Bank for International Settlements) data source.

    No API key required - uses public BIS Statistics API.
    """

    BASE_URL = "https://stats.bis.org/api/v1"

    def __init__(self):
        super().__init__(name="BIS", requires_api_key=False)
        self.session = SessionManager.get_session("bis")

        # Dataset codes
        self.datasets = {
            "credit": "TOTAL_CREDIT",
            "debt_securities": "DEBT_SEC2",
            "derivatives": "DERIV",
            "exchange_rates": "WS_XRU",
            "property_prices": "WS_PP",
            "cbs": "WS_CBS",  # Consolidated banking statistics
            "lbs": "WS_LBS",  # Locational banking statistics
        }

    def validate_config(self) -> bool:
        """Validate BIS configuration (no API key needed)."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test BIS API connection."""
        try:
            # Test with dataflow list
            url = f"{self.BASE_URL}/dataflow"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            return DataSourceResponse.success_response(
                {"status": "connected", "test": "passed"},
                metadata={"source": "bis"}
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
        # Default to credit statistics
        return self.get_credit_statistics(
            countries=None,
            frequency="Q",
            start_date=start_date,
            end_date=end_date
        )

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for available series."""
        return self.list_datasets()

    def get_credit_statistics(
        self,
        countries: Optional[str] = None,
        frequency: str = "Q",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get credit statistics.

        Args:
            countries: Comma-separated country codes (e.g., "US,GB,JP")
            frequency: "Q" (quarterly), "M" (monthly), or "A" (annual)
            start_date: Start date YYYY-MM (optional)
            end_date: End date YYYY-MM (optional)

        Returns:
            DataSourceResponse with credit statistics
        """
        self._log_request("get_credit_statistics", {
            "countries": countries,
            "frequency": frequency
        })

        try:
            dataset = self.datasets["credit"]
            url = f"{self.BASE_URL}/data/{dataset}"

            params = {"format": "json"}
            if countries:
                params["c1"] = countries.replace(",", "+")
            if frequency:
                params["freq"] = frequency
            if start_date:
                params["startPeriod"] = start_date
            if end_date:
                params["endPeriod"] = end_date

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            parsed_data = self._parse_bis_response(data)

            return DataSourceResponse.success_response(
                parsed_data,
                metadata={"dataset": "credit", "countries": countries}
            )

        except Exception as e:
            return self._handle_error("get_credit_statistics", e)

    def get_exchange_rates(
        self,
        currencies: Optional[str] = None,
        frequency: str = "D",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get exchange rates.

        Args:
            currencies: Comma-separated currency codes (e.g., "USD,EUR,JPY")
            frequency: "D" (daily), "M" (monthly)
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)

        Returns:
            DataSourceResponse with exchange rate data
        """
        self._log_request("get_exchange_rates", {"currencies": currencies})

        try:
            dataset = self.datasets["exchange_rates"]
            url = f"{self.BASE_URL}/data/{dataset}"

            params = {"format": "json"}
            if currencies:
                params["c1"] = currencies.replace(",", "+")
            if frequency:
                params["freq"] = frequency
            if start_date:
                params["startPeriod"] = start_date
            if end_date:
                params["endPeriod"] = end_date

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            parsed_data = self._parse_bis_response(data)

            return DataSourceResponse.success_response(
                parsed_data,
                metadata={"dataset": "exchange_rates", "currencies": currencies}
            )

        except Exception as e:
            return self._handle_error("get_exchange_rates", e)

    def get_property_prices(
        self,
        countries: Optional[str] = None,
        frequency: str = "Q",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get property price statistics.

        Args:
            countries: Comma-separated country codes
            frequency: "Q" (quarterly), "A" (annual)
            start_date: Start date YYYY-MM (optional)
            end_date: End date YYYY-MM (optional)

        Returns:
            DataSourceResponse with property price data
        """
        self._log_request("get_property_prices", {"countries": countries})

        try:
            dataset = self.datasets["property_prices"]
            url = f"{self.BASE_URL}/data/{dataset}"

            params = {"format": "json"}
            if countries:
                params["c1"] = countries.replace(",", "+")
            if frequency:
                params["freq"] = frequency
            if start_date:
                params["startPeriod"] = start_date
            if end_date:
                params["endPeriod"] = end_date

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            parsed_data = self._parse_bis_response(data)

            return DataSourceResponse.success_response(
                parsed_data,
                metadata={"dataset": "property_prices", "countries": countries}
            )

        except Exception as e:
            return self._handle_error("get_property_prices", e)

    def list_datasets(self) -> DataSourceResponse:
        """List available BIS datasets.

        Returns:
            DataSourceResponse with available datasets
        """
        self._log_request("list_datasets", {})

        try:
            url = f"{self.BASE_URL}/dataflow"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            datasets = []
            if "dataflows" in data:
                for df in data["dataflows"]:
                    datasets.append({
                        "id": df.get("id", ""),
                        "name": df.get("name", ""),
                        "description": df.get("description", "")
                    })

            return DataSourceResponse.success_response(
                datasets,
                metadata={"total": len(datasets)}
            )

        except Exception as e:
            return self._handle_error("list_datasets", e)

    # Helper methods

    def _parse_bis_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse BIS API response."""
        parsed = []

        try:
            if "dataSets" in data and len(data["dataSets"]) > 0:
                dataset = data["dataSets"][0]
                if "series" in dataset:
                    for series_key, series_data in dataset["series"].items():
                        if "observations" in series_data:
                            for obs_key, obs_value in series_data["observations"].items():
                                parsed.append({
                                    "series": series_key,
                                    "period": obs_key,
                                    "value": obs_value[0] if isinstance(obs_value, list) else obs_value
                                })
        except Exception as e:
            self.logger.warning(f"Failed to parse BIS response: {e}")

        return parsed
