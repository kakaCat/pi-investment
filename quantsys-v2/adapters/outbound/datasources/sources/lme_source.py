"""LME (London Metal Exchange) data source.

Provides access to base metals and other commodity prices from the LME.

API Documentation: https://www.lme.com/
No official public API - uses public data endpoints.
"""

from typing import Optional, Dict, Any, List
import logging
from datetime import datetime

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class LMESource(EconomicDataSource):
    """London Metal Exchange data source.

    Provides access to:
    - Base metals (copper, aluminum, zinc, lead, nickel, tin)
    - Minor metals (cobalt, molybdenum)
    - Precious metals (gold, silver)
    - Settlement prices
    - Trading volumes
    - Open interest
    - Warehouse stocks

    No API key required (public data).
    """

    BASE_URL = "https://www.lme.com"
    DATA_URL = "https://www.lme.com/en/Market-Data"

    # LME metals
    METALS = {
        "CA": "Copper Grade A",
        "AH": "Aluminum",
        "ZS": "Zinc",
        "PB": "Lead",
        "NI": "Nickel",
        "SN": "Tin",
        "CO": "Cobalt",
        "MO": "Molybdenum",
        "LMAU": "Gold",
        "LMAG": "Silver"
    }

    # Contract types
    CONTRACT_TYPES = [
        "Cash",
        "3-Month",
        "15-Month",
        "27-Month"
    ]

    def __init__(self):
        """Initialize LME data source."""
        super().__init__(name="LME", requires_api_key=False)
        self.session = SessionManager.get_session("lme")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to LME website.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "LME"},
                metadata={"source": "LME", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"LME connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_metals(self) -> DataSourceResponse:
        """Get list of available metals.

        Returns:
            DataSourceResponse with metal list
        """
        metals = [
            {"code": code, "name": name}
            for code, name in self.METALS.items()
        ]

        return DataSourceResponse.success_response(
            data=metals,
            metadata={
                "source": "LME",
                "count": len(metals)
            }
        )

    def get_contract_types(self) -> DataSourceResponse:
        """Get list of contract types.

        Returns:
            DataSourceResponse with contract types
        """
        return DataSourceResponse.success_response(
            data=self.CONTRACT_TYPES,
            metadata={
                "source": "LME",
                "count": len(self.CONTRACT_TYPES)
            }
        )

    def get_prices(self, metal_code: Optional[str] = None) -> DataSourceResponse:
        """Get LME prices.

        Args:
            metal_code: Metal code (e.g., 'CA', 'AH') or None for all

        Returns:
            DataSourceResponse with price data
        """
        try:
            if metal_code and metal_code not in self.METALS:
                return DataSourceResponse.error_response(
                    error=f"Invalid metal code: {metal_code}. Valid: {list(self.METALS.keys())}"
                )

            response = self.session.get(
                f"{self.DATA_URL}/Pricing-data",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.DATA_URL}/Pricing-data",
                    "metal_code": metal_code,
                    "metal_name": self.METALS.get(metal_code) if metal_code else None,
                    "note": "HTML parsing or data download required for structured data"
                },
                metadata={
                    "source": "LME",
                    "metal_code": metal_code,
                    "data_type": "prices"
                }
            )
        except Exception as e:
            return handle_request_error(e, "LME", "get_prices")

    def get_volumes(self, metal_code: Optional[str] = None) -> DataSourceResponse:
        """Get trading volumes.

        Args:
            metal_code: Metal code (optional)

        Returns:
            DataSourceResponse with volume data
        """
        try:
            if metal_code and metal_code not in self.METALS:
                return DataSourceResponse.error_response(
                    error=f"Invalid metal code: {metal_code}"
                )

            response = self.session.get(
                f"{self.DATA_URL}/Volumes",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.DATA_URL}/Volumes",
                    "metal_code": metal_code,
                    "note": "HTML parsing required for volume data"
                },
                metadata={
                    "source": "LME",
                    "metal_code": metal_code,
                    "data_type": "volumes"
                }
            )
        except Exception as e:
            return handle_request_error(e, "LME", "get_volumes")

    def get_stocks(self, metal_code: Optional[str] = None) -> DataSourceResponse:
        """Get warehouse stock levels.

        Args:
            metal_code: Metal code (optional)

        Returns:
            DataSourceResponse with stock data
        """
        try:
            if metal_code and metal_code not in self.METALS:
                return DataSourceResponse.error_response(
                    error=f"Invalid metal code: {metal_code}"
                )

            response = self.session.get(
                f"{self.DATA_URL}/Stocks",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.DATA_URL}/Stocks",
                    "metal_code": metal_code,
                    "note": "HTML parsing required for stock data"
                },
                metadata={
                    "source": "LME",
                    "metal_code": metal_code,
                    "data_type": "stocks"
                }
            )
        except Exception as e:
            return handle_request_error(e, "LME", "get_stocks")

    def get_settlement_prices(self, date: Optional[str] = None) -> DataSourceResponse:
        """Get settlement prices.

        Args:
            date: Date in YYYY-MM-DD format (optional, defaults to latest)

        Returns:
            DataSourceResponse with settlement prices
        """
        try:
            response = self.session.get(
                f"{self.DATA_URL}/Pricing-data",
                timeout=30
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={
                    "url": f"{self.DATA_URL}/Pricing-data",
                    "date": date or "latest",
                    "note": "Download CSV or parse HTML for settlement prices"
                },
                metadata={
                    "source": "LME",
                    "date": date,
                    "data_type": "settlement_prices"
                }
            )
        except Exception as e:
            return handle_request_error(e, "LME", "get_settlement_prices")

    def get_copper_prices(self) -> DataSourceResponse:
        """Get copper (Grade A) prices.

        Returns:
            DataSourceResponse with copper price data
        """
        return self.get_prices(metal_code="CA")

    def get_aluminum_prices(self) -> DataSourceResponse:
        """Get aluminum prices.

        Returns:
            DataSourceResponse with aluminum price data
        """
        return self.get_prices(metal_code="AH")

    def get_zinc_prices(self) -> DataSourceResponse:
        """Get zinc prices.

        Returns:
            DataSourceResponse with zinc price data
        """
        return self.get_prices(metal_code="ZS")

    def get_nickel_prices(self) -> DataSourceResponse:
        """Get nickel prices.

        Returns:
            DataSourceResponse with nickel price data
        """
        return self.get_prices(metal_code="NI")
