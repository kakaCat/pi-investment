"""WITS (World Integrated Trade Solution) data source.

Provides access to international trade, tariff, and non-tariff measures data.

API Documentation: https://wits.worldbank.org/
No API key required (public data).
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class WITSSource(EconomicDataSource):
    """World Integrated Trade Solution data source.

    Provides access to:
    - International trade flows (import/export)
    - Tariff data (MFN, preferential, bound)
    - Non-tariff measures
    - Trade competitiveness
    - Market access indicators
    - Trade agreements

    No API key required.
    """

    BASE_URL = "https://wits.worldbank.org/API/V1"

    # Common reporters (countries/regions)
    REGIONS = [
        "WLD",  # World
        "EAS",  # East Asia & Pacific
        "ECS",  # Europe & Central Asia
        "LCN",  # Latin America & Caribbean
        "MEA",  # Middle East & North Africa
        "SAS",  # South Asia
        "SSF",  # Sub-Saharan Africa
        "USA", "CHN", "JPN", "DEU", "GBR", "FRA", "IND", "BRA", "RUS", "CAN"
    ]

    def __init__(self):
        """Initialize WITS data source."""
        super().__init__(name="WITS", requires_api_key=False)
        self.session = SessionManager.get_session("wits")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to WITS API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/wits/datasource/TRN/country/ALL/partner/ALL/product/ALL/indicator/MPRT-TRD-VL/year/2022",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "WITS"},
                metadata={"source": "WITS", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"WITS connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make request to WITS API.

        Args:
            endpoint: API endpoint path

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_trade_flows(
        self,
        reporter: str = "CHN",
        partner: str = "ALL",
        year: int = 2022
    ) -> DataSourceResponse:
        """Get trade flow data.

        Args:
            reporter: Reporter country/region code
            partner: Partner country code ('ALL' for all)
            year: Year for trade data

        Returns:
            DataSourceResponse with trade data
        """
        try:
            endpoint = (
                f"wits/datasource/TRN/country/{reporter}/partner/{partner}"
                f"/product/ALL/indicator/MPRT-TRD-VL/year/{year}"
            )

            data = self._make_request(endpoint)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "WITS",
                    "reporter": reporter,
                    "partner": partner,
                    "year": year,
                    "indicator": "import_value"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WITS", "get_trade_flows")

    def get_tariff_data(
        self,
        reporter: str = "CHN",
        year: int = 2022
    ) -> DataSourceResponse:
        """Get tariff data.

        Args:
            reporter: Reporter country code
            year: Year for tariff data

        Returns:
            DataSourceResponse with tariff data
        """
        try:
            endpoint = (
                f"wits/datasource/TRN/country/{reporter}/partner/ALL"
                f"/product/ALL/indicator/AHS-SMPL-AVR/year/{year}"
            )

            data = self._make_request(endpoint)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "WITS",
                    "reporter": reporter,
                    "year": year,
                    "indicator": "applied_tariff"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WITS", "get_tariff_data")

    def get_regions(self) -> DataSourceResponse:
        """Get list of regions and countries.

        Returns:
            DataSourceResponse with region list
        """
        return DataSourceResponse.success_response(
            data=self.REGIONS,
            metadata={
                "source": "WITS",
                "count": len(self.REGIONS)
            }
        )

    def get_market_access(
        self,
        exporter: str = "CHN",
        importer: str = "USA",
        year: int = 2022
    ) -> DataSourceResponse:
        """Get market access indicators.

        Args:
            exporter: Exporting country
            importer: Importing country
            year: Year

        Returns:
            DataSourceResponse with market access data
        """
        try:
            endpoint = (
                f"wits/datasource/TRN/country/{importer}/partner/{exporter}"
                f"/product/ALL/indicator/AHS-AVR-TRFF/year/{year}"
            )

            data = self._make_request(endpoint)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "WITS",
                    "exporter": exporter,
                    "importer": importer,
                    "year": year,
                    "indicator": "market_access"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WITS", "get_market_access")
