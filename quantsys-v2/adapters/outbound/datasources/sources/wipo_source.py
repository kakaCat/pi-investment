"""WIPO (World Intellectual Property Organization) data source.

Provides access to global patent, trademark, and industrial design statistics.

No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class WIPOSource(EconomicDataSource):
    """World Intellectual Property Organization data source.

    Provides access to:
    - Global patent filings (by country, technology, year)
    - Trademark registration data
    - Industrial design statistics
    - Innovation index rankings (Global Innovation Index)
    - Technology trends
    - IP intensity by industry

    No API key required. Patent data as innovation/technology proxy.
    """

    BASE_URL = "https://api.wipo.int/api/v1"
    GII_URL = "https://www.wipo.int/export/sites/www/global_innovation_index"

    IP_TYPES = ["patent", "trademark", "industrial_design", "utility_model"]

    TECHNOLOGY_FIELDS = {
        "1": "Electrical machinery",
        "2": "Audio-visual technology",
        "3": "Telecommunications",
        "4": "Digital communication",
        "5": "Basic communication processes",
        "6": "Computer technology",
        "7": "IT methods for management",
        "8": "Semiconductors",
        "9": "Optics",
        "10": "Measurement",
        "11": "Analysis of biological materials",
        "12": "Control",
        "13": "Medical technology",
        "14": "Organic fine chemistry",
        "15": "Biotechnology",
        "16": "Pharmaceuticals",
        "17": "Macromolecular chemistry",
        "18": "Food chemistry",
        "19": "Basic materials chemistry",
        "20": "Materials metallurgy",
        "21": "Surface technology",
        "22": "Micro-structural and nano-technology",
        "23": "Chemical engineering",
        "24": "Environmental technology",
        "25": "Handling",
        "26": "Machine tools",
        "27": "Engines pumps turbines",
        "28": "Textile and paper machines",
        "29": "Other special machines",
        "30": "Thermal processes and apparatus",
        "31": "Mechanical elements",
        "32": "Transport",
        "33": "Furniture games",
        "34": "Other consumer goods",
        "35": "Civil engineering"
    }

    def __init__(self):
        super().__init__(name="WIPO", requires_api_key=False)
        self.session = SessionManager.get_session("wipo")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/ipstats/patent",
                timeout=10
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "WIPO"},
                metadata={"source": "WIPO", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"WIPO connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_patent_statistics(
        self,
        country: Optional[str] = None,
        year: Optional[int] = None
    ) -> DataSourceResponse:
        """Get patent filing statistics.

        Args:
            country: Country ISO code (optional, e.g., 'CN', 'US', 'JP')
            year: Year (optional, defaults to latest available)

        Returns:
            DataSourceResponse with patent statistics
        """
        try:
            params = {}
            if country:
                params["country"] = country
            if year:
                params["year"] = year

            response = self.session.get(
                f"{self.BASE_URL}/ipstats/patent",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "WIPO",
                    "country": country,
                    "year": year,
                    "type": "patent"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WIPO", "get_patent_statistics")

    def get_technology_trends(
        self,
        technology_field: Optional[str] = None,
        country: Optional[str] = None
    ) -> DataSourceResponse:
        """Get technology trend data from patent filings.

        Args:
            technology_field: Technology field code (1-35)
            country: Country code

        Returns:
            DataSourceResponse with technology trends
        """
        try:
            params: Dict[str, Any] = {}
            if technology_field:
                params["field"] = technology_field
            if country:
                params["country"] = country

            response = self.session.get(
                f"{self.BASE_URL}/ipstats/patent/by_technology",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "WIPO",
                    "technology_field": technology_field,
                    "country": country
                }
            )
        except Exception as e:
            return handle_request_error(e, "WIPO", "get_technology_trends")

    def get_technology_fields(self) -> DataSourceResponse:
        """Get list of WIPO technology fields.

        Returns:
            DataSourceResponse with technology field codes and names
        """
        fields = [
            {"code": code, "name": name}
            for code, name in self.TECHNOLOGY_FIELDS.items()
        ]
        return DataSourceResponse.success_response(
            data=fields,
            metadata={"source": "WIPO", "count": len(fields)}
        )

    def get_trademark_statistics(
        self,
        country: Optional[str] = None,
        year: Optional[int] = None
    ) -> DataSourceResponse:
        """Get trademark filing statistics.

        Args:
            country: Country code
            year: Year

        Returns:
            DataSourceResponse with trademark statistics
        """
        try:
            params = {}
            if country:
                params["country"] = country
            if year:
                params["year"] = year

            response = self.session.get(
                f"{self.BASE_URL}/ipstats/trademark",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "WIPO",
                    "country": country,
                    "year": year,
                    "type": "trademark"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WIPO", "get_trademark_statistics")

    def get_global_innovation_index(
        self,
        year: Optional[int] = None
    ) -> DataSourceResponse:
        """Get Global Innovation Index rankings.

        The GII ranks countries by innovation performance across 80+ indicators
        including R&D expenditure, patent filings, high-tech exports, and
        tertiary education enrollment.

        Args:
            year: Year (optional)

        Returns:
            DataSourceResponse with GII rankings
        """
        try:
            params = {}
            if year:
                params["year"] = year

            response = self.session.get(
                f"{self.GII_URL}/rankings",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "WIPO",
                    "year": year,
                    "dataset": "global_innovation_index"
                }
            )
        except Exception as e:
            return handle_request_error(e, "WIPO", "get_global_innovation_index")

    def get_ip_types(self) -> DataSourceResponse:
        """Get IP types available.

        Returns:
            DataSourceResponse with IP type list
        """
        return DataSourceResponse.success_response(
            data=self.IP_TYPES,
            metadata={"source": "WIPO", "count": len(self.IP_TYPES)}
        )
