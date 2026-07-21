"""GitHub activity and open-source development data source.
Tracks software development activity as a leading economic indicator. No API key required.
"""

from typing import Optional, Dict, Any
import logging
import os
from datetime import datetime, timedelta

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class GitHubActivitySource(EconomicDataSource):
    """GitHub development activity data source.
    Repository stats, language trends, developer geography, open-source health.
    Economic: tech sector proxy, developer labor market, innovation tracking."""

    BASE_URL = "https://api.github.com"
    TRENDING_LANGUAGES = ["Python", "JavaScript", "TypeScript", "Go", "Rust",
        "Java", "C++", "Kotlin", "Swift", "Zig"]

    def __init__(self, api_token: Optional[str] = None):
        super().__init__(name="GitHubActivity", requires_api_key=False)
        self.api_token = api_token or os.getenv("GITHUB_TOKEN")
        self.session = SessionManager.get_session("github")
        if self.api_token:
            self.session.headers.update({"Authorization": f"Bearer {self.api_token}"})

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/repos/torvalds/linux", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "GitHub"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_repository(self, owner: str, repo: str) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/repos/{owner}/{repo}", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "GitHub", "repo": f"{owner}/{repo}"})
        except Exception as e:
            return handle_request_error(e, "GitHub", "get_repository")

    def get_trending_repos(self, language: Optional[str] = None, since: str = "weekly") -> DataSourceResponse:
        try:
            days = {"daily": 1, "weekly": 7, "monthly": 30}
            d = (datetime.now() - timedelta(days=days.get(since, 7))).strftime("%Y-%m-%d")
            query = f"created:>{d}"
            if language: query += f" language:{language}"
            r = self.session.get(f"{self.BASE_URL}/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 25}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "GitHub", "language": language, "since": since})
        except Exception as e:
            return handle_request_error(e, "GitHub", "get_trending_repos")

    def get_languages(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.TRENDING_LANGUAGES,
            metadata={"source": "GitHub", "count": len(self.TRENDING_LANGUAGES)})
