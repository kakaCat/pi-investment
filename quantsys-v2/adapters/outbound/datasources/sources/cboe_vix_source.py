"""CBOE volatility and options market data source.

Provides VIX, VIX futures term structure, SKEW, and options market statistics.
No API key required for basic data.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CBOEVIXSource(EconomicDataSource):
    """CBOE (Chicago Board Options Exchange) volatility data source.

    Provides CBOE Volatility Index (VIX), VIX futures term structure,
    VIX options data, SKEW index (tail risk), put/call ratios, and
    VVIX (volatility of VIX). Essential for market risk sentiment.
    No API key required.
    """

    BASE_URL = "https://cdn.cboe.com/api"

    INDICATORS = {
        "vix": "CBOE Volatility Index (fear gauge)",
        "vix_9d": "VIX9D (9-day expected volatility)",
        "vix_3m": "VIX3M (3-month expected volatility)",
        "vix_6m": "VIX6M (6-month volatility)",
        "vix_1y": "VIX1Y (1-year volatility)",
        "skew": "CBOE SKEW index (tail risk, black swan indicator)",
        "vvix": "VVIX (volatility of VIX)",
        "put_call_ratio": "Total put/call ratio",
        "equity_put_call": "Equity-only put/call ratio",
        "vix_term_structure": "VIX futures term structure",
    }

    def __init__(self):
        super().__init__(name="CBOEVIX", requires_api_key=False)
        self.session = SessionManager.get_session("cboe")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/vix/futures", timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "CBOE"},
                metadata={"source": "CBOE", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"CBOE connection test failed: {e}")
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
            url = f"{self.BASE_URL}/vix/{series_id}"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "CBOE", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "CBOEVIX", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "CBOE", "query": query},
        )

    def get_vix(self) -> DataSourceResponse:
        """Get current VIX index value and recent history."""
        return self.get_series("current")

    def get_vix_term_structure(self) -> DataSourceResponse:
        """Get VIX futures term structure for contango/backwardation analysis."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/vix/futures", timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "CBOE", "indicator": "vix_term_structure"},
            )
        except Exception as e:
            return handle_request_error(e, "CBOEVIX", "get_vix_term_structure")

    def get_put_call_ratio(self) -> DataSourceResponse:
        """Get equity put/call ratio as sentiment indicator."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/vix/putcall", timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "CBOE", "indicator": "put_call_ratio"},
            )
        except Exception as e:
            return handle_request_error(e, "CBOEVIX", "get_put_call_ratio")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "CBOE", "count": len(items)},
        )
