"""Fitch Connect credit ratings and research data source.

Provides access to credit ratings, macroeconomic data, and financial research.

API Documentation: https://www.fitchconnect.com/
Requires API key (enterprise subscription).
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class FitchConnectSource(EconomicDataSource):
    """Fitch Connect credit ratings and research data source.

    Provides access to:
    - Credit ratings (sovereign, corporate, financial institutions)
    - Macroeconomic forecasts
    - Country risk data
    - Industry research
    - Fundamentals data
    - Rating actions and reports

    Requires API key (enterprise subscription).
    """

    BASE_URL = "https://api.fitchconnect.com/v1"

    # Rating agencies covered
    RATING_AGENCIES = ["Fitch", "Moody's", "S&P", "DBRS"]

    # Rating scales
    RATING_SCALES = {
        "AAA": "Highest credit quality",
        "AA+": "Very high credit quality",
        "AA": "Very high credit quality",
        "AA-": "Very high credit quality",
        "A+": "High credit quality",
        "A": "High credit quality",
        "A-": "High credit quality",
        "BBB+": "Good credit quality",
        "BBB": "Good credit quality",
        "BBB-": "Good credit quality",
        "BB+": "Speculative",
        "BB": "Speculative",
        "BB-": "Speculative",
        "B+": "Highly speculative",
        "B": "Highly speculative",
        "B-": "Highly speculative",
        "CCC": "Substantial risk",
        "CC": "Very high risk",
        "C": "Near default",
        "D": "Default"
    }

    def __init__(self, api_key: Optional[str] = None, client_id: Optional[str] = None):
        """Initialize Fitch Connect data source.

        Args:
            api_key: Fitch Connect API key (or set FITCH_API_KEY env var)
            client_id: Fitch Connect client ID (or set FITCH_CLIENT_ID env var)
        """
        super().__init__(name="FitchConnect", requires_api_key=True)
        self.api_key = api_key or os.getenv("FITCH_API_KEY")
        self.client_id = client_id or os.getenv("FITCH_CLIENT_ID")
        self.session = SessionManager.get_session("fitch")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key and client ID are configured
        """
        if not self.api_key or not self.client_id:
            logger.error("Fitch Connect credentials not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Fitch Connect API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="Credentials not configured. Set FITCH_API_KEY and FITCH_CLIENT_ID environment variables."
            )

        try:
            headers = {
                "X-API-KEY": self.api_key,
                "X-CLIENT-ID": self.client_id
            }

            response = self.session.get(
                f"{self.BASE_URL}/ratings/sovereign",
                headers=headers,
                params={"limit": 1},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "FitchConnect"},
                metadata={"source": "FitchConnect", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Fitch Connect connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make request to Fitch Connect API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "X-API-KEY": self.api_key,
            "X-CLIENT-ID": self.client_id
        }

        response = self.session.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_rating_scales(self) -> DataSourceResponse:
        """Get rating scales explanation.

        Returns:
            DataSourceResponse with rating scales
        """
        scales = [
            {"rating": rating, "description": desc}
            for rating, desc in self.RATING_SCALES.items()
        ]

        return DataSourceResponse.success_response(
            data=scales,
            metadata={"source": "FitchConnect", "count": len(scales)}
        )

    def get_sovereign_ratings(
        self,
        country: Optional[str] = None,
        limit: int = 100
    ) -> DataSourceResponse:
        """Get sovereign credit ratings.

        Args:
            country: Country ISO code (optional)
            limit: Maximum number of results

        Returns:
            DataSourceResponse with sovereign ratings
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Credentials not configured")

        try:
            params = {"limit": limit}
            if country:
                params["country"] = country

            data = self._make_request("ratings/sovereign", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FitchConnect",
                    "country": country,
                    "dataset": "sovereign_ratings"
                }
            )
        except Exception as e:
            return handle_request_error(e, "FitchConnect", "get_sovereign_ratings")

    def get_corporate_ratings(
        self,
        sector: Optional[str] = None,
        limit: int = 100
    ) -> DataSourceResponse:
        """Get corporate credit ratings.

        Args:
            sector: Industry sector (optional)
            limit: Maximum number of results

        Returns:
            DataSourceResponse with corporate ratings
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Credentials not configured")

        try:
            params = {"limit": limit}
            if sector:
                params["sector"] = sector

            data = self._make_request("ratings/corporate", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FitchConnect",
                    "sector": sector,
                    "dataset": "corporate_ratings"
                }
            )
        except Exception as e:
            return handle_request_error(e, "FitchConnect", "get_corporate_ratings")

    def get_macro_forecasts(
        self,
        country: Optional[str] = None,
        indicator: Optional[str] = None
    ) -> DataSourceResponse:
        """Get macroeconomic forecasts.

        Args:
            country: Country ISO code (optional)
            indicator: Economic indicator (optional, e.g., 'GDP', 'CPI')

        Returns:
            DataSourceResponse with macro forecasts
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Credentials not configured")

        try:
            params = {}
            if country:
                params["country"] = country
            if indicator:
                params["indicator"] = indicator

            data = self._make_request("macro/forecasts", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FitchConnect",
                    "country": country,
                    "indicator": indicator,
                    "dataset": "macro_forecasts"
                }
            )
        except Exception as e:
            return handle_request_error(e, "FitchConnect", "get_macro_forecasts")

    def get_country_risk(
        self,
        country: Optional[str] = None
    ) -> DataSourceResponse:
        """Get country risk assessment data.

        Args:
            country: Country ISO code (optional)

        Returns:
            DataSourceResponse with country risk data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Credentials not configured")

        try:
            params = {}
            if country:
                params["country"] = country

            data = self._make_request("risk/country", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FitchConnect",
                    "country": country,
                    "dataset": "country_risk"
                }
            )
        except Exception as e:
            return handle_request_error(e, "FitchConnect", "get_country_risk")

    def get_industry_research(
        self,
        industry: Optional[str] = None,
        limit: int = 50
    ) -> DataSourceResponse:
        """Get industry research reports.

        Args:
            industry: Industry name (optional)
            limit: Maximum number of results

        Returns:
            DataSourceResponse with research data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="Credentials not configured")

        try:
            params = {"limit": limit}
            if industry:
                params["industry"] = industry

            data = self._make_request("research/industry", params=params)

            return DataSourceResponse.success_response(
                data=data.get("data", []),
                metadata={
                    "source": "FitchConnect",
                    "industry": industry,
                    "dataset": "industry_research"
                }
            )
        except Exception as e:
            return handle_request_error(e, "FitchConnect", "get_industry_research")
