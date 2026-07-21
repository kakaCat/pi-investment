"""RBA (Reserve Bank of Australia) data source.

Provides access to Australian economic and financial statistics including
interest rates, exchange rates, inflation, and monetary policy data.

API Documentation: https://www.rba.gov.au/statistics/
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class RBASource(EconomicDataSource):
    """Reserve Bank of Australia data source.

    Provides access to:
    - Interest rates (cash rate, bond yields)
    - Exchange rates (AUD pairs)
    - Inflation data (CPI)
    - Money and credit aggregates
    - Financial aggregates
    - Payment systems data

    No API key required.
    """

    BASE_URL = "https://www.rba.gov.au/statistics"

    # Common series IDs
    SERIES = {
        "cash_rate": "FIRMMCRT",
        "aud_usd": "FXRUSD",
        "aud_eur": "FXREUR",
        "aud_jpy": "FXRJPY",
        "aud_gbp": "FXRGBP",
        "aud_cny": "FXRCNY",
        "cpi": "GCPIAG",
        "unemployment": "GLFSURSA",
        "gdp": "GGDPCVGDP",
    }

    def __init__(self):
        """Initialize RBA data source."""
        super().__init__(name="RBA", requires_api_key=False)
        self.session = SessionManager.get_session("rba")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to RBA API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            # Test with cash rate series
            response = self.session.get(
                f"{self.BASE_URL}/tables/json/f1-data.json",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "RBA"},
                metadata={"source": "RBA", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"RBA connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, table: str) -> Dict[str, Any]:
        """Make request to RBA API.

        Args:
            table: Table identifier (e.g., 'f1-data' for interest rates)

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/tables/json/{table}.json"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_cash_rate(self) -> DataSourceResponse:
        """Get RBA cash rate (official interest rate).

        Returns:
            DataSourceResponse with cash rate data
        """
        try:
            data = self._make_request("f1-data")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "RBA",
                    "series": "cash_rate",
                    "description": "Official cash rate target"
                }
            )
        except Exception as e:
            return handle_request_error(e, "RBA", "get_cash_rate")

    def get_exchange_rates(self) -> DataSourceResponse:
        """Get AUD exchange rates.

        Returns:
            DataSourceResponse with exchange rate data
        """
        try:
            data = self._make_request("f11-data")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "RBA",
                    "series": "exchange_rates",
                    "description": "AUD exchange rates"
                }
            )
        except Exception as e:
            return handle_request_error(e, "RBA", "get_exchange_rates")

    def get_inflation(self) -> DataSourceResponse:
        """Get inflation data (CPI).

        Returns:
            DataSourceResponse with inflation data
        """
        try:
            data = self._make_request("g1-data")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "RBA",
                    "series": "inflation",
                    "description": "Consumer Price Index"
                }
            )
        except Exception as e:
            return handle_request_error(e, "RBA", "get_inflation")

    def get_money_aggregates(self) -> DataSourceResponse:
        """Get money and credit aggregates.

        Returns:
            DataSourceResponse with money aggregates data
        """
        try:
            data = self._make_request("d3-data")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "RBA",
                    "series": "money_aggregates",
                    "description": "Money and credit aggregates"
                }
            )
        except Exception as e:
            return handle_request_error(e, "RBA", "get_money_aggregates")

    def get_bond_yields(self) -> DataSourceResponse:
        """Get Australian government bond yields.

        Returns:
            DataSourceResponse with bond yield data
        """
        try:
            data = self._make_request("f2-data")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "RBA",
                    "series": "bond_yields",
                    "description": "Government bond yields"
                }
            )
        except Exception as e:
            return handle_request_error(e, "RBA", "get_bond_yields")

    def get_commodity_prices(self) -> DataSourceResponse:
        """Get commodity price indices.

        Returns:
            DataSourceResponse with commodity price data
        """
        try:
            data = self._make_request("g5-data")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "RBA",
                    "series": "commodity_prices",
                    "description": "Commodity price indices"
                }
            )
        except Exception as e:
            return handle_request_error(e, "RBA", "get_commodity_prices")

    def get_financial_aggregates(self) -> DataSourceResponse:
        """Get financial aggregates (lending, deposits).

        Returns:
            DataSourceResponse with financial aggregates data
        """
        try:
            data = self._make_request("d1-data")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "RBA",
                    "series": "financial_aggregates",
                    "description": "Financial aggregates"
                }
            )
        except Exception as e:
            return handle_request_error(e, "RBA", "get_financial_aggregates")
