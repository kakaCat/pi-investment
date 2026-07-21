"""EIA Petroleum data source.

Provides US crude oil and petroleum product data: stocks, production, imports.
API key required (free from www.eia.gov).
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EIAPetroleumSource(EconomicDataSource):
    """EIA Petroleum data source.

    Provides weekly petroleum status report (crude stocks, gasoline stocks,
    distillate stocks), crude oil production, refinery utilization, product
    supplied (demand proxy), imports/exports, and SPR levels.

    The Weekly Petroleum Status Report is one of the most market-moving
    energy releases (Wednesdays 10:30 AM ET).

    API key required. Free registration at https://www.eia.gov/opendata/
    """

    BASE_URL = "https://api.eia.gov/v2"

    SERIES = {
        "crude_stocks": "PET.WCESTUS1.W",              # Weekly crude oil ending stocks
        "crude_production": "PET.WCRFPUS2.W",          # Weekly crude oil production
        "gasoline_stocks": "PET.WGTSTUS1.W",           # Weekly gasoline stocks
        "distillate_stocks": "PET.WDISTUS1.W",         # Weekly distillate fuel oil stocks
        "refinery_utilization": "PET.WPULEUS3.W",      # Refinery utilization rate
        "total_product_supplied": "PET.WRPUPUS2.W",    # Total product supplied (demand)
        "gasoline_demand": "PET.WGFUPUS2.W",           # Finished motor gasoline demand
        "crude_imports": "PET.WCRIMUS2.W",             # Weekly crude oil imports
        "crude_exports": "PET.WCREXUS2.W",             # Weekly crude oil exports
        "spr_stocks": "PET.WCSSTUS1.W",                # Strategic Petroleum Reserve
        "cushing_stocks": "PET.W_EPC0_SAX_YCUOK_MBBL.W",  # Cushing, OK hub stocks
        "wti_spot_price": "PET.RWTC.D",                # WTI spot price Cushing
        "brent_spot_price": "PET.RBRTE.D",             # Brent spot price
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="EIAPetroleum", requires_api_key=True)
        self.api_key = api_key or os.getenv("EIA_API_KEY", "")
        self.session = SessionManager.get_session("eia_petrol")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("EIA API key not configured. Register at https://www.eia.gov/opendata/")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/petroleum/stoc/wstk/data",
                params={"api_key": self.api_key, "length": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "EIA_Petroleum"},
                metadata={"source": "EIA", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"EIA Petroleum connection test failed: {e}")
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
            params: Dict[str, Any] = {"api_key": self.api_key, "length": 5000}
            if start_date:
                params["start"] = start_date
            if end_date:
                params["end"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/petroleum/stoc/wstk/data",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EIA_Petroleum", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "EIAPetroleum", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.SERIES.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "EIA_Petroleum", "query": query},
        )

    def get_crude_stocks(self) -> DataSourceResponse:
        """Get weekly crude oil stocks (key weekly report metric)."""
        return self.get_series("crude_stocks")

    def get_wti_price(self) -> DataSourceResponse:
        """Get WTI spot price at Cushing, OK."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/petroleum/pri/spt/data",
                params={"api_key": self.api_key, "length": 500},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EIA_Petroleum", "series": "wti_spot"},
            )
        except Exception as e:
            return handle_request_error(e, "EIAPetroleum", "get_wti_price")

    def get_series_list(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.SERIES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "EIA_Petroleum", "count": len(items)},
        )
