"""EOD Historical Data (EODHD) market data source.

Provides access to global stock market data, fundamentals, and economic calendars.
API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EODHDSource(EconomicDataSource):
    """EOD Historical Data (EODHD) market data source.

    Provides end-of-day historical prices, real-time quotes, fundamentals
    (balance sheet, income, cash flow), insider transactions, economic
    events calendar, and macro indicators for 60+ global exchanges.

    API key required. Register at https://eodhd.com
    """

    BASE_URL = "https://eodhd.com/api"

    EXCHANGES = {
        "US": "NYSE, NASDAQ, AMEX",
        "LSE": "London Stock Exchange",
        "TSE": "Tokyo Stock Exchange",
        "HKEX": "Hong Kong Exchange",
        "SSE": "Shanghai Stock Exchange",
        "SZSE": "Shenzhen Stock Exchange",
        "XETRA": "Deutsche Börse XETRA",
        "EURONEXT": "Euronext (Paris, Amsterdam, Brussels, Lisbon)",
        "ASX": "Australian Securities Exchange",
        "TSX": "Toronto Stock Exchange",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="EODHD", requires_api_key=True)
        self.api_key = api_key or os.getenv("EODHD_API_KEY", "")
        self.session = SessionManager.get_session("eodhd")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("EODHD API key not configured. Register at https://eodhd.com")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/eod/AAPL.US",
                params={"api_token": self.api_key, "fmt": "json", "limit": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "EODHD"},
                metadata={"source": "EODHD", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"EODHD connection test failed: {e}")
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
            params: Dict[str, Any] = {
                "api_token": self.api_key,
                "fmt": "json",
            }
            if start_date:
                params["from"] = start_date
            if end_date:
                params["to"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/eod/{series_id}", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EODHD", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "EODHD", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/search/{query}",
                params={"api_token": self.api_key, "limit": limit},
                timeout=15,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EODHD", "query": query},
            )
        except Exception as e:
            return handle_request_error(e, "EODHD", "search_series")

    def get_fundamentals(self, symbol: str) -> DataSourceResponse:
        """Get company fundamentals (balance sheet, income, cash flow)."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/fundamentals/{symbol}",
                params={"api_token": self.api_key},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EODHD", "symbol": symbol},
            )
        except Exception as e:
            return handle_request_error(e, "EODHD", "get_fundamentals")

    def get_economic_calendar(self, date_from: str = None, date_to: str = None) -> DataSourceResponse:
        """Get economic events calendar."""
        try:
            params: Dict[str, Any] = {"api_token": self.api_key, "fmt": "json"}
            if date_from:
                params["from"] = date_from
            if date_to:
                params["to"] = date_to
            response = self.session.get(
                f"{self.BASE_URL}/economic-events", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EODHD"},
            )
        except Exception as e:
            return handle_request_error(e, "EODHD", "get_economic_calendar")

    def get_exchanges(self) -> DataSourceResponse:
        items = [{"code": k, "description": v} for k, v in self.EXCHANGES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "EODHD", "count": len(items)},
        )
