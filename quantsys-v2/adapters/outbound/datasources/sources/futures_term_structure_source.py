"""Futures term structure and carry data source.
Provides commodity futures term structure, calendar spreads, and roll yield data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class FuturesTermStructureSource(EconomicDataSource):
    """Commodity futures term structure and carry data source.
    Curve shape (contango/backwardation), calendar spreads, roll yield.
    Economic: commodity supply/demand balance, storage economics, carry returns."""

    FMP_URL = "https://financialmodelingprep.com/api/v4"
    COMMODITIES = ["crude_oil", "natural_gas", "gasoline", "gold", "silver",
        "copper", "corn", "wheat", "soybeans", "sugar", "coffee", "cotton"]

    def __init__(self):
        super().__init__(name="FuturesTermStructure", requires_api_key=False)
        self.session = SessionManager.get_session("futures_ts")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.FMP_URL}/quotes/commodity", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "FuturesTS"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_curve_shape(self, commodity: str = "crude_oil", exchange: str = "NYMEX") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.FMP_URL}/futures/curve/{commodity}",
                params={"exchange": exchange}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "FuturesTS", "commodity": commodity, "exchange": exchange})
        except Exception as e:
            return handle_request_error(e, "FuturesTermStructure", "get_curve_shape")

    def get_calendar_spreads(self, commodity: str = "crude_oil") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.FMP_URL}/futures/spreads/{commodity}", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "FuturesTS", "commodity": commodity, "indicator": "calendar_spread"})
        except Exception as e:
            return handle_request_error(e, "FuturesTermStructure", "get_calendar_spreads")

    def get_commodities(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.COMMODITIES,
            metadata={"source": "FuturesTermStructure", "count": len(self.COMMODITIES)})
