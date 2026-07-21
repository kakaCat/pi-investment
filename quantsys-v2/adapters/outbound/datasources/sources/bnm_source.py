"""Bank Negara Malaysia (BNM) central bank data source.

Provides access to Malaysian monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BNMSource(EconomicDataSource):
    """Bank Negara Malaysia (BNM) central bank data source.

    Provides access to Overnight Policy Rate (OPR), exchange rates (MYR),
    CPI inflation, GDP growth, money supply, and banking system stats.
    No API key required. Uses BNM Open API.
    """

    BASE_URL = "https://api.bnm.gov.my/public"

    INDICATORS = {
        "opr": "opr",                    # Overnight Policy Rate
        "exchange_rate": "exchange-rate",
        "interbank_rate": "interbank-rate",
        "kl_usd_reference_rate": "kl-usd-reference-rate",
        "cpi": "consumer-price-index",
        "gdp": "gross-domestic-product",
        "money_supply": "money-supply",
        "reserves": "international-reserves",
    }

    def __init__(self):
        super().__init__(name="BNM", requires_api_key=False)
        self.session = SessionManager.get_session("bnm")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/opr", timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "BNM"},
                metadata={"source": "BNM", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"BNM connection test failed: {e}")
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
            params: Dict[str, Any] = {}
            if start_date:
                params["start"] = start_date
            if end_date:
                params["end"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/{series_id}", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "BNM", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "BNM", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "BNM", "query": query},
        )

    def get_opr(self) -> DataSourceResponse:
        """Get Overnight Policy Rate (BNM policy rate)."""
        return self.get_series("opr")

    def get_exchange_rates(self) -> DataSourceResponse:
        """Get MYR exchange rates against major currencies."""
        return self.get_series("exchange-rate")

    def get_cpi(self) -> DataSourceResponse:
        """Get Malaysian Consumer Price Index."""
        return self.get_series("consumer-price-index")

    def get_gdp(self) -> DataSourceResponse:
        """Get Malaysian GDP data."""
        return self.get_series("gross-domestic-product")

    def get_reserves(self) -> DataSourceResponse:
        """Get international reserves."""
        return self.get_series("international-reserves")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "BNM", "count": len(items)},
        )
