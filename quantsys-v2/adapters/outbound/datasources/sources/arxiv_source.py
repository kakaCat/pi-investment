"""arXiv academic paper data source.

Provides access to arXiv preprint repository for scientific papers.

API Documentation: https://arxiv.org/help/api/
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging
import xml.etree.ElementTree as ET

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class ArxivSource(EconomicDataSource):
    """arXiv academic paper data source.

    Provides access to:
    - 2+ million preprints
    - Physics, mathematics, computer science, etc.
    - Paper metadata (title, authors, abstract)
    - PDF downloads
    - Search and filtering

    No API key required.
    """

    BASE_URL = "http://export.arxiv.org/api/query"

    # Common categories
    CATEGORIES = {
        "cs.AI": "Artificial Intelligence",
        "cs.LG": "Machine Learning",
        "cs.CL": "Computation and Language",
        "cs.CV": "Computer Vision",
        "econ.EM": "Econometrics",
        "econ.GN": "General Economics",
        "q-fin.CP": "Computational Finance",
        "q-fin.EC": "Economics",
        "q-fin.GN": "General Finance",
        "q-fin.MF": "Mathematical Finance",
        "q-fin.PM": "Portfolio Management",
        "q-fin.PR": "Pricing of Securities",
        "q-fin.RM": "Risk Management",
        "q-fin.ST": "Statistical Finance",
        "q-fin.TR": "Trading and Market Microstructure",
        "stat.ML": "Machine Learning (Statistics)",
        "math.OC": "Optimization and Control"
    }

    def __init__(self):
        """Initialize arXiv data source."""
        super().__init__(name="arXiv", requires_api_key=False)
        self.session = SessionManager.get_session("arxiv")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to arXiv API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                self.BASE_URL,
                params={"search_query": "all:test", "max_results": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "arXiv"},
                metadata={"source": "arXiv", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"arXiv connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _parse_entry(self, entry: ET.Element) -> Dict[str, Any]:
        """Parse XML entry to dictionary.

        Args:
            entry: XML entry element

        Returns:
            Parsed entry dictionary
        """
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        result = {}
        result["id"] = entry.find("atom:id", ns).text if entry.find("atom:id", ns) is not None else None
        result["title"] = entry.find("atom:title", ns).text.strip() if entry.find("atom:title", ns) is not None else None
        result["summary"] = entry.find("atom:summary", ns).text.strip() if entry.find("atom:summary", ns) is not None else None
        result["published"] = entry.find("atom:published", ns).text if entry.find("atom:published", ns) is not None else None
        result["updated"] = entry.find("atom:updated", ns).text if entry.find("atom:updated", ns) is not None else None

        # Authors
        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.find("atom:name", ns)
            if name is not None:
                authors.append(name.text)
        result["authors"] = authors

        # Categories
        categories = []
        for category in entry.findall("atom:category", ns):
            term = category.get("term")
            if term:
                categories.append(term)
        result["categories"] = categories

        # Links
        links = {}
        for link in entry.findall("atom:link", ns):
            rel = link.get("rel", "alternate")
            href = link.get("href")
            if href:
                links[rel] = href
        result["links"] = links

        return result

    def search(
        self,
        query: str,
        max_results: int = 10,
        sort_by: str = "relevance",
        sort_order: str = "descending"
    ) -> DataSourceResponse:
        """Search arXiv papers.

        Args:
            query: Search query (e.g., 'all:machine learning', 'ti:neural networks')
            max_results: Maximum number of results
            sort_by: Sort by ('relevance', 'lastUpdatedDate', 'submittedDate')
            sort_order: Sort order ('ascending', 'descending')

        Returns:
            DataSourceResponse with search results
        """
        try:
            params = {
                "search_query": query,
                "max_results": max_results,
                "sortBy": sort_by,
                "sortOrder": sort_order
            }

            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            # Parse XML response
            root = ET.fromstring(response.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            entries = []
            for entry in root.findall("atom:entry", ns):
                entries.append(self._parse_entry(entry))

            return DataSourceResponse.success_response(
                data=entries,
                metadata={
                    "source": "arXiv",
                    "query": query,
                    "count": len(entries)
                }
            )
        except Exception as e:
            return handle_request_error(e, "arXiv", "search")

    def search_by_category(
        self,
        category: str,
        max_results: int = 10
    ) -> DataSourceResponse:
        """Search papers by category.

        Args:
            category: Category code (e.g., 'cs.AI', 'q-fin.CP')
            max_results: Maximum number of results

        Returns:
            DataSourceResponse with papers in category
        """
        query = f"cat:{category}"
        return self.search(query, max_results=max_results, sort_by="submittedDate")

    def search_by_author(
        self,
        author: str,
        max_results: int = 10
    ) -> DataSourceResponse:
        """Search papers by author.

        Args:
            author: Author name
            max_results: Maximum number of results

        Returns:
            DataSourceResponse with author's papers
        """
        query = f"au:{author}"
        return self.search(query, max_results=max_results, sort_by="submittedDate")

    def get_paper(self, arxiv_id: str) -> DataSourceResponse:
        """Get specific paper by arXiv ID.

        Args:
            arxiv_id: arXiv ID (e.g., '2103.00020')

        Returns:
            DataSourceResponse with paper details
        """
        query = f"id:{arxiv_id}"
        return self.search(query, max_results=1)

    def get_recent_papers(
        self,
        category: Optional[str] = None,
        max_results: int = 10
    ) -> DataSourceResponse:
        """Get recent papers.

        Args:
            category: Category code (optional)
            max_results: Maximum number of results

        Returns:
            DataSourceResponse with recent papers
        """
        if category:
            query = f"cat:{category}"
        else:
            query = "all:*"

        return self.search(
            query,
            max_results=max_results,
            sort_by="submittedDate",
            sort_order="descending"
        )
