"""CME/CBOT grain futures data source.

Provides access to grain futures data from Chicago Board of Trade (CBOT).

Data includes corn, wheat, soybeans, oats, and rice futures.
"""

from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CMEGrainSource(EconomicDataSource):
    """CME/CBOT grain futures data source.

    Provides access to:
    - Corn futures (ZC)
    - Wheat futures (ZW)
    - Soybean futures (ZS)
    - Oats futures (ZO)
    - Rice futures (ZR)
    - Settlement prices
    - Volume and open interest

    No API key required (public data).
    """

    BASE_URL = "https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures/Settlements"

    # Product codes
    PRODUCTS = {
        "corn": "ZC",
        "wheat": "ZW",
        "soybeans": "ZS",
        "oats": "ZO",
        "rice": "ZR",
        "soybean_meal": "ZM",
        "soybean_oil": "ZL"
    }

    def __init__(self):
        """Initialize CME Grain data source."""
        super().__init__(name="CME_Grain", requires_api_key=False)
        self.session = SessionManager.get_session("cme_grain")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to CME API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            # Test with corn futures
            today = datetime.now().strftime("%Y%m%d")
            response = self.session.get(
                f"{self.BASE_URL}/{self.PRODUCTS['corn']}/FUT",
                params={"tradeDate": today},
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "CME_Grain"},
                metadata={"source": "CME_Grain", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"CME Grain connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(
        self,
        product_code: str,
        trade_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Make request to CME API.

        Args:
            product_code: Product code (e.g., 'ZC', 'ZW')
            trade_date: Trade date (YYYYMMDD format)

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        if not trade_date:
            trade_date = datetime.now().strftime("%Y%m%d")

        url = f"{self.BASE_URL}/{product_code}/FUT"
        params = {"tradeDate": trade_date}

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_corn_futures(
        self,
        trade_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get corn futures settlement data.

        Args:
            trade_date: Trade date (YYYY-MM-DD format)

        Returns:
            DataSourceResponse with corn futures data
        """
        try:
            if trade_date:
                trade_date = trade_date.replace("-", "")

            data = self._make_request(self.PRODUCTS["corn"], trade_date)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "CME_Grain",
                    "product": "corn",
                    "product_code": self.PRODUCTS["corn"],
                    "trade_date": trade_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "CME_Grain", "get_corn_futures")

    def get_wheat_futures(
        self,
        trade_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get wheat futures settlement data.

        Args:
            trade_date: Trade date (YYYY-MM-DD format)

        Returns:
            DataSourceResponse with wheat futures data
        """
        try:
            if trade_date:
                trade_date = trade_date.replace("-", "")

            data = self._make_request(self.PRODUCTS["wheat"], trade_date)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "CME_Grain",
                    "product": "wheat",
                    "product_code": self.PRODUCTS["wheat"],
                    "trade_date": trade_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "CME_Grain", "get_wheat_futures")

    def get_soybean_futures(
        self,
        trade_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get soybean futures settlement data.

        Args:
            trade_date: Trade date (YYYY-MM-DD format)

        Returns:
            DataSourceResponse with soybean futures data
        """
        try:
            if trade_date:
                trade_date = trade_date.replace("-", "")

            data = self._make_request(self.PRODUCTS["soybeans"], trade_date)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "CME_Grain",
                    "product": "soybeans",
                    "product_code": self.PRODUCTS["soybeans"],
                    "trade_date": trade_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "CME_Grain", "get_soybean_futures")

    def get_grain_settlement(
        self,
        grain: str,
        trade_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get settlement data for any grain.

        Args:
            grain: Grain name ('corn', 'wheat', 'soybeans', 'oats', 'rice')
            trade_date: Trade date (YYYY-MM-DD format)

        Returns:
            DataSourceResponse with grain futures data
        """
        try:
            product_code = self.PRODUCTS.get(grain.lower())
            if not product_code:
                return DataSourceResponse.error_response(
                    error=f"Invalid grain: {grain}. Valid options: {list(self.PRODUCTS.keys())}"
                )

            if trade_date:
                trade_date = trade_date.replace("-", "")

            data = self._make_request(product_code, trade_date)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "CME_Grain",
                    "product": grain,
                    "product_code": product_code,
                    "trade_date": trade_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "CME_Grain", "get_grain_settlement")

    def get_all_grains(
        self,
        trade_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get settlement data for all grains.

        Args:
            trade_date: Trade date (YYYY-MM-DD format)

        Returns:
            DataSourceResponse with all grain futures data
        """
        try:
            if trade_date:
                trade_date = trade_date.replace("-", "")

            all_data = {}
            for grain, product_code in self.PRODUCTS.items():
                try:
                    data = self._make_request(product_code, trade_date)
                    all_data[grain] = data
                except Exception as e:
                    logger.warning(f"Failed to fetch {grain}: {e}")
                    all_data[grain] = {"error": str(e)}

            return DataSourceResponse.success_response(
                data=all_data,
                metadata={
                    "source": "CME_Grain",
                    "products": list(self.PRODUCTS.keys()),
                    "trade_date": trade_date
                }
            )
        except Exception as e:
            return handle_request_error(e, "CME_Grain", "get_all_grains")
