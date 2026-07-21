"""Crossref academic citation data source.

Provides access to scholarly metadata including citations, DOIs, and publications.

API Documentation: https://api.crossref.org/
No API key required (polite pool recommended).
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CrossrefSource(EconomicDataSource):
    """Crossref academic citation data source.

    Provides access to:
    - 130+ million scholarly records
    - DOI metadata
    - Citation data
    - Journal information
    - Author data
    - Funder information

    No API key required (polite pool with email recommended).
    """

    BASE_URL = "https://api.crossref.org"

    def __init__(self, mailto: Optional[str] = None):
        """Initialize Crossref data source.

        Args:
            mailto: Email for polite pool (recommended for better rate limits)
        """
        super().__init__(name="Crossref", requires_api_key=False)
        self.mailto = mailto
        self.session = SessionManager.get_session("crossref")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Crossref API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            params = {}
            if self.mailto:
                params["mailto"] = self.mailto

            response = self.session.get(
                f"{self.BASE_URL}/works",
                params={**params, "rows": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Crossref", "polite_pool": bool(self.mailto)},
                metadata={"source": "Crossref", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Crossref connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to Crossref API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        request_params = params or {}
        if self.mailto:
            request_params["mailto"] = self.mailto

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def search_works(
        self,
        query: str,
        rows: int = 20,
        sort: str = "relevance"
    ) -> DataSourceResponse:
        """Search for scholarly works.

        Args:
            query: Search query
            rows: Number of results
            sort: Sort order ('relevance', 'score', 'updated', 'deposited', 'indexed', 'published')

        Returns:
            DataSourceResponse with search results
        """
        try:
            params = {
                "query": query,
                "rows": rows,
                "sort": sort
            }

            data = self._make_request("works", params=params)

            return DataSourceResponse.success_response(
                data=data.get("message", {}).get("items", []),
                metadata={
                    "source": "Crossref",
                    "query": query,
                    "total_results": data.get("message", {}).get("total-results", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "Crossref", "search_works")

    def get_work(self, doi: str) -> DataSourceResponse:
        """Get metadata for a specific DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            DataSourceResponse with work metadata
        """
        try:
            data = self._make_request(f"works/{doi}")

            return DataSourceResponse.success_response(
                data=data.get("message", {}),
                metadata={
                    "source": "Crossref",
                    "doi": doi
                }
            )
        except Exception as e:
            return handle_request_error(e, "Crossref", "get_work")

    def search_by_author(
        self,
        author: str,
        rows: int = 20
    ) -> DataSourceResponse:
        """Search works by author.

        Args:
            author: Author name
            rows: Number of results

        Returns:
            DataSourceResponse with author's works
        """
        try:
            params = {
                "query.author": author,
                "rows": rows
            }

            data = self._make_request("works", params=params)

            return DataSourceResponse.success_response(
                data=data.get("message", {}).get("items", []),
                metadata={
                    "source": "Crossref",
                    "author": author,
                    "total_results": data.get("message", {}).get("total-results", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "Crossref", "search_by_author")

    def search_by_title(
        self,
        title: str,
        rows: int = 20
    ) -> DataSourceResponse:
        """Search works by title.

        Args:
            title: Work title
            rows: Number of results

        Returns:
            DataSourceResponse with matching works
        """
        try:
            params = {
                "query.title": title,
                "rows": rows
            }

            data = self._make_request("works", params=params)

            return DataSourceResponse.success_response(
                data=data.get("message", {}).get("items", []),
                metadata={
                    "source": "Crossref",
                    "title": title,
                    "total_results": data.get("message", {}).get("total-results", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "Crossref", "search_by_title")

    def get_journal(self, issn: str) -> DataSourceResponse:
        """Get journal information.

        Args:
            issn: Journal ISSN

        Returns:
            DataSourceResponse with journal metadata
        """
        try:
            data = self._make_request(f"journals/{issn}")

            return DataSourceResponse.success_response(
                data=data.get("message", {}),
                metadata={
                    "source": "Crossref",
                    "issn": issn
                }
            )
        except Exception as e:
            return handle_request_error(e, "Crossref", "get_journal")

    def get_funders(self, query: Optional[str] = None, rows: int = 20) -> DataSourceResponse:
        """Get funder information.

        Args:
            query: Search query (optional)
            rows: Number of results

        Returns:
            DataSourceResponse with funder data
        """
        try:
            params = {"rows": rows}
            if query:
                params["query"] = query

            data = self._make_request("funders", params=params)

            return DataSourceResponse.success_response(
                data=data.get("message", {}).get("items", []),
                metadata={
                    "source": "Crossref",
                    "query": query,
                    "total_results": data.get("message", {}).get("total-results", 0)
                }
            )
        except Exception as e:
            return handle_request_error(e, "Crossref", "get_funders")
