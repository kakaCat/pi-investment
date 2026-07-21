"""SimFin financial data source.

Provides access to standardized fundamental financial data for global stocks.
API key required (free tier available).
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class SimFinSource(EconomicDataSource):
    """SimFin standardized fundamental financial data source.

    Provides income statements, balance sheets, cash flow statements, and
    derived ratios for 7,000+ US stocks and global ADRs. All financials are
    standardized to a common chart of accounts for cross-company comparison.

    API key required. Free tier available at https://simfin.com
    """

    BASE_URL = "https://backend.simfin.com/api/v3"

    STATEMENTS = {
        "income": "Income Statement",
        "balance": "Balance Sheet",
        "cashflow": "Cash Flow Statement",
        "derived": "Derived ratios and margins",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="SimFin", requires_api_key=True)
        self.api_key = api_key or os.getenv("SIMFIN_API_KEY", "")
        self.session = SessionManager.get_session("simfin")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("SimFin API key not configured. Register at https://simfin.com")
            return False
        if len(self.api_key) < 10:
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/companies/compact",
                headers={"Authorization": self.api_key},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "SimFin"},
                metadata={"source": "SimFin", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"SimFin connection test failed: {e}")
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
            params: Dict[str, Any] = {"ticker": series_id}
            if start_date:
                params["start"] = start_date
            if end_date:
                params["end"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/companies/statements/compact",
                headers={"Authorization": self.api_key},
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "SimFin", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "SimFin", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/companies/compact",
                headers={"Authorization": self.api_key},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            matches = [
                {"ticker": c.get("ticker"), "name": c.get("name")}
                for c in data
                if query.lower() in c.get("ticker", "").lower()
                or query.lower() in c.get("name", "").lower()
            ]
            return DataSourceResponse.success_response(
                data=matches[:limit],
                metadata={"source": "SimFin", "query": query},
            )
        except Exception as e:
            return handle_request_error(e, "SimFin", "search_series")

    def get_financials(
        self,
        ticker: str,
        statement: str = "income",
        periods: int = 8,
    ) -> DataSourceResponse:
        """Get standardized financial statements for a ticker.

        Args:
            ticker: Stock ticker symbol
            statement: 'income', 'balance', 'cashflow', or 'derived'
            periods: Number of fiscal periods (default 8 quarters)
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/companies/statements/compact",
                headers={"Authorization": self.api_key},
                params={"ticker": ticker, "statements": statement, "periods": periods},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "SimFin", "ticker": ticker, "statement": statement},
            )
        except Exception as e:
            return handle_request_error(e, "SimFin", "get_financials")

    def get_statements(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.STATEMENTS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "SimFin", "count": len(items)},
        )
