"""OpenCorporates data source.

Provides access to global company registration data from official registries.

API Documentation: https://api.opencorporates.com/documentation/API-Reference
Requires API key for full access (free tier available).
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class OpenCorporatesSource(EconomicDataSource):
    """OpenCorporates company data source.

    Provides access to:
    - Company registration data
    - Officer information
    - Corporate filings
    - Company search
    - Jurisdiction data

    API key optional (free tier available).
    """

    BASE_URL = "https://api.opencorporates.com/v0.4"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenCorporates data source.

        Args:
            api_key: OpenCorporates API key (optional, or set OPENCORPORATES_API_KEY env var)
        """
        super().__init__(name="OpenCorporates", requires_api_key=False)
        self.api_key = api_key or os.getenv("OPENCORPORATES_API_KEY")
        self.session = SessionManager.get_session("opencorporates")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (API key is optional)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to OpenCorporates API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            params = {}
            if self.api_key:
                params["api_token"] = self.api_key

            response = self.session.get(
                f"{self.BASE_URL}/jurisdictions",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "OpenCorporates", "authenticated": bool(self.api_key)},
                metadata={"source": "OpenCorporates", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"OpenCorporates connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to OpenCorporates API.

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
        if self.api_key:
            request_params["api_token"] = self.api_key

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def search_companies(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        limit: int = 30
    ) -> DataSourceResponse:
        """Search for companies.

        Args:
            query: Search query (company name)
            jurisdiction: Jurisdiction code (e.g., 'us_ca', 'gb')
            limit: Maximum number of results

        Returns:
            DataSourceResponse with search results
        """
        try:
            params = {"q": query, "per_page": limit}
            if jurisdiction:
                params["jurisdiction_code"] = jurisdiction

            data = self._make_request("companies/search", params=params)

            companies = data.get("results", {}).get("companies", [])
            return DataSourceResponse.success_response(
                data=companies,
                metadata={
                    "source": "OpenCorporates",
                    "query": query,
                    "count": len(companies)
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenCorporates", "search_companies")

    def get_company(
        self,
        jurisdiction: str,
        company_number: str
    ) -> DataSourceResponse:
        """Get company details.

        Args:
            jurisdiction: Jurisdiction code (e.g., 'us_ca', 'gb')
            company_number: Company registration number

        Returns:
            DataSourceResponse with company details
        """
        try:
            data = self._make_request(f"companies/{jurisdiction}/{company_number}")

            company = data.get("results", {}).get("company", {})
            return DataSourceResponse.success_response(
                data=company,
                metadata={
                    "source": "OpenCorporates",
                    "jurisdiction": jurisdiction,
                    "company_number": company_number
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenCorporates", "get_company")

    def get_company_officers(
        self,
        jurisdiction: str,
        company_number: str
    ) -> DataSourceResponse:
        """Get company officers.

        Args:
            jurisdiction: Jurisdiction code
            company_number: Company registration number

        Returns:
            DataSourceResponse with officer list
        """
        try:
            data = self._make_request(f"companies/{jurisdiction}/{company_number}/officers")

            officers = data.get("results", {}).get("officers", [])
            return DataSourceResponse.success_response(
                data=officers,
                metadata={
                    "source": "OpenCorporates",
                    "jurisdiction": jurisdiction,
                    "company_number": company_number,
                    "count": len(officers)
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenCorporates", "get_company_officers")

    def get_jurisdictions(self) -> DataSourceResponse:
        """Get list of available jurisdictions.

        Returns:
            DataSourceResponse with jurisdiction list
        """
        try:
            data = self._make_request("jurisdictions")

            jurisdictions = data.get("results", {}).get("jurisdictions", [])
            return DataSourceResponse.success_response(
                data=jurisdictions,
                metadata={
                    "source": "OpenCorporates",
                    "count": len(jurisdictions)
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenCorporates", "get_jurisdictions")

    def search_officers(
        self,
        query: str,
        limit: int = 30
    ) -> DataSourceResponse:
        """Search for company officers.

        Args:
            query: Search query (officer name)
            limit: Maximum number of results

        Returns:
            DataSourceResponse with search results
        """
        try:
            params = {"q": query, "per_page": limit}
            data = self._make_request("officers/search", params=params)

            officers = data.get("results", {}).get("officers", [])
            return DataSourceResponse.success_response(
                data=officers,
                metadata={
                    "source": "OpenCorporates",
                    "query": query,
                    "count": len(officers)
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenCorporates", "search_officers")
