"""Global Trade Alert (GTA) data source.

Provides access to trade intervention monitoring and protectionism data.

No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class GlobalTradeAlertSource(EconomicDataSource):
    """Global Trade Alert trade intervention data source.

    Provides access to:
    - Trade intervention tracking (tariffs, subsidies, quotas)
    - Protectionism monitoring
    - Harmful vs liberalizing intervention classification
    - Country and sector-level trade policy analysis
    - Trade war impact assessment
    - Supply chain risk indicators

    Critical for trade war scenario analysis and supply chain risk.
    No API key required.
    """

    BASE_URL = "https://api.globaltradealert.org/api/v1"

    INTERVENTION_TYPES = [
        "tariff",
        "import_quota",
        "export_ban",
        "subsidy",
        "local_content_requirement",
        "anti_dumping",
        "countervailing_duty",
        "safeguard",
        "sanitary_phytosanitary",
        "technical_barrier",
        "public_procurement",
        "export_subsidy",
        "investment_measure",
        "capital_control"
    ]

    G20_COUNTRIES = [
        "ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND",
        "IDN", "ITA", "JPN", "KOR", "MEX", "RUS", "SAU", "ZAF",
        "TUR", "GBR", "USA", "EU"
    ]

    def __init__(self):
        super().__init__(name="GlobalTradeAlert", requires_api_key=False)
        self.session = SessionManager.get_session("gta")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/interventions",
                params={"limit": 1},
                timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "GlobalTradeAlert"},
                metadata={"source": "GTA", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"GTA connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_interventions(
        self,
        implementing_country: Optional[str] = None,
        affected_country: Optional[str] = None,
        intervention_type: Optional[str] = None,
        sector: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        harmful_only: bool = False
    ) -> DataSourceResponse:
        """Get trade interventions.

        Args:
            implementing_country: Country implementing the measure
            affected_country: Country affected by the measure
            intervention_type: Type of intervention
            sector: Affected sector (HS code or description)
            year_from: Start year
            year_to: End year
            harmful_only: Only return harmful interventions

        Returns:
            DataSourceResponse with intervention data
        """
        try:
            params: Dict[str, Any] = {}
            if implementing_country:
                params["implementing_country"] = implementing_country
            if affected_country:
                params["affected_country"] = affected_country
            if intervention_type:
                params["intervention_type"] = intervention_type
            if sector:
                params["sector"] = sector
            if year_from:
                params["year_from"] = year_from
            if year_to:
                params["year_to"] = year_to
            if harmful_only:
                params["harmful"] = "true"

            response = self.session.get(
                f"{self.BASE_URL}/interventions",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "GTA",
                    "implementing_country": implementing_country,
                    "affected_country": affected_country,
                    "intervention_type": intervention_type,
                    "sector": sector,
                    "harmful_only": harmful_only
                }
            )
        except Exception as e:
            return handle_request_error(e, "GTA", "get_interventions")

    def get_country_profile(
        self,
        country: str
    ) -> DataSourceResponse:
        """Get trade policy profile for a country.

        Args:
            country: Country ISO code

        Returns:
            DataSourceResponse with country trade policy profile
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/country/{country}",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "GTA",
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "GTA", "get_country_profile")

    def get_sector_exposure(
        self,
        sector: str,
        country: Optional[str] = None
    ) -> DataSourceResponse:
        """Get trade intervention exposure for a specific sector.

        Args:
            sector: Sector name or HS code
            country: Filter by country (optional)

        Returns:
            DataSourceResponse with sector exposure data
        """
        try:
            params = {"sector": sector}
            if country:
                params["country"] = country

            response = self.session.get(
                f"{self.BASE_URL}/sector_exposure",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "GTA",
                    "sector": sector,
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "GTA", "get_sector_exposure")

    def get_intervention_types(self) -> DataSourceResponse:
        """Get list of intervention types.

        Returns:
            DataSourceResponse with intervention type list
        """
        return DataSourceResponse.success_response(
            data=self.INTERVENTION_TYPES,
            metadata={"source": "GTA", "count": len(self.INTERVENTION_TYPES)}
        )

    def get_g20_countries(self) -> DataSourceResponse:
        """Get G20 country codes.

        Returns:
            DataSourceResponse with G20 country list
        """
        return DataSourceResponse.success_response(
            data=self.G20_COUNTRIES,
            metadata={"source": "GTA", "count": len(self.G20_COUNTRIES)}
        )
