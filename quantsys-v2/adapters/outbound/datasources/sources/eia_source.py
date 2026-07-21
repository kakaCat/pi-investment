"""U.S. Energy Information Administration data source.
Provides comprehensive energy statistics. Requires API key (free registration).
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EIASource(EconomicDataSource):
    """U.S. Energy Information Administration data source.
    Crude oil, natural gas, electricity, coal, renewables, STEO forecasts."""

    BASE_URL = "https://api.eia.gov/v2"
    KEY_ROUTES = {"crude_oil_production": "petroleum/crd/crpdn",
        "crude_oil_stocks": "petroleum/stoc/wstk", "nat_gas_storage": "natural-gas/stor/wkly",
        "nat_gas_prices": "natural-gas/pri/fut", "electricity": "electricity/rto"}

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="EIA", requires_api_key=True)
        self.api_key = api_key or os.getenv("EIA_API_KEY")
        self.session = SessionManager.get_session("eia")

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Set EIA_API_KEY env var")
        try:
            r = self.session.get(f"{self.BASE_URL}/petroleum/crd/crpdn",
                params={"api_key": self.api_key, "length": 1}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "EIA"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def _make_request(self, route: str, params: Dict[str, Any]) -> DataSourceResponse:
        try:
            params["api_key"] = self.api_key
            r = self.session.get(f"{self.BASE_URL}/{route}", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(), metadata={"source": "EIA", "route": route})
        except Exception as e:
            return handle_request_error(e, "EIA", route)

    def get_crude_oil_production(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        return self._make_request("petroleum/crd/crpdn", {"data[]": "value", "frequency": "monthly"})

    def get_nat_gas_storage(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        return self._make_request("natural-gas/stor/wkly", {"data[]": "value"})

    def get_routes(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "route": r} for n, r in self.KEY_ROUTES.items()],
            metadata={"source": "EIA", "count": len(self.KEY_ROUTES)})
