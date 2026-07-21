"""GDELT Project global news and event monitoring data source.
Provides real-time monitoring of global news, events, and sentiment. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class GDELTSource(EconomicDataSource):
    """GDELT Project global event and news monitoring data source.
    Global Knowledge Graph, event database, sentiment/tone, geopolitical tracking."""

    BASE_URL = "https://api.gdeltproject.org/api/v2"
    EVENT_TYPES = {"PROTEST": "14", "MILITARY_CONFLICT": "19", "DIPLOMATIC": "04",
        "ECONOMIC": "06", "HUMANITARIAN": "12"}

    def __init__(self):
        super().__init__(name="GDELT", requires_api_key=False)
        self.session = SessionManager.get_session("gdelt")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/doc/doc",
                params={"query": "test", "mode": "artlist", "maxrecords": 1}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "GDELT"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def search_news(self, query: str, max_records: int = 50, timespan: str = "7d") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/doc/doc",
                params={"query": query, "mode": "artlist", "maxrecords": min(max_records, 250),
                "timespan": timespan, "format": "json"}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "GDELT", "query": query, "timespan": timespan})
        except Exception as e:
            return handle_request_error(e, "GDELT", "search_news")

    def get_tone(self, query: str, timespan: str = "30d") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/doc/doc",
                params={"query": query, "mode": "tonechart", "timespan": timespan, "format": "json"}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "GDELT", "query": query, "indicator": "sentiment"})
        except Exception as e:
            return handle_request_error(e, "GDELT", "get_tone")

    def get_event_types(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "cameo_code": c} for n, c in self.EVENT_TYPES.items()],
            metadata={"source": "GDELT", "count": len(self.EVENT_TYPES)})
