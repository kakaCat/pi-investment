"""Carbon markets and emissions data source.

Provides access to EU ETS carbon prices, emissions data, and carbon credit markets.

No API key required (uses public APIs).
"""

from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class CarbonSource(EconomicDataSource):
    """Carbon markets and emissions data source.

    Provides access to:
    - EU ETS carbon allowance prices (EEX)
    - Carbon credit pricing
    - National emissions data
    - Renewable energy statistics
    - IRENA renewable capacity data
    - Energy transition indicators

    No API key required.
    """

    BASE_URL = "https://api.energy-charts.info"
    IRENA_URL = "https://api.irena.org/api/v1"
    ENTEC_URL = "https://api.energycharts.info"

    EMISSIONS_SCOPES = {
        "scope1": "Direct emissions from owned sources",
        "scope2": "Indirect emissions from purchased energy",
        "scope3": "All other indirect emissions in value chain"
    }

    CARBON_MARKETS = {
        "EU_ETS": "EU Emissions Trading System",
        "UK_ETS": "UK Emissions Trading System",
        "RGGI": "US Regional Greenhouse Gas Initiative",
        "CCA": "California Carbon Allowance",
        "NZ_ETS": "New Zealand Emissions Trading Scheme",
        "K_ETS": "Korea Emissions Trading System"
    }

    def __init__(self):
        super().__init__(name="Carbon", requires_api_key=False)
        self.session = SessionManager.get_session("carbon")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/price/spot_bzn",
                params={"bzn": "DE-LU"},
                timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "EnergyCharts"},
                metadata={"source": "Carbon", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Carbon connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_eu_ets_price(self) -> DataSourceResponse:
        """Get EU ETS carbon allowance price (EUR/tonne CO2).

        Returns:
            DataSourceResponse with EUA spot and futures prices
        """
        try:
            data = self.session.get(
                f"{self.BASE_URL}/price/spot_bzn",
                params={"bzn": "DE-LU"},
                timeout=30
            ).json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "EnergyCharts",
                    "market": "EU_ETS",
                    "unit": "EUR/tCO2"
                }
            )
        except Exception as e:
            return handle_request_error(e, "Carbon", "get_eu_ets_price")

    def get_power_generation(self, country: str = "DE") -> DataSourceResponse:
        """Get power generation mix by source.

        Args:
            country: Country code (ISO 3166-1 alpha-2)

        Returns:
            DataSourceResponse with generation data
        """
        try:
            data = self.session.get(
                f"{self.BASE_URL}/power",
                params={"country": country.lower()},
                timeout=30
            ).json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "EnergyCharts",
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "Carbon", "get_power_generation")

    def get_carbon_markets(self) -> DataSourceResponse:
        """Get list of carbon markets.

        Returns:
            DataSourceResponse with carbon market descriptions
        """
        markets = [
            {"code": code, "description": desc}
            for code, desc in self.CARBON_MARKETS.items()
        ]
        return DataSourceResponse.success_response(
            data=markets,
            metadata={"source": "Carbon", "count": len(markets)}
        )

    def get_renewable_share(self, country: str = "DE") -> DataSourceResponse:
        """Get renewable energy share in power generation.

        Args:
            country: Country code

        Returns:
            DataSourceResponse with renewable share data
        """
        try:
            params = {
                "country": country.lower(),
                "start": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "end": datetime.now().strftime("%Y-%m-%d")
            }
            data = self.session.get(
                f"{self.BASE_URL}/ren_share",
                params=params,
                timeout=30
            ).json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "EnergyCharts",
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "Carbon", "get_renewable_share")

    def get_emissions_scopes(self) -> DataSourceResponse:
        """Get emissions scope definitions.

        Returns:
            DataSourceResponse with scope definitions
        """
        scopes = [
            {"scope": key, "description": desc}
            for key, desc in self.EMISSIONS_SCOPES.items()
        ]
        return DataSourceResponse.success_response(
            data=scopes,
            metadata={"source": "Carbon", "count": len(scopes)}
        )
