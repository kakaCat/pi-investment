"""NYMEX (New York Mercantile Exchange) energy futures data source.

Provides access to crude oil, natural gas, gasoline, heating oil futures.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class NYMEXSource(EconomicDataSource):
    """NYMEX (CME Group) energy futures data source.

    Provides WTI crude oil (CL), natural gas (NG), RBOB gasoline (RB),
    heating oil (HO), Brent crude (BZ), and ethanol futures. Includes
    settlement prices, open interest, volume, and futures curve data.

    No API key required. Uses CME Group public data.
    """

    BASE_URL = "https://www.cmegroup.com"

    PRODUCTS = {
        "wti": {"code": "CL", "name": "WTI Crude Oil", "unit": "USD/barrel", "size": "1,000 barrels"},
        "brent": {"code": "BZ", "name": "Brent Crude Oil", "unit": "USD/barrel", "size": "1,000 barrels"},
        "nat_gas": {"code": "NG", "name": "Henry Hub Natural Gas", "unit": "USD/MMBtu", "size": "10,000 MMBtu"},
        "rbob": {"code": "RB", "name": "RBOB Gasoline", "unit": "USD/gallon", "size": "42,000 gallons"},
        "heating_oil": {"code": "HO", "name": "Heating Oil", "unit": "USD/gallon", "size": "42,000 gallons"},
        "ethanol": {"code": "EH", "name": "Ethanol", "unit": "USD/gallon", "size": "29,000 gallons"},
    }

    def __init__(self):
        super().__init__(name="NYMEX", requires_api_key=False)
        self.session = SessionManager.get_session("nymex")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/cmegroup/globex/price-discovery-settlements",
                params={"product": "CL", "limit": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "NYMEX"},
                metadata={"source": "NYMEX", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"NYMEX connection test failed: {e}")
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
            product = self.PRODUCTS.get(series_id.lower(), self.PRODUCTS["wti"])
            params: Dict[str, Any] = {
                "product": product["code"],
                "format": "json",
            }
            response = self.session.get(
                f"{self.BASE_URL}/cmegroup/globex/price-discovery-settlements",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "NYMEX", "product": series_id, "code": product["code"]},
            )
        except Exception as e:
            return handle_request_error(e, "NYMEX", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "code": v["code"], "name": v["name"]}
            for k, v in self.PRODUCTS.items()
            if query.lower() in k.lower() or query.lower() in v["name"].lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "NYMEX", "query": query},
        )

    def get_wti(self) -> DataSourceResponse:
        """Get WTI crude oil futures (CL) settlement data."""
        return self.get_series("wti")

    def get_nat_gas(self) -> DataSourceResponse:
        """Get Henry Hub natural gas futures (NG) settlement data."""
        return self.get_series("nat_gas")

    def get_products(self) -> DataSourceResponse:
        items = [
            {"name": k, "code": v["code"], "full_name": v["name"],
             "unit": v["unit"], "size": v["size"]}
            for k, v in self.PRODUCTS.items()
        ]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "NYMEX", "count": len(items)},
        )
