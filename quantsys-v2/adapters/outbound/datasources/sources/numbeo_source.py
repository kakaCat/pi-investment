"""Numbeo cost of living data source.

Provides access to cost of living, property prices, and quality of life data
for cities worldwide.

API Documentation: https://www.numbeo.com/api/doc.jsp
Requires API key: https://www.numbeo.com/common/api.jsp
"""

from typing import Optional, Dict, Any, List
import logging
import os

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class NumbeoSource(EconomicDataSource):
    """Numbeo cost of living data source.

    Provides access to:
    - Cost of living indices
    - Property prices
    - Crime statistics
    - Healthcare quality
    - Pollution levels
    - Traffic data
    - Quality of life indices

    Requires API key.
    """

    BASE_URL = "https://www.numbeo.com/api"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Numbeo data source.

        Args:
            api_key: Numbeo API key (or set NUMBEO_API_KEY env var)
        """
        super().__init__(name="Numbeo", requires_api_key=True)
        self.api_key = api_key or os.getenv("NUMBEO_API_KEY")
        self.session = SessionManager.get_session("numbeo")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True if API key is configured
        """
        if not self.api_key:
            logger.error("Numbeo API key not configured")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Numbeo API.

        Returns:
            DataSourceResponse with connection status
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(
                error="API key not configured. Set NUMBEO_API_KEY environment variable."
            )

        try:
            response = self.session.get(
                f"{self.BASE_URL}/cities",
                params={"api_key": self.api_key},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Numbeo"},
                metadata={"source": "Numbeo", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Numbeo connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make request to Numbeo API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        request_params = {"api_key": self.api_key}
        if params:
            request_params.update(params)

        response = self.session.get(url, params=request_params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_cities(self) -> DataSourceResponse:
        """Get list of available cities.

        Returns:
            DataSourceResponse with city list
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            data = self._make_request("cities")

            return DataSourceResponse.success_response(
                data=data.get("cities", []),
                metadata={
                    "source": "Numbeo",
                    "count": len(data.get("cities", []))
                }
            )
        except Exception as e:
            return handle_request_error(e, "Numbeo", "get_cities")

    def get_city_prices(
        self,
        city: str,
        country: Optional[str] = None
    ) -> DataSourceResponse:
        """Get prices for a city.

        Args:
            city: City name
            country: Country name (optional)

        Returns:
            DataSourceResponse with price data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"query": city}
            if country:
                params["country"] = country

            data = self._make_request("city_prices", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Numbeo",
                    "city": city,
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "Numbeo", "get_city_prices")

    def get_cost_of_living(
        self,
        city: str,
        country: Optional[str] = None
    ) -> DataSourceResponse:
        """Get cost of living index for a city.

        Args:
            city: City name
            country: Country name (optional)

        Returns:
            DataSourceResponse with cost of living data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"query": city}
            if country:
                params["country"] = country

            data = self._make_request("indices", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Numbeo",
                    "city": city,
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "Numbeo", "get_cost_of_living")

    def get_property_prices(
        self,
        city: str,
        country: Optional[str] = None
    ) -> DataSourceResponse:
        """Get property prices for a city.

        Args:
            city: City name
            country: Country name (optional)

        Returns:
            DataSourceResponse with property price data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"query": city}
            if country:
                params["country"] = country

            data = self._make_request("city_property_prices", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Numbeo",
                    "city": city,
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "Numbeo", "get_property_prices")

    def compare_cities(
        self,
        city1: str,
        city2: str,
        country1: Optional[str] = None,
        country2: Optional[str] = None
    ) -> DataSourceResponse:
        """Compare cost of living between two cities.

        Args:
            city1: First city name
            city2: Second city name
            country1: First country name (optional)
            country2: Second country name (optional)

        Returns:
            DataSourceResponse with comparison data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {
                "city1": city1,
                "city2": city2
            }
            if country1:
                params["country1"] = country1
            if country2:
                params["country2"] = country2

            data = self._make_request("city_comparison", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Numbeo",
                    "city1": city1,
                    "city2": city2
                }
            )
        except Exception as e:
            return handle_request_error(e, "Numbeo", "compare_cities")

    def get_country_data(self, country: str) -> DataSourceResponse:
        """Get aggregated data for a country.

        Args:
            country: Country name

        Returns:
            DataSourceResponse with country data
        """
        if not self.validate_config():
            return DataSourceResponse.error_response(error="API key not configured")

        try:
            params = {"country": country}
            data = self._make_request("country_indices", params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Numbeo",
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "Numbeo", "get_country_data")
