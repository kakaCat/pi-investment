"""Freightos Baltic Index (FBX) container freight data source.

Provides global container freight spot rates for key shipping routes.
No API key required for public data.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class FreightosSource(EconomicDataSource):
    """Freightos Baltic Index (FBX) container freight data source.

    Provides daily spot container freight rates for 12 major global shipping
    routes including China-US West Coast, China-US East Coast, China-Europe,
    Europe-South America, etc.

    FBX is a key indicator for global supply chain costs and inflation
    forecasting. Freight rates historically lead goods inflation by 3-6 months.

    No API key required for public FBX data.
    """

    BASE_URL = "https://fbx.freightos.com/api"

    ROUTES = {
        "FBX01": "China/East Asia to US West Coast",
        "FBX02": "US West Coast to China/East Asia",
        "FBX03": "China/East Asia to US East Coast",
        "FBX04": "US East Coast to China/East Asia",
        "FBX11": "China/East Asia to North Europe",
        "FBX12": "North Europe to China/East Asia",
        "FBX13": "China/East Asia to Mediterranean",
        "FBX14": "Mediterranean to China/East Asia",
        "FBX21": "North Europe to US East Coast",
        "FBX22": "US East Coast to North Europe",
        "FBX24": "Europe to South America East Coast",
        "FBX26": "Europe to South America West Coast",
    }

    def __init__(self):
        super().__init__(name="Freightos", requires_api_key=False)
        self.session = SessionManager.get_session("freightos")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/fbx/global",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "FreightosFBX"},
                metadata={"source": "Freightos", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Freightos connection test failed: {e}")
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
                params["from"] = start_date
            if end_date:
                params["to"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/fbx/{series_id.lower()}",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Freightos", "route": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "Freightos", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.ROUTES.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "Freightos", "query": query},
        )

    def get_global_index(self) -> DataSourceResponse:
        """Get global FBX container freight index (composite)."""
        return self.get_series("global")

    def get_china_uswc(self) -> DataSourceResponse:
        """Get China to US West Coast freight rates (most watched route)."""
        return self.get_series("FBX01")

    def get_routes(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.ROUTES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "Freightos", "count": len(items)},
        )
