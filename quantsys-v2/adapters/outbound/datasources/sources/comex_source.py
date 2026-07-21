"""COMEX (Commodity Exchange) futures data source.

Provides access to precious metals futures data: gold, silver, copper,
platinum, palladium. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class COMEXSource(EconomicDataSource):
    """COMEX (CME Commodity Exchange) precious metals futures data source.

    Provides gold, silver, copper, platinum, and palladium futures prices,
    settlement data, open interest, volume, and inventory/warehouse reports.
    Essential for precious metals traders and inflation hedgers.

    No API key required. Uses CME Group public data.
    """

    BASE_URL = "https://www.cmegroup.com"

    METALS = {
        "gold": {"code": "GC", "unit": "USD/troy oz", "contract_size": "100 oz"},
        "micro_gold": {"code": "MGC", "unit": "USD/troy oz", "contract_size": "10 oz"},
        "silver": {"code": "SI", "unit": "USD/troy oz", "contract_size": "5,000 oz"},
        "micro_silver": {"code": "SIL", "unit": "USD/troy oz", "contract_size": "1,000 oz"},
        "copper": {"code": "HG", "unit": "USD/lb", "contract_size": "25,000 lbs"},
        "platinum": {"code": "PL", "unit": "USD/troy oz", "contract_size": "50 oz"},
        "palladium": {"code": "PA", "unit": "USD/troy oz", "contract_size": "100 oz"},
        "aluminum": {"code": "ALI", "unit": "USD/metric ton", "contract_size": "25 mt"},
    }

    def __init__(self):
        super().__init__(name="COMEX", requires_api_key=False)
        self.session = SessionManager.get_session("comex")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/cmegroup/globex/price-discovery-settlements",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "COMEX"},
                metadata={"source": "COMEX", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"COMEX connection test failed: {e}")
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
            metal = self.METALS.get(series_id.lower(), self.METALS["gold"])
            params: Dict[str, Any] = {
                "product": metal["code"],
                "format": "json",
            }
            response = self.session.get(
                f"{self.BASE_URL}/cmegroup/globex/price-discovery-settlements",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "COMEX", "metal": series_id, "code": metal["code"]},
            )
        except Exception as e:
            return handle_request_error(e, "COMEX", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "code": v["code"], "unit": v["unit"]}
            for k, v in self.METALS.items()
            if query.lower() in k.lower() or query.lower() in v["code"].lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "COMEX", "query": query},
        )

    def get_gold(self) -> DataSourceResponse:
        """Get gold futures (GC) settlement data."""
        return self.get_series("gold")

    def get_silver(self) -> DataSourceResponse:
        """Get silver futures (SI) settlement data."""
        return self.get_series("silver")

    def get_copper(self) -> DataSourceResponse:
        """Get copper futures (HG) settlement data."""
        return self.get_series("copper")

    def get_metals(self) -> DataSourceResponse:
        items = [
            {"name": k, "code": v["code"], "unit": v["unit"], "contract_size": v["contract_size"]}
            for k, v in self.METALS.items()
        ]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "COMEX", "count": len(items)},
        )
