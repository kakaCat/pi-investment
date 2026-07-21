"""Google Trends search interest data source.
Provides search volume trends for economic nowcasting and sentiment. No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class GoogleTrendsSource(EconomicDataSource):
    """Google Trends search interest data source.
    Search interest time series, trending searches, geographic breakdown, related topics.
    Economic: GDP nowcasting, unemployment forecasting, consumer confidence proxy."""

    BASE_URL = "https://trends.google.com/trends/api"
    ECONOMIC_CATEGORIES = {"unemployment": 12, "real_estate": 85, "autos": 47,
        "finance": 7, "shopping": 18, "travel": 67, "business": 8}

    def __init__(self):
        super().__init__(name="GoogleTrends", requires_api_key=False)
        self.session = SessionManager.get_session("google_trends")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/explore",
                params={"geo": "US", "tz": "-480"}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "GoogleTrends"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_interest_over_time(self, keywords: List[str], geo: str = "US",
        timeframe: str = "today 12-m") -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/trendingsearches/daily",
                params={"q": ",".join(keywords[:5]), "geo": geo, "date": timeframe}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "GoogleTrends", "keywords": keywords, "geo": geo})
        except Exception as e:
            return handle_request_error(e, "GoogleTrends", "get_interest_over_time")

    def get_categories(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "id": i} for n, i in self.ECONOMIC_CATEGORIES.items()],
            metadata={"source": "GoogleTrends", "count": len(self.ECONOMIC_CATEGORIES)})
