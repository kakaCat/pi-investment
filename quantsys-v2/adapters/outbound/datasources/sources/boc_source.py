"""Bank of Canada (BoC) central bank data source.

Provides access to Canadian monetary policy and financial system data.

No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BankOfCanadaSource(EconomicDataSource):
    """Bank of Canada (BoC) central bank data source.

    Provides access to:
    - Policy interest rate (overnight rate target)
    - Exchange rates (CAD vs major currencies)
    - Consumer Price Index and core inflation
    - Bond yields (Government of Canada benchmarks)
    - Money supply aggregates (M1+, M2, M2+, M3)
    - GDP and output gap estimates
    - Banking system data
    - Financial stability indicators

    No API key required.
    """

    BASE_URL = "https://www.bankofcanada.ca/valet"

    # Valet API series groups
    SERIES_GROUPS = {
        "overnight_rate": "V39079",           # Target overnight rate
        "bank_rate": "V39078",                # Bank rate
        "cpi": "V41690973",                   # Consumer Price Index
        "core_cpi": "V41690914",              # CPI excluding food/energy
        "gdp": "V65201216",                   # Real GDP
        "unemployment": "V2062815",           # Unemployment rate
        "usd_cad": "FXUSDCAD",                # USD/CAD exchange rate
        "eur_cad": "FXEURCAD",                # EUR/CAD exchange rate
        "cny_cad": "FXCNYCAD",                # CNY/CAD exchange rate
        "5yr_yield": "V39051",                # 5-year benchmark yield
        "10yr_yield": "V39053",               # 10-year benchmark yield
        "m1": "V37146",                       # M1+ money supply
        "m2": "V37151",                       # M2 money supply
        "wti_price": "V61300",                # WTI oil price (CAD)
        "housing_starts": "V107744",          # Housing starts
    }

    OBSERVATION_FREQUENCIES = ["daily", "weekly", "monthly", "quarterly", "annual"]

    def __init__(self):
        super().__init__(name="BankOfCanada", requires_api_key=False)
        self.session = SessionManager.get_session("boc")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/observations/V39079",
                params={"recent": 1},
                timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "BankOfCanada"},
                metadata={"source": "BankOfCanada", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"BoC connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, series_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/observations/{series_name}/json"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_series(
        self,
        series_name: str,
        recent: int = 100,
        frequency: Optional[str] = None
    ) -> DataSourceResponse:
        """Get data for a specific BoC series.

        Args:
            series_name: Series identifier (from SERIES_GROUPS or custom)
            recent: Number of recent observations
            frequency: Observation frequency filter

        Returns:
            DataSourceResponse with series data
        """
        try:
            params: Dict[str, Any] = {"recent": recent}
            if frequency:
                if frequency not in self.OBSERVATION_FREQUENCIES:
                    return DataSourceResponse.error_response(
                        error=f"Invalid frequency: {frequency}. Valid: {self.OBSERVATION_FREQUENCIES}"
                    )
                params["frequency"] = frequency

            data = self._make_request(series_name, params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "BankOfCanada",
                    "series": series_name,
                    "recent": recent
                }
            )
        except Exception as e:
            return handle_request_error(e, "BankOfCanada", "get_series")

    def get_overnight_rate(
        self,
        recent: int = 50
    ) -> DataSourceResponse:
        """Get target overnight rate (BoC policy rate).

        Args:
            recent: Number of recent observations

        Returns:
            DataSourceResponse with overnight rate history
        """
        return self.get_series("V39079", recent=recent, frequency="daily")

    def get_exchange_rates(
        self,
        base_currency: str = "USD"
    ) -> DataSourceResponse:
        """Get CAD exchange rates against major currencies.

        Args:
            base_currency: Base currency (default: USD)

        Returns:
            DataSourceResponse with exchange rate data
        """
        try:
            fx_series = f"FX{base_currency}CAD"
            data = self._make_request(fx_series, {"recent": 100})

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "BankOfCanada",
                    "base_currency": base_currency,
                    "quote_currency": "CAD"
                }
            )
        except Exception as e:
            return handle_request_error(e, "BankOfCanada", "get_exchange_rates")

    def get_cpi(
        self,
        recent: int = 60
    ) -> DataSourceResponse:
        """Get Canadian CPI data.

        Args:
            recent: Number of monthly observations

        Returns:
            DataSourceResponse with CPI data
        """
        return self.get_series("V41690973", recent=recent, frequency="monthly")

    def get_bond_yields(
        self,
        tenor: str = "10yr"
    ) -> DataSourceResponse:
        """Get Government of Canada benchmark bond yields.

        Args:
            tenor: Bond tenor ('5yr' or '10yr')

        Returns:
            DataSourceResponse with bond yield data
        """
        series_map = {"5yr": "V39051", "10yr": "V39053"}
        series_name = series_map.get(tenor, "V39053")
        return self.get_series(series_name, recent=100, frequency="daily")

    def get_money_supply(
        self,
        aggregate: str = "M2"
    ) -> DataSourceResponse:
        """Get Canadian money supply aggregates.

        Args:
            aggregate: Money supply measure ('M1', 'M2')

        Returns:
            DataSourceResponse with money supply data
        """
        series_map = {"M1": "V37146", "M2": "V37151"}
        series_name = series_map.get(aggregate, "V37151")
        return self.get_series(series_name, recent=60, frequency="monthly")

    def get_series_groups(self) -> DataSourceResponse:
        """Get available series groups.

        Returns:
            DataSourceResponse with series group mappings
        """
        groups = [
            {"name": name, "series": code}
            for name, code in self.SERIES_GROUPS.items()
        ]
        return DataSourceResponse.success_response(
            data=groups,
            metadata={"source": "BankOfCanada", "count": len(groups)}
        )

    def get_gdp(self, recent: int = 40) -> DataSourceResponse:
        """Get Canadian GDP data.

        Args:
            recent: Number of quarterly observations

        Returns:
            DataSourceResponse with GDP data
        """
        return self.get_series("V65201216", recent=recent, frequency="quarterly")
