"""Intrinio financial data source.

Provides access to real-time and historical financial data including
stocks, options, forex, and fundamentals.

API Documentation: https://docs.intrinio.com/
Requires API key: https://intrinio.com/
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class IntrinioSource(EconomicDataSource):
    """Intrinio financial data source.

    Provides access to:
    - Stock prices and fundamentals
    - Options data
    - Forex rates
    - Economic data
    - Company financials
    - Real-time quotes

    Requires API key.
    """

    BASE_URL = "https://api-v2.intrinio.com"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Intrinio data source.

        Args:
            api_key: Intrinio API key (or set INTRINIO_API_KEY env var)
        """
        super().__init__(name="Intrinio", requires_api_key=True)
        self.api_key = api_key or os.getenv("INTRINIO_API_KEY")
        self.session = SessionManager.get_session("intrinio")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("Intrinio API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Intrinio API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set INTRINIO_API_KEY environment variable."
            )

        try:
            response = self.session.get(
                f"{self.BASE_URL}/companies",
                auth=(self.api_key, ""),
                params={"page_size": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Intrinio"},
                metadata={"source": "Intrinio", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Intrinio connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to Intrinio API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, auth=(self.api_key, ""), params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_company(self, identifier: str) -> DataSourceResponse:
        """Get company information.

        Args:
            identifier: Company ticker or CIK

        Returns:
            DataSourceResponse with company data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request(f"companies/{identifier}")
            return DataSourceResponse.success_response(
                data=data,
                metadata={"source": "Intrinio", "identifier": identifier}
            )
        except Exception as e:
            return handle_request_error(e, "Intrinio", "get_company")

    def get_stock_prices(
        self,
        identifier: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: str = "daily"
    ) -> DataSourceResponse:
        """Get historical stock prices.

        Args:
            identifier: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            frequency: Data frequency ('daily', 'weekly', 'monthly')

        Returns:
            DataSourceResponse with price data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"frequency": frequency}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            data = self._make_request(f"securities/{identifier}/prices", params=params)
            return DataSourceResponse.success_response(
                data=data.get("stock_prices", []),
                metadata={"source": "Intrinio", "identifier": identifier, "frequency": frequency}
            )
        except Exception as e:
            return handle_request_error(e, "Intrinio", "get_stock_prices")

    def get_fundamentals(
        self,
        identifier: str,
        statement_code: str = "income_statement",
        fiscal_year: Optional[int] = None
    ) -> DataSourceResponse:
        """Get company fundamentals.

        Args:
            identifier: Company ticker
            statement_code: Statement type ('income_statement', 'balance_sheet', 'cash_flow')
            fiscal_year: Fiscal year (optional)

        Returns:
            DataSourceResponse with fundamental data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"statement_code": statement_code}
            if fiscal_year:
                params["fiscal_year"] = fiscal_year

            data = self._make_request(f"companies/{identifier}/fundamentals", params=params)
            return DataSourceResponse.success_response(
                data=data.get("fundamentals", []),
                metadata={"source": "Intrinio", "identifier": identifier, "statement": statement_code}
            )
        except Exception as e:
            return handle_request_error(e, "Intrinio", "get_fundamentals")
