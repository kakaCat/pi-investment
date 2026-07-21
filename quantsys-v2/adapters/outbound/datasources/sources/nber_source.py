"""NBER (National Bureau of Economic Research) data source.

Provides access to NBER working papers and economic research.

API Documentation: https://www.nber.org/
No official API - uses web scraping of public data.
"""

from typing import Optional, Dict, Any, List
import logging
from datetime import datetime

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class NBERSource(EconomicDataSource):
    """NBER economic research data source.

    Provides access to:
    - Working papers
    - Research programs
    - Economic data
    - Business cycle dates
    - Recession indicators

    No API key required (public data).
    """

    BASE_URL = "https://www.nber.org"
    PAPERS_URL = "https://www.nber.org/papers"

    # Research programs
    PROGRAMS = {
        "AG": "Aging",
        "AP": "Asset Pricing",
        "CF": "Corporate Finance",
        "CH": "Children",
        "DAE": "Development of the American Economy",
        "DEV": "Development Economics",
        "ED": "Education",
        "EFG": "Economics of Fluctuations and Growth",
        "ENV": "Environment and Energy Economics",
        "HC": "Health Care",
        "HE": "Health Economics",
        "IFM": "International Finance and Macroeconomics",
        "IO": "Industrial Organization",
        "ITI": "Innovation and Entrepreneurship",
        "LE": "Labor Studies",
        "LS": "Law and Economics",
        "ME": "Monetary Economics",
        "PE": "Public Economics",
        "POL": "Political Economy",
        "PR": "Productivity, Innovation, and Entrepreneurship"
    }

    def __init__(self):
        """Initialize NBER data source."""
        super().__init__(name="NBER", requires_api_key=False)
        self.session = SessionManager.get_session("nber")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to NBER website.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/cycles.html",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "NBER"},
                metadata={"source": "NBER", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"NBER connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_programs(self) -> DataSourceResponse:
        """Get list of NBER research programs.

        Returns:
            DataSourceResponse with program list
        """
        programs = [
            {"code": code, "name": name}
            for code, name in self.PROGRAMS.items()
        ]

        return DataSourceResponse.success_response(
            data=programs,
            metadata={
                "source": "NBER",
                "count": len(programs)
            }
        )

    def get_paper_info(self, paper_id: str) -> DataSourceResponse:
        """Get information about a specific working paper.

        Args:
            paper_id: NBER working paper number (e.g., 'w12345')

        Returns:
            DataSourceResponse with paper information
        """
        try:
            # Construct paper URL
            paper_url = f"{self.PAPERS_URL}/{paper_id}"

            response = self.session.get(paper_url, timeout=30)
            response.raise_for_status()

            # Return basic info (full parsing would require BeautifulSoup)
            return DataSourceResponse.success_response(
                data={
                    "paper_id": paper_id,
                    "url": paper_url,
                    "pdf_url": f"{paper_url}.pdf",
                    "note": "HTML parsing required for full metadata"
                },
                metadata={
                    "source": "NBER",
                    "paper_id": paper_id
                }
            )
        except Exception as e:
            return handle_request_error(e, "NBER", "get_paper_info")

    def get_business_cycles(self) -> DataSourceResponse:
        """Get US business cycle dates (recessions).

        Returns:
            DataSourceResponse with business cycle data
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/cycles.html",
                timeout=30
            )
            response.raise_for_status()

            # Return URL for now (full parsing would require BeautifulSoup)
            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.BASE_URL}/cycles.html",
                    "note": "HTML parsing required for structured data",
                    "description": "US Business Cycle Expansions and Contractions"
                },
                metadata={
                    "source": "NBER",
                    "data_type": "business_cycles"
                }
            )
        except Exception as e:
            return handle_request_error(e, "NBER", "get_business_cycles")

    def search_papers(
        self,
        program: Optional[str] = None,
        year: Optional[int] = None
    ) -> DataSourceResponse:
        """Search for working papers.

        Args:
            program: Program code (e.g., 'EFG', 'LE')
            year: Publication year

        Returns:
            DataSourceResponse with search information
        """
        try:
            if program and program not in self.PROGRAMS:
                return DataSourceResponse.error_response(
                    error=f"Invalid program: {program}. Valid: {list(self.PROGRAMS.keys())}"
                )

            # Construct search URL
            if program:
                search_url = f"{self.BASE_URL}/programs/{program.lower()}"
            else:
                search_url = f"{self.PAPERS_URL}"

            return DataSourceResponse.success_response(
                data={
                    "search_url": search_url,
                    "program": program,
                    "program_name": self.PROGRAMS.get(program) if program else None,
                    "year": year,
                    "note": "Visit URL or implement HTML parsing for paper list"
                },
                metadata={
                    "source": "NBER",
                    "program": program,
                    "year": year
                }
            )
        except Exception as e:
            return handle_request_error(e, "NBER", "search_papers")

    def get_recent_papers(self, limit: int = 10) -> DataSourceResponse:
        """Get recent working papers.

        Args:
            limit: Maximum number of papers

        Returns:
            DataSourceResponse with recent papers info
        """
        try:
            response = self.session.get(
                f"{self.PAPERS_URL}",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.PAPERS_URL}",
                    "limit": limit,
                    "note": "HTML parsing required for paper list"
                },
                metadata={
                    "source": "NBER",
                    "data_type": "recent_papers"
                }
            )
        except Exception as e:
            return handle_request_error(e, "NBER", "get_recent_papers")
