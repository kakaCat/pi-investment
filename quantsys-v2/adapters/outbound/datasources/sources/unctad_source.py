"""UNCTAD (UN Conference on Trade and Development) data source.

Provides access to trade, FDI, and development statistics.

No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class UNCTADSource(EconomicDataSource):
    """UNCTAD trade and development statistics data source.

    Provides access to:
    - Foreign Direct Investment (FDI) flows and stocks
    - International trade statistics (goods and services)
    - Commodity prices and terms of trade
    - Digital economy and e-commerce data
    - Maritime transport and port statistics
    - Creative economy data
    - SDG trade-related indicators

    No API key required.
    """

    BASE_URL = "https://unctadstat-api.unctad.org/api/v1"

    UNCTAD_DOMAINS = [
        "FDI_FLOW_INWARD",
        "FDI_FLOW_OUTWARD",
        "FDI_STOCK_INWARD",
        "FDI_STOCK_OUTWARD",
        "TRADE_GOODS",
        "TRADE_SERVICES",
        "COMMODITY_PRICES",
        "DIGITAL_ECONOMY",
        "MARITIME_TRANSPORT",
        "CREATIVE_ECONOMY",
        "POPULATION"
    ]

    def __init__(self):
        super().__init__(name="UNCTAD", requires_api_key=False)
        self.session = SessionManager.get_session("unctad")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/data",
                params={"limit": 1},
                timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "UNCTAD"},
                metadata={"source": "UNCTAD", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"UNCTAD connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_fdi_flows(
        self,
        country: Optional[str] = None,
        direction: str = "inward",
        year_from: int = 2010,
        year_to: int = 2024
    ) -> DataSourceResponse:
        """Get FDI flow data.

        Args:
            country: Reporter country code (optional, all if None)
            direction: 'inward' or 'outward'
            year_from: Start year
            year_to: End year

        Returns:
            DataSourceResponse with FDI data
        """
        try:
            domain = f"FDI_FLOW_{direction.upper()}"
            params: Dict[str, Any] = {
                "from": year_from,
                "to": year_to
            }
            if country:
                params["country"] = country

            response = self.session.get(
                f"{self.BASE_URL}/data/{domain}",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UNCTAD",
                    "domain": domain,
                    "country": country,
                    "year_range": f"{year_from}-{year_to}"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNCTAD", "get_fdi_flows")

    def get_trade_statistics(
        self,
        reporter: Optional[str] = None,
        partner: Optional[str] = None,
        year: int = 2023
    ) -> DataSourceResponse:
        """Get international trade in goods statistics.

        Args:
            reporter: Reporter country
            partner: Partner country (optional)
            year: Year

        Returns:
            DataSourceResponse with trade data
        """
        try:
            params: Dict[str, Any] = {"year": year}
            if reporter:
                params["reporter"] = reporter
            if partner:
                params["partner"] = partner

            response = self.session.get(
                f"{self.BASE_URL}/data/TRADE_GOODS",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UNCTAD",
                    "reporter": reporter,
                    "partner": partner,
                    "year": year
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNCTAD", "get_trade_statistics")

    def get_commodity_prices(
        self,
        commodity: Optional[str] = None
    ) -> DataSourceResponse:
        """Get UNCTAD commodity price indices.

        Covers: all food, tropical beverages, vegetable oilseeds and oils,
        agricultural raw materials, minerals ores and metals.

        Args:
            commodity: Specific commodity group (optional)

        Returns:
            DataSourceResponse with commodity price data
        """
        try:
            params = {}
            if commodity:
                params["commodity"] = commodity

            response = self.session.get(
                f"{self.BASE_URL}/data/COMMODITY_PRICES",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UNCTAD",
                    "commodity": commodity,
                    "note": "USD-denominated commodity price indices"
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNCTAD", "get_commodity_prices")

    def get_digital_economy(
        self,
        indicator: Optional[str] = None,
        country: Optional[str] = None
    ) -> DataSourceResponse:
        """Get digital economy statistics.

        Covers e-commerce, ICT goods trade, digitally deliverable services.

        Args:
            indicator: Specific indicator (optional)
            country: Country code (optional)

        Returns:
            DataSourceResponse with digital economy data
        """
        try:
            params = {}
            if indicator:
                params["indicator"] = indicator
            if country:
                params["country"] = country

            response = self.session.get(
                f"{self.BASE_URL}/data/DIGITAL_ECONOMY",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UNCTAD",
                    "domain": "digital_economy",
                    "country": country,
                    "indicator": indicator
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNCTAD", "get_digital_economy")

    def get_maritime_transport(
        self,
        country: Optional[str] = None,
        indicator: Optional[str] = None
    ) -> DataSourceResponse:
        """Get maritime transport and port statistics.

        Liner shipping connectivity index, port calls, container throughput.

        Args:
            country: Country code (optional)
            indicator: Specific indicator (optional)

        Returns:
            DataSourceResponse with maritime data
        """
        try:
            params = {}
            if country:
                params["country"] = country
            if indicator:
                params["indicator"] = indicator

            response = self.session.get(
                f"{self.BASE_URL}/data/MARITIME_TRANSPORT",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "UNCTAD",
                    "domain": "maritime_transport",
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "UNCTAD", "get_maritime_transport")

    def get_domains(self) -> DataSourceResponse:
        """Get available UNCTAD data domains.

        Returns:
            DataSourceResponse with domain list
        """
        return DataSourceResponse.success_response(
            data=self.UNCTAD_DOMAINS,
            metadata={"source": "UNCTAD", "count": len(self.UNCTAD_DOMAINS)}
        )
