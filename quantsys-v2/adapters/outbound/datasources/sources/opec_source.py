"""OPEC (Organization of the Petroleum Exporting Countries) data source.

Provides access to oil production, prices, and market data.

API Documentation: https://www.opec.org/
Data scraped from public reports and statistics pages.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class OPECSource(EconomicDataSource):
    """OPEC data source.

    Provides access to:
    - Oil production data by country
    - OPEC basket price
    - Crude oil prices
    - Market reports
    - Supply and demand statistics

    No API key required (public data).
    """

    BASE_URL = "https://www.opec.org"
    DATA_URL = "https://www.opec.org/opec_web/en/data_graphs"

    # OPEC member countries
    MEMBERS = [
        "Algeria", "Angola", "Congo", "Equatorial Guinea", "Gabon", "Iran",
        "Iraq", "Kuwait", "Libya", "Nigeria", "Saudi Arabia", "UAE", "Venezuela"
    ]

    def __init__(self):
        """Initialize OPEC data source."""
        super().__init__(name="OPEC", requires_api_key=False)
        self.session = SessionManager.get_session("opec")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to OPEC website.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/opec_web/en/",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "OPEC"},
                metadata={"source": "OPEC", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"OPEC connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_basket_price(self) -> DataSourceResponse:
        """Get OPEC basket price (reference crude oil price).

        Returns:
            DataSourceResponse with basket price data
        """
        try:
            # OPEC basket price endpoint
            response = self.session.get(
                f"{self.DATA_URL}/4.htm",
                timeout=30
            )
            response.raise_for_status()

            # Note: This returns HTML, would need parsing
            # For now, return raw response info
            return DataSourceResponse.success_response(
                data={
                    "message": "OPEC basket price data available",
                    "url": f"{self.DATA_URL}/4.htm",
                    "note": "HTML parsing required for structured data"
                },
                metadata={
                    "source": "OPEC",
                    "data_type": "basket_price"
                }
            )
        except Exception as e:
            return handle_request_error(e, "OPEC", "get_basket_price")

    def get_production_data(self) -> DataSourceResponse:
        """Get OPEC production data by country.

        Returns:
            DataSourceResponse with production data
        """
        try:
            response = self.session.get(
                f"{self.DATA_URL}/60.htm",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "message": "OPEC production data available",
                    "url": f"{self.DATA_URL}/60.htm",
                    "members": self.MEMBERS,
                    "note": "HTML parsing required for structured data"
                },
                metadata={
                    "source": "OPEC",
                    "data_type": "production"
                }
            )
        except Exception as e:
            return handle_request_error(e, "OPEC", "get_production_data")

    def get_member_countries(self) -> DataSourceResponse:
        """Get list of OPEC member countries.

        Returns:
            DataSourceResponse with member country list
        """
        return DataSourceResponse.success_response(
            data=self.MEMBERS,
            metadata={
                "source": "OPEC",
                "count": len(self.MEMBERS)
            }
        )

    def get_market_report(self) -> DataSourceResponse:
        """Get latest monthly oil market report.

        Returns:
            DataSourceResponse with market report info
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/opec_web/en/publications/338.htm",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "message": "Monthly Oil Market Report available",
                    "url": f"{self.BASE_URL}/opec_web/en/publications/338.htm",
                    "note": "PDF download and parsing required"
                },
                metadata={
                    "source": "OPEC",
                    "data_type": "market_report"
                }
            )
        except Exception as e:
            return handle_request_error(e, "OPEC", "get_market_report")
