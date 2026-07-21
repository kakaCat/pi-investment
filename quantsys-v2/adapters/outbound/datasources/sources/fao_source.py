"""FAO (Food and Agriculture Organization) data source.
Provides global food price, agricultural production, and food security data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class FAOSource(EconomicDataSource):
    """UN Food and Agriculture Organization data source.
    FAO Food Price Index, agricultural production, trade, food balances."""

    BASE_URL = "https://fenixservices.fao.org/faostat/api/v1/en"
    FAO_DOMAINS = ["QCL", "QI", "QCLI", "PP", "FBS", "FS", "TP", "CC", "RF", "RL", "RT"]

    def __init__(self):
        super().__init__(name="FAO", requires_api_key=False)
        self.session = SessionManager.get_session("fao")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/data/QCL", params={"limit": 1}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "FAO"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_food_price_index(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/data/PP",
                params={"area": "5000", "element": "5531", "item": "22013b"}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "FAO", "indicator": "food_price_index"})
        except Exception as e:
            return handle_request_error(e, "FAO", "get_food_price_index")

    def get_production(self, item: Optional[str] = None, area: Optional[str] = None,
        year: Optional[int] = None) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {"limit": 100}
            if item: params["item"] = item
            if area: params["area"] = area
            if year: params["year"] = year
            r = self.session.get(f"{self.BASE_URL}/data/QCL", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "FAO", "area": area, "year": year})
        except Exception as e:
            return handle_request_error(e, "FAO", "get_production")

    def get_domains(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.FAO_DOMAINS,
            metadata={"source": "FAO", "count": len(self.FAO_DOMAINS)})
