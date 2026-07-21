"""FRED (Federal Reserve Economic Data) source.

Provides access to US economic data from the Federal Reserve Bank of St. Louis.
Inspired by FinceptTerminal's fred_data.py implementation.
"""

from typing import Optional, List, Dict, Any
import json
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.config import get_fred_api_key
from adapters.outbound.datasources.error_handler import normalize_date, safe_call

logger = logging.getLogger(__name__)


class FREDSource(EconomicDataSource):
    """FRED economic data source.

    Requires FRED_API_KEY environment variable.
    Get your free API key at: https://fred.stlouisfed.org/docs/api/api_key.html
    """

    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self):
        super().__init__(name="FRED", requires_api_key=True)
        self.api_key = get_fred_api_key()
        self.session = SessionManager.get_session("fred")

    def validate_config(self) -> bool:
        """Validate FRED API key is configured."""
        if not self.api_key:
            self.logger.error(
                "FRED API key not configured. "
                "Set FRED_API_KEY environment variable. "
                "Get your key at: https://fred.stlouisfed.org/docs/api/api_key.html"
            )
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test FRED API connection."""
        if not self.validate_config():
            return DataSourceResponse.error_response("FRED API key not configured")

        try:
            # Test with a simple series request (GDP)
            result = self._make_request("series", {"series_id": "GDP"})
            if "error" in result:
                return DataSourceResponse.error_response(result["error"])

            return DataSourceResponse.success_response(
                {"status": "connected", "test": "passed"},
                metadata={"source": "fred"}
            )
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: Optional[str] = None,
        transform: Optional[str] = None
    ) -> DataSourceResponse:
        """Fetch FRED series data.

        Args:
            series_id: FRED series ID (e.g., 'GDP', 'UNRATE', 'CPIAUCSL')
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)
            frequency: a=Annual, q=Quarterly, m=Monthly, w=Weekly, d=Daily (optional)
            transform: chg=Change, pch=Percent Change, log=Natural Log (optional)

        Returns:
            DataSourceResponse with series data and metadata
        """
        self._log_request("get_series", {
            "series_id": series_id,
            "start_date": start_date,
            "end_date": end_date,
            "frequency": frequency,
            "transform": transform
        })

        if not self.validate_config():
            return DataSourceResponse.error_response("FRED API key not configured")

        try:
            # Build parameters
            params = {"series_id": series_id}
            if start_date:
                params["observation_start"] = start_date
            if end_date:
                params["observation_end"] = end_date
            if frequency:
                params["frequency"] = frequency
            if transform:
                params["units"] = transform

            # Get observations
            obs_data = self._make_request("series/observations", params)
            if "error" in obs_data:
                return DataSourceResponse.error_response(obs_data["error"])

            # Get series metadata
            metadata_result = self._make_request("series", {"series_id": series_id})
            series_info = metadata_result.get("seriess", [{}])[0] if "seriess" in metadata_result else {}

            # Format observations
            observations = []
            for obs in obs_data.get("observations", []):
                if obs.get("value") != ".":  # Skip missing values
                    try:
                        observations.append({
                            "date": obs["date"],
                            "value": float(obs["value"])
                        })
                    except (ValueError, KeyError):
                        continue

            result = {
                "series_id": series_id,
                "title": series_info.get("title", "N/A"),
                "units": series_info.get("units", "N/A"),
                "frequency": series_info.get("frequency", "N/A"),
                "seasonal_adjustment": series_info.get("seasonal_adjustment", "N/A"),
                "last_updated": series_info.get("last_updated", "N/A"),
                "observations": observations,
                "observation_count": len(observations)
            }

            self._log_success("get_series", len(observations))
            return DataSourceResponse.success_response(
                result,
                metadata={"series_id": series_id}
            )

        except Exception as e:
            return self._handle_error("get_series", e)

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for FRED series.

        Args:
            query: Search query text
            limit: Maximum number of results (default 10)

        Returns:
            DataSourceResponse with search results
        """
        self._log_request("search_series", {"query": query, "limit": limit})

        if not self.validate_config():
            return DataSourceResponse.error_response("FRED API key not configured")

        try:
            params = {
                "search_text": query,
                "limit": limit,
                "order_by": "popularity",
                "sort_order": "desc"
            }

            result = self._make_request("series/search", params)
            if "error" in result:
                return DataSourceResponse.error_response(result["error"])

            series_list = []
            for series in result.get("seriess", []):
                series_list.append({
                    "id": series.get("id"),
                    "title": series.get("title"),
                    "frequency": series.get("frequency"),
                    "units": series.get("units"),
                    "seasonal_adjustment": series.get("seasonal_adjustment"),
                    "last_updated": series.get("last_updated"),
                    "popularity": series.get("popularity", 0)
                })

            self._log_success("search_series", len(series_list))
            return DataSourceResponse.success_response(
                series_list,
                metadata={"query": query}
            )

        except Exception as e:
            return self._handle_error("search_series", e)

    def get_categories(self, category_id: Optional[int] = None) -> DataSourceResponse:
        """Get FRED categories.

        Args:
            category_id: Category ID (None for root categories)

        Returns:
            DataSourceResponse with category list
        """
        self._log_request("get_categories", {"category_id": category_id})

        if not self.validate_config():
            return DataSourceResponse.error_response("FRED API key not configured")

        try:
            endpoint = "category/children" if category_id else "category"
            params = {"category_id": category_id} if category_id else {}

            result = self._make_request(endpoint, params)
            if "error" in result:
                return DataSourceResponse.error_response(result["error"])

            categories = result.get("categories", [])
            self._log_success("get_categories", len(categories))
            return DataSourceResponse.success_response(categories)

        except Exception as e:
            return self._handle_error("get_categories", e)

    def get_release_series(self, release_id: int) -> DataSourceResponse:
        """Get series for a specific release.

        Args:
            release_id: FRED release ID

        Returns:
            DataSourceResponse with series list
        """
        self._log_request("get_release_series", {"release_id": release_id})

        if not self.validate_config():
            return DataSourceResponse.error_response("FRED API key not configured")

        try:
            result = self._make_request("release/series", {"release_id": release_id})
            if "error" in result:
                return DataSourceResponse.error_response(result["error"])

            series_list = result.get("seriess", [])
            self._log_success("get_release_series", len(series_list))
            return DataSourceResponse.success_response(series_list)

        except Exception as e:
            return self._handle_error("get_release_series", e)

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict:
        """Make request to FRED API using connection pool.

        Args:
            endpoint: API endpoint (e.g., "series/observations")
            params: Query parameters

        Returns:
            JSON response as dict
        """
        params["api_key"] = self.api_key
        params["file_type"] = "json"

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=15)

            # Handle specific HTTP errors
            if response.status_code in (401, 403):
                return {
                    "error": f"FRED rejected the API key (HTTP {response.status_code})",
                    "error_code": "INVALID_API_KEY"
                }

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                return {
                    "error": f"FRED rate limit hit. Retry in ~{retry_after}s",
                    "error_code": "RATE_LIMITED",
                    "retry_after": int(retry_after)
                }

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"FRED API request failed: {e}")
            return {"error": str(e), "error_code": "REQUEST_FAILED"}


# Popular FRED series IDs for quick reference
POPULAR_SERIES = {
    # GDP & Growth
    "GDP": "Gross Domestic Product",
    "GDPC1": "Real Gross Domestic Product",
    "GDPPOT": "Real Potential Gross Domestic Product",

    # Employment
    "UNRATE": "Unemployment Rate",
    "PAYEMS": "All Employees, Total Nonfarm",
    "CIVPART": "Labor Force Participation Rate",

    # Inflation
    "CPIAUCSL": "Consumer Price Index for All Urban Consumers",
    "CPILFESL": "Consumer Price Index for All Urban Consumers: All Items Less Food and Energy",
    "PCEPI": "Personal Consumption Expenditures: Chain-type Price Index",

    # Interest Rates
    "DFF": "Federal Funds Effective Rate",
    "DGS10": "10-Year Treasury Constant Maturity Rate",
    "DGS2": "2-Year Treasury Constant Maturity Rate",
    "T10Y2Y": "10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity",

    # Money Supply
    "M1SL": "M1 Money Stock",
    "M2SL": "M2 Money Stock",

    # Housing
    "HOUST": "Housing Starts: Total: New Privately Owned Housing Units Started",
    "MORTGAGE30US": "30-Year Fixed Rate Mortgage Average in the United States",

    # Consumer
    "RSXFS": "Advance Retail Sales: Retail Trade and Food Services",
    "UMCSENT": "University of Michigan: Consumer Sentiment",
}
