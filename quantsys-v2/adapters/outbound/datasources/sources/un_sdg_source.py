"""UN SDG (Sustainable Development Goals) data source.

Provides access to UN Sustainable Development Goals indicators and data.

API Documentation: https://unstats.un.org/sdgapi/swagger/
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class UNSDGSource(EconomicDataSource):
    """UN Sustainable Development Goals data source.

    Provides access to:
    - 17 SDG goals
    - 169 targets
    - 232 indicators
    - Country-level data
    - Time series data
    - Goal progress tracking

    No API key required.
    """

    BASE_URL = "https://unstats.un.org/sdgapi/v1"

    # 17 SDG Goals
    GOALS = {
        1: "No Poverty",
        2: "Zero Hunger",
        3: "Good Health and Well-being",
        4: "Quality Education",
        5: "Gender Equality",
        6: "Clean Water and Sanitation",
        7: "Affordable and Clean Energy",
        8: "Decent Work and Economic Growth",
        9: "Industry, Innovation and Infrastructure",
        10: "Reduced Inequalities",
        11: "Sustainable Cities and Communities",
        12: "Responsible Consumption and Production",
        13: "Climate Action",
        14: "Life Below Water",
        15: "Life on Land",
        16: "Peace, Justice and Strong Institutions",
        17: "Partnerships for the Goals"
    }

    def __init__(self):
        """Initialize UN SDG data source."""
        super().__init__(name="UN_SDG", requires_api_key=False)
        self.session = SessionManager.get_session("un_sdg")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to UN SDG API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/sdg/Goal/List",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "UN_SDG"},
                metadata={"source": "UN_SDG", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"UN SDG connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make request to UN SDG API.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_goals(self) -> DataSourceResponse:
        """Get list of all SDG goals.

        Returns:
            DataSourceResponse with goal list
        """
        try:
            data = self._make_request("sdg/Goal/List")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UN_SDG",
                    "count": len(data) if isinstance(data, list) else 0
                }
            )
        except Exception as e:
            return handle_request_error(e, "UN_SDG", "get_goals")

    def get_goal(self, goal_code: int) -> DataSourceResponse:
        """Get details for a specific goal.

        Args:
            goal_code: Goal number (1-17)

        Returns:
            DataSourceResponse with goal details
        """
        try:
            if goal_code < 1 or goal_code > 17:
                return DataSourceResponse.error_response(
                    error=f"Invalid goal code: {goal_code}. Must be 1-17."
                )

            data = self._make_request(f"sdg/Goal/{goal_code}")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UN_SDG",
                    "goal_code": goal_code,
                    "goal_name": self.GOALS.get(goal_code)
                }
            )
        except Exception as e:
            return handle_request_error(e, "UN_SDG", "get_goal")

    def get_targets(self, goal_code: Optional[int] = None) -> DataSourceResponse:
        """Get SDG targets.

        Args:
            goal_code: Goal number (optional, returns all if not specified)

        Returns:
            DataSourceResponse with target list
        """
        try:
            if goal_code:
                endpoint = f"sdg/Goal/{goal_code}/Target/List"
            else:
                endpoint = "sdg/Target/List"

            data = self._make_request(endpoint)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UN_SDG",
                    "goal_code": goal_code,
                    "count": len(data) if isinstance(data, list) else 0
                }
            )
        except Exception as e:
            return handle_request_error(e, "UN_SDG", "get_targets")

    def get_indicators(
        self,
        goal_code: Optional[int] = None,
        target_code: Optional[str] = None
    ) -> DataSourceResponse:
        """Get SDG indicators.

        Args:
            goal_code: Goal number (optional)
            target_code: Target code (optional, e.g., '1.1')

        Returns:
            DataSourceResponse with indicator list
        """
        try:
            if target_code:
                endpoint = f"sdg/Target/{target_code}/Indicator/List"
            elif goal_code:
                endpoint = f"sdg/Goal/{goal_code}/Indicator/List"
            else:
                endpoint = "sdg/Indicator/List"

            data = self._make_request(endpoint)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UN_SDG",
                    "goal_code": goal_code,
                    "target_code": target_code,
                    "count": len(data) if isinstance(data, list) else 0
                }
            )
        except Exception as e:
            return handle_request_error(e, "UN_SDG", "get_indicators")

    def get_indicator_data(
        self,
        indicator_code: str,
        area_code: Optional[str] = None
    ) -> DataSourceResponse:
        """Get data for a specific indicator.

        Args:
            indicator_code: Indicator code (e.g., '1.1.1')
            area_code: Country/area code (optional)

        Returns:
            DataSourceResponse with indicator data
        """
        try:
            endpoint = f"sdg/Indicator/{indicator_code}/Data"
            params = {}
            if area_code:
                params["areaCode"] = area_code

            data = self._make_request(endpoint, params=params)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UN_SDG",
                    "indicator_code": indicator_code,
                    "area_code": area_code
                }
            )
        except Exception as e:
            return handle_request_error(e, "UN_SDG", "get_indicator_data")

    def get_geo_areas(self) -> DataSourceResponse:
        """Get list of geographic areas.

        Returns:
            DataSourceResponse with area list
        """
        try:
            data = self._make_request("sdg/GeoArea/List")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UN_SDG",
                    "count": len(data) if isinstance(data, list) else 0
                }
            )
        except Exception as e:
            return handle_request_error(e, "UN_SDG", "get_geo_areas")

    def get_country_data(
        self,
        area_code: str,
        goal_code: Optional[int] = None
    ) -> DataSourceResponse:
        """Get SDG data for a specific country.

        Args:
            area_code: Country/area code
            goal_code: Goal number (optional)

        Returns:
            DataSourceResponse with country data
        """
        try:
            if goal_code:
                endpoint = f"sdg/Goal/{goal_code}/GeoArea/{area_code}/Data"
            else:
                endpoint = f"sdg/GeoArea/{area_code}/Data"

            data = self._make_request(endpoint)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UN_SDG",
                    "area_code": area_code,
                    "goal_code": goal_code
                }
            )
        except Exception as e:
            return handle_request_error(e, "UN_SDG", "get_country_data")
