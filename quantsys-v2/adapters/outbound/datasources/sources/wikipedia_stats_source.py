"""Wikipedia pageview statistics data source.
Provides Wikipedia article traffic data as an information demand proxy. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class WikipediaStatsSource(EconomicDataSource):
    """Wikipedia pageview statistics data source.
    Daily pageviews, top articles, geographic distribution.
    Economic: information demand nowcasting, brand/corporate monitoring."""

    API_URL = "https://wikimedia.org/api/rest_v1"
    ECONOMIC_TOPICS = {"recession": "Recession", "inflation": "Inflation",
        "unemployment": "Unemployment", "bitcoin": "Bitcoin", "stock_market": "Stock_market"}

    def __init__(self):
        super().__init__(name="WikipediaStats", requires_api_key=False)
        self.session = SessionManager.get_session("wikipedia")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(
                f"{self.API_URL}/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/Earth/daily/20240101/20240102",
                timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "Wikipedia"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_pageviews(self, article: str, start_date: str, end_date: str) -> DataSourceResponse:
        try:
            r = self.session.get(
                f"{self.API_URL}/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{article}/daily/{start_date}/{end_date}",
                timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "Wikipedia", "article": article})
        except Exception as e:
            return handle_request_error(e, "Wikipedia", "get_pageviews")

    def get_economic_topics(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"topic": n, "article": t} for n, t in self.ECONOMIC_TOPICS.items()],
            metadata={"source": "Wikipedia", "count": len(self.ECONOMIC_TOPICS)})
