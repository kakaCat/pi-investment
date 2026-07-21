"""OpenSecrets political donations data source.

Provides access to US political campaign finance data including donations,
lobbying, and PAC contributions.

API Documentation: https://www.opensecrets.org/api/
Requires API key: https://www.opensecrets.org/api/admin/index.php?function=signup
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class OpenSecretsSource(EconomicDataSource):
    """OpenSecrets political finance data source.

    Provides access to:
    - Campaign contributions
    - Lobbying data
    - PAC contributions
    - Legislator profiles
    - Industry contributions
    - Organization donations

    Requires API key.
    """

    BASE_URL = "https://www.opensecrets.org/api"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenSecrets data source.

        Args:
            api_key: OpenSecrets API key (or set OPENSECRETS_API_KEY env var)
        """
        super().__init__(name="OpenSecrets", requires_api_key=True)
        self.api_key = api_key or os.getenv("OPENSECRETS_API_KEY")
        self.session = SessionManager.get_session("opensecrets")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("OpenSecrets API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to OpenSecrets API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set OPENSECRETS_API_KEY environment variable."
            )

        try:
            response = self.session.get(
                f"{self.BASE_URL}/",
                params={
                    "method": "getLegislators",
                    "id": "CA",
                    "apikey": self.api_key,
                    "output": "json"
                },
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "OpenSecrets"},
                metadata={"source": "OpenSecrets", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"OpenSecrets connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to OpenSecrets API.

        Args:
            method: API method name
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        request_params = {
            "method": method,
            "apikey": self.api_key,
            "output": "json"
        }
        if params:
            request_params.update(params)

        response = self.session.get(self.BASE_URL, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_legislators(self, state: str) -> DataSourceResponse:
        """Get legislators for a state.

        Args:
            state: Two-letter state code (e.g., 'CA', 'NY')

        Returns:
            DataSourceResponse with legislator list
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request("getLegislators", params={"id": state})

            return DataSourceResponse.success_response(
                data=data.get("response", {}).get("legislator", []),
                metadata={
                    "source": "OpenSecrets",
                    "state": state
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenSecrets", "get_legislators")

    def get_candidate_summary(self, cid: str, cycle: Optional[str] = None) -> DataSourceResponse:
        """Get candidate financial summary.

        Args:
            cid: Candidate ID
            cycle: Election cycle year (e.g., '2020', '2022')

        Returns:
            DataSourceResponse with candidate summary
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"cid": cid}
            if cycle:
                params["cycle"] = cycle

            data = self._make_request("candSummary", params=params)

            return DataSourceResponse.success_response(
                data=data.get("response", {}).get("summary", {}),
                metadata={
                    "source": "OpenSecrets",
                    "cid": cid,
                    "cycle": cycle
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenSecrets", "get_candidate_summary")

    def get_candidate_contributors(
        self,
        cid: str,
        cycle: Optional[str] = None
    ) -> DataSourceResponse:
        """Get top contributors to a candidate.

        Args:
            cid: Candidate ID
            cycle: Election cycle year

        Returns:
            DataSourceResponse with contributor data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"cid": cid}
            if cycle:
                params["cycle"] = cycle

            data = self._make_request("candContrib", params=params)

            return DataSourceResponse.success_response(
                data=data.get("response", {}).get("contributors", {}).get("contributor", []),
                metadata={
                    "source": "OpenSecrets",
                    "cid": cid,
                    "cycle": cycle
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenSecrets", "get_candidate_contributors")

    def get_candidate_industries(
        self,
        cid: str,
        cycle: Optional[str] = None
    ) -> DataSourceResponse:
        """Get top industries contributing to a candidate.

        Args:
            cid: Candidate ID
            cycle: Election cycle year

        Returns:
            DataSourceResponse with industry contribution data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"cid": cid}
            if cycle:
                params["cycle"] = cycle

            data = self._make_request("candIndustry", params=params)

            return DataSourceResponse.success_response(
                data=data.get("response", {}).get("industries", {}).get("industry", []),
                metadata={
                    "source": "OpenSecrets",
                    "cid": cid,
                    "cycle": cycle
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenSecrets", "get_candidate_industries")

    def get_organization_summary(self, org: str) -> DataSourceResponse:
        """Get organization donation summary.

        Args:
            org: Organization name or ID

        Returns:
            DataSourceResponse with organization summary
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request("getOrgs", params={"org": org})

            return DataSourceResponse.success_response(
                data=data.get("response", {}).get("organization", []),
                metadata={
                    "source": "OpenSecrets",
                    "org": org
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenSecrets", "get_organization_summary")

    def get_independent_expenditures(
        self,
        cid: Optional[str] = None,
        cycle: Optional[str] = None
    ) -> DataSourceResponse:
        """Get independent expenditure data.

        Args:
            cid: Candidate ID (optional)
            cycle: Election cycle year (optional)

        Returns:
            DataSourceResponse with independent expenditure data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {}
            if cid:
                params["cid"] = cid
            if cycle:
                params["cycle"] = cycle

            data = self._make_request("independentExpend", params=params)

            return DataSourceResponse.success_response(
                data=data.get("response", {}).get("indexp", []),
                metadata={
                    "source": "OpenSecrets",
                    "cid": cid,
                    "cycle": cycle
                }
            )
        except Exception as e:
            return handle_request_error(e, "OpenSecrets", "get_independent_expenditures")
