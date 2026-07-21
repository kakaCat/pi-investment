"""Federal Reserve System (the Fed) data source.

Provides access to Federal Reserve monetary policy data, including
federal funds rate, discount rate, balance sheet (H.4.1), and
Selected Interest Rates (H.15). Complements FRED for Fed-specific data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class FederalReserveSource(EconomicDataSource):
    """Federal Reserve System monetary policy and banking data source.

    Provides access to:
    - Federal funds rate (effective, target range upper/lower)
    - Discount rate (primary/secondary/seasonal credit)
    - Balance sheet data (H.4.1 statistical release)
    - Selected Interest Rates (H.15: Treasury, mortgage, corporate)
    - Reserve balances and money supply measures
    - FOMC meeting calendars and minutes
    - Senior Loan Officer Survey (SLOOS)

    Uses the Federal Reserve Data API (data.nasdaq.com or FRED).
    No API key required for basic endpoints.
    """

    BASE_URL = "https://www.federalreserve.gov"
    API_URL = "https://markets.newyorkfed.org/api"

    INDICATORS = {
        "effr": "Effective Federal Funds Rate",
        "sofr": "Secured Overnight Financing Rate",
        "target_range_upper": "FFR target range upper bound",
        "target_range_lower": "FFR target range lower bound",
        "discount_primary": "Primary credit discount rate",
        "discount_secondary": "Secondary credit discount rate",
        "balance_sheet_total": "Total assets (H.4.1)",
        "reserve_balances": "Reserve balances with Federal Reserve Banks",
        "treasury_10yr": "10-year Treasury yield (H.15)",
        "mortgage_30yr": "30-year fixed mortgage rate (H.15)",
        "corporate_aaa": "Moody's AAA corporate bond yield (H.15)",
    }

    def __init__(self):
        super().__init__(name="FederalReserve", requires_api_key=False)
        self.session = SessionManager.get_session("fed")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.API_URL}/rates/unsecured/effr/last/5",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "FederalReserve"},
                metadata={"source": "FederalReserve", "base_url": self.API_URL},
            )
        except Exception as e:
            logger.error(f"Fed connection test failed: {e}")
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
            if start_date and end_date:
                url = f"{self.API_URL}/rates/unsecured/{series_id}/range"
                params = {"startDate": start_date, "endDate": end_date}
            else:
                url = f"{self.API_URL}/rates/unsecured/{series_id}/last/100"
                params = {}

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "FederalReserve", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "FederalReserve", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "FederalReserve", "query": query},
        )

    def get_federal_funds_rate(self) -> DataSourceResponse:
        """Get Effective Federal Funds Rate (EFFR) history."""
        return self.get_series("effr")

    def get_sofr(self) -> DataSourceResponse:
        """Get Secured Overnight Financing Rate (SOFR) history."""
        try:
            response = self.session.get(
                f"{self.API_URL}/rates/unsecured/sofr/last/100",
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "FederalReserve", "series": "SOFR"},
            )
        except Exception as e:
            return handle_request_error(e, "FederalReserve", "get_sofr")

    def get_treasury_yields(
        self, maturity: str = "10yr"
    ) -> DataSourceResponse:
        """Get Treasury yield curve data.

        Args:
            maturity: One of '1mo', '3mo', '6mo', '1yr', '2yr', '5yr', '10yr', '30yr'
        """
        try:
            response = self.session.get(
                f"{self.API_URL}/rates/treasury/all/last/100",
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "FederalReserve", "maturity": maturity},
            )
        except Exception as e:
            return handle_request_error(e, "FederalReserve", "get_treasury_yields")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "FederalReserve", "count": len(items)},
        )
