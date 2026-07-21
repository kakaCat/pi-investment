"""S&P Global Platts commodity price assessment data source.

Provides benchmark commodity price assessments for energy, petrochemicals,
metals, and agriculture. API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class PlattsSource(EconomicDataSource):
    """S&P Global Platts commodity price assessment data source.

    Provides industry-standard benchmark price assessments for crude oil
    (dated Brent), refined products, natural gas (JKM, TTF, Henry Hub),
    LNG, petrochemicals, metals, and agricultural commodities.

    Platts assessments are used as settlement benchmarks in many physical
    and derivative contracts worldwide.

    API key required. Enterprise subscription. https://www.spglobal.com/platts
    """

    BASE_URL = "https://api.platts.com/price-assessment/v1"

    SYMBOLS = {
        "dated_brent": "Dated Brent crude oil ($/bbl)",
        "wti_cushing": "WTI at Cushing ($/bbl)",
        "dubai_crude": "Dubai crude ($/bbl)",
        "jkm": "Japan Korea Marker LNG ($/MMBtu)",
        "ttf": "Dutch TTF natural gas (EUR/MWh)",
        "henry_hub": "Henry Hub natural gas ($/MMBtu)",
        "gasoline_95": "Eurobob gasoline ($/mt)",
        "diesel_10ppm": "ULSD 10ppm diesel ($/mt)",
        "jet_fuel": "Jet fuel ($/mt)",
        "aluminum": "LME Aluminum ($/mt)",
        "copper": "LME Copper ($/mt)",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="Platts", requires_api_key=True)
        self.api_key = api_key or os.getenv("PLATTS_API_KEY", "")
        self.session = SessionManager.get_session("platts")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("Platts API key not configured. Requires enterprise subscription.")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/symbols",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "SPGlobal_Platts"},
                metadata={"source": "Platts", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Platts connection test failed: {e}")
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
            params: Dict[str, Any] = {"symbol": series_id}
            if start_date:
                params["startDate"] = start_date
            if end_date:
                params["endDate"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/assessments",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Platts", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "Platts", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.SYMBOLS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "Platts", "query": query},
        )

    def get_symbols(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.SYMBOLS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "Platts", "count": len(items)},
        )
