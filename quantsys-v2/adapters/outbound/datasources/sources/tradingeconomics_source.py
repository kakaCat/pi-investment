"""Trading Economics economic indicators data source.
Provides 300K+ economic indicators across 196 countries. Requires API key.
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class TradingEconomicsSource(EconomicDataSource):
    """Trading Economics global economic data source.
    300K+ indicators, bond yields, credit ratings, stock indices, currencies, commodities."""

    BASE_URL = "https://api.tradingeconomics.com"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="TradingEconomics", requires_api_key=True)
        self.api_key = api_key or os.getenv("TRADINGECONOMICS_API_KEY")
        self.session = SessionManager.get_session("tradingeconomics")

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Set TRADINGECONOMICS_API_KEY env var")
        try:
            r = self.session.get(f"{self.BASE_URL}/country/United%20States",
                params={"c": self.api_key}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "TE"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        if params is None: params = {}
        params["c"] = self.api_key
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_indicators(self, country: str, indicator: Optional[str] = None) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            endpoint = f"country/{country}"
            if indicator: endpoint += f"/{indicator}"
            data = self._make_request(endpoint)
            return DataSourceResponse.success_response(data=data,
                metadata={"source": "TradingEconomics", "country": country})
        except Exception as e:
            return handle_request_error(e, "TradingEconomics", "get_indicators")

    def get_calendar(self, country: Optional[str] = None) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            endpoint = f"calendar/country/{country}" if country else "calendar"
            data = self._make_request(endpoint)
            return DataSourceResponse.success_response(data=data,
                metadata={"source": "TradingEconomics", "type": "calendar"})
        except Exception as e:
            return handle_request_error(e, "TradingEconomics", "get_calendar")
