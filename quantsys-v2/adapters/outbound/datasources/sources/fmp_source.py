"""FMP (Financial Modeling Prep) data source.

Provides access to comprehensive financial data including stocks, forex, crypto, and more.

API Documentation: https://site.financialmodelingprep.com/developer/docs
Requires API key (free tier available).
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class FMPSource(EconomicDataSource):
    """Financial Modeling Prep data source.

    Provides access to:
    - Stock quotes and historical prices
    - Financial statements (income, balance sheet, cash flow)
    - Company profiles and key metrics
    - SEC filings
    - Insider trading
    - Institutional holdings
    - ETF holdings
    - Economic indicators
    - Forex and crypto data
    - Market news

    Requires API key (free tier: 250 requests/day).
    """

    BASE_URL = "https://financialmodelingprep.com/api/v3"
    V4_URL = "https://financialmodelingprep.com/api/v4"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize FMP data source.

        Args:
            api_key: FMP API key (or set FMP_API_KEY env var)
        """
        super().__init__(name="FMP", requires_api_key=True)
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        self.session = SessionManager.get_session("fmp")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("FMP API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to FMP API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set FMP_API_KEY environment variable."
            )

        try:
            response = self.session.get(
                f"{self.BASE_URL}/quote/AAPL",
                params={"apikey": self.api_key},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "FMP"},
                metadata={"source": "FMP", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"FMP connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, version: str = "v3") -> Any:
        """Make request to FMP API.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            version: API version ('v3' or 'v4')

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        base_url = self.V4_URL if version == "v4" else self.BASE_URL
        url = f"{base_url}/{endpoint}"
        request_params = {"apikey": self.api_key}
        if params:
            request_params.update(params)

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_quote(self, symbol: str) -> DataSourceResponse:
        """Get real-time quote for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            DataSourceResponse with quote data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request(f"quote/{symbol}")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_quote")

    def get_historical_prices(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get historical price data.

        Args:
            symbol: Stock symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with historical prices
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date

            data = self._make_request(f"historical-price-full/{symbol}", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol,
                    "from_date": from_date,
                    "to_date": to_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_historical_prices")

    def get_company_profile(self, symbol: str) -> DataSourceResponse:
        """Get company profile.

        Args:
            symbol: Stock symbol

        Returns:
            DataSourceResponse with company profile
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request(f"profile/{symbol}")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_company_profile")

    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5
    ) -> DataSourceResponse:
        """Get income statement.

        Args:
            symbol: Stock symbol
            period: 'annual' or 'quarter'
            limit: Number of periods

        Returns:
            DataSourceResponse with income statement
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"period": period, "limit": limit}
            data = self._make_request(f"income-statement/{symbol}", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol,
                    "period": period
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_income_statement")

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5
    ) -> DataSourceResponse:
        """Get balance sheet.

        Args:
            symbol: Stock symbol
            period: 'annual' or 'quarter'
            limit: Number of periods

        Returns:
            DataSourceResponse with balance sheet
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"period": period, "limit": limit}
            data = self._make_request(f"balance-sheet-statement/{symbol}", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol,
                    "period": period
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_balance_sheet")

    def get_cash_flow(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5
    ) -> DataSourceResponse:
        """Get cash flow statement.

        Args:
            symbol: Stock symbol
            period: 'annual' or 'quarter'
            limit: Number of periods

        Returns:
            DataSourceResponse with cash flow statement
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"period": period, "limit": limit}
            data = self._make_request(f"cash-flow-statement/{symbol}", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol,
                    "period": period
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_cash_flow")

    def get_key_metrics(self, symbol: str, period: str = "annual") -> DataSourceResponse:
        """Get key financial metrics.

        Args:
            symbol: Stock symbol
            period: 'annual' or 'quarter'

        Returns:
            DataSourceResponse with key metrics
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"period": period}
            data = self._make_request(f"key-metrics/{symbol}", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol,
                    "period": period
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_key_metrics")

    def get_insider_trading(self, symbol: str) -> DataSourceResponse:
        """Get insider trading data.

        Args:
            symbol: Stock symbol

        Returns:
            DataSourceResponse with insider trading data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request(f"insider-trading", params={"symbol": symbol}, version="v4")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_insider_trading")

    def get_institutional_holders(self, symbol: str) -> DataSourceResponse:
        """Get institutional holders.

        Args:
            symbol: Stock symbol

        Returns:
            DataSourceResponse with institutional holders
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request(f"institutional-holder/{symbol}")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "symbol": symbol
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_institutional_holders")

    def get_market_news(self, limit: int = 50) -> DataSourceResponse:
        """Get market news.

        Args:
            limit: Number of news items

        Returns:
            DataSourceResponse with news
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"limit": limit}
            data = self._make_request("stock_news", params=params, version="v4")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "limit": limit
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_market_news")

    def get_economic_calendar(self, from_date: str, to_date: str) -> DataSourceResponse:
        """Get economic calendar events.

        Args:
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with economic events
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"from": from_date, "to": to_date}
            data = self._make_request("economic_calendar", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "FMP",
                    "from_date": from_date,
                    "to_date": to_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "FMP", "get_economic_calendar")
