"""SWIFT / ISO 20022 payment systems data source.

Provides access to payment systems statistics, cross-border transactions,
and financial messaging data.

No official public API - uses available public data from various sources.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class SWIFTSource(EconomicDataSource):
    """SWIFT/ISO 20022 payment systems data source.

    Provides access to:
    - Cross-border payment statistics
    - Currency usage data
    - Payment system metrics
    - Financial crime compliance
    - ISO 20022 adoption data

    No API key required (public data from BIS/CPMI).
    """

    BASE_URL = "https://www.bis.org/statistics"

    # BIS CPMI datasets
    DATASETS = {
        "cpmi_red_book": "payment-red-book",
        "cpmi_red_book_indicators": "payment-red-book/indicators",
        "cpmi_statistics": "payment-statistics",
        "cpmi_cyber": "payment-cyber"
    }

    def __init__(self):
        """Initialize SWIFT/Payments data source."""
        super().__init__(name="SWIFT", requires_api_key=False)
        self.session = SessionManager.get_session("swift")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to BIS statistics.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/cpmi/data_feed.htm",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "BIS_CPMI"},
                metadata={"source": "BIS_CPMI", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"BIS CPMI connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_red_book_data(self) -> DataSourceResponse:
        """Get CPMI Red Book payment statistics.

        Returns:
            DataSourceResponse with payment statistics
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/cpmi/publ/d97.csv",
                timeout=30
            )

            if response.status_code == 200:
                return DataSourceResponse.success_response(
                    data={
                        "url": f"{self.BASE_URL}/cpmi/publ/d97.csv",
                        "description": "CPMI Red Book - payment systems statistics",
                        "note": "CSV data download or parse directly"
                    },
                    metadata={
                        "source": "BIS_CPMI",
                        "dataset": "red_book"
                    }
                )
            else:
                return DataSourceResponse.error_response(
                    error=f"Failed to fetch Red Book data: HTTP {response.status_code}"
                )
        except Exception as e:
            return handle_request_error(e, "SWIFT/Payments", "get_red_book_data")

    def get_payment_indicators(self) -> DataSourceResponse:
        """Get payment system indicators.

        Returns:
            DataSourceResponse with payment indicators
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/cpmi/data_feed.htm",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.BASE_URL}/cpmi/data_feed.htm",
                    "description": "CPMI data feed - latest payment indicators",
                    "indicators": [
                        "Number of cashless payments",
                        "Value of cashless payments",
                        "ATM and POS terminals",
                        "Cards in circulation",
                        "Payment system infrastructure"
                    ],
                    "note": "HTML parsing required for structured data"
                },
                metadata={
                    "source": "BIS_CPMI",
                    "dataset": "indicators"
                }
            )
        except Exception as e:
            return handle_request_error(e, "SWIFT/Payments", "get_payment_indicators")

    def get_datasets(self) -> DataSourceResponse:
        """Get list of available payment datasets.

        Returns:
            DataSourceResponse with dataset list
        """
        datasets = [
            {"key": key, "name": name}
            for key, name in self.DATASETS.items()
        ]

        return DataSourceResponse.success_response(
            data=datasets,
            metadata={
                "source": "BIS_CPMI",
                "count": len(datasets)
            }
        )
