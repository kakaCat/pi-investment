"""Event Registry geopolitical and news event data source.
Provides structured news event and geopolitical incident tracking. Requires API key.
"""

from typing import Optional, Dict, Any
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EventRegistrySource(EconomicDataSource):
    """Event Registry news and geopolitical event data source.
    Real-time event detection, clustering, sentiment analysis, risk indicators.
    Economic: geopolitical risk monitoring, event-driven trading, sanctions tracking."""

    BASE_URL = "https://eventregistry.org/api/v1"
    EVENT_CATEGORIES = ["political_conflict", "economic_sanction", "trade_dispute",
        "natural_disaster", "terrorism", "election", "policy_change", "central_bank"]

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="EventRegistry", requires_api_key=True)
        self.api_key = api_key or os.getenv("EVENTREGISTRY_API_KEY")
        self.session = SessionManager.get_session("event_registry")

    def validate_config(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Set EVENTREGISTRY_API_KEY env var")
        try:
            r = self.session.get(f"{self.BASE_URL}/minuteStreamArticles",
                params={"apiKey": self.api_key, "count": 1}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "EventRegistry"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def search_events(self, keyword: Optional[str] = None, source_country: Optional[str] = None,
        max_events: int = 50) -> DataSourceResponse:
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")
        try:
            params: Dict[str, Any] = {"apiKey": self.api_key, "count": max_events, "lang": "eng"}
            if keyword: params["keyword"] = keyword
            if source_country: params["sourceCountryUri"] = source_country
            r = self.session.get(f"{self.BASE_URL}/event/getEvents", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "EventRegistry", "keyword": keyword})
        except Exception as e:
            return handle_request_error(e, "EventRegistry", "search_events")

    def get_categories(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.EVENT_CATEGORIES,
            metadata={"source": "EventRegistry", "count": len(self.EVENT_CATEGORIES)})
