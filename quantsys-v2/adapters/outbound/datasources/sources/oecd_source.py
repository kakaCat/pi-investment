"""OECD (Organisation for Economic Co-operation and Development) Source.

Provides access to OECD economic data including:
- GDP data
- CPI (Consumer Price Index)
- Unemployment rates
- Trade statistics
- Social indicators

Inspired by FinceptTerminal's oecd_data.py implementation.
No API key required - public SDMX API.
"""

from typing import Optional, List, Dict, Any
import pandas as pd

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager


class OECDSource(EconomicDataSource):
    """OECD economic data source.

    No API key required - uses public OECD SDMX API.
    """

    BASE_URL = "https://sdmx.oecd.org/public/rest/data/"

    def __init__(self):
        super().__init__(name="OECD", requires_api_key=False)
        self.session = SessionManager.get_session("oecd")

        # Country code mappings
        self.country_codes = {
            "united_states": "USA", "usa": "USA", "us": "USA",
            "united_kingdom": "GBR", "uk": "GBR",
            "germany": "DEU", "france": "FRA", "italy": "ITA",
            "japan": "JPN", "canada": "CAN", "australia": "AUS",
            "korea": "KOR", "mexico": "MEX", "spain": "ESP",
            "netherlands": "NLD", "switzerland": "CHE", "sweden": "SWE",
            "poland": "POL", "belgium": "BEL", "austria": "AUT",
            "norway": "NOR", "denmark": "DNK", "finland": "FIN",
            "ireland": "IRL", "portugal": "PRT", "greece": "GRC",
            "czech_republic": "CZE", "hungary": "HUN", "turkey": "TUR",
            "chile": "CHL", "israel": "ISR", "estonia": "EST",
            "slovenia": "SVN", "latvia": "LVA", "lithuania": "LTU",
            "luxembourg": "LUX", "slovakia": "SVK", "iceland": "ISL",
            "oecd": "OECD", "g7": "G7", "g20": "G20",
            "euro_area": "EA20", "eu": "EU27_2020",
        }

    def validate_config(self) -> bool:
        """Validate OECD configuration (no API key needed)."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test OECD API connection."""
        try:
            result = self.get_gdp(countries="USA", frequency="Q")
            if not result.success:
                return DataSourceResponse.error_response(result.error)

            return DataSourceResponse.success_response(
                {"status": "connected", "test": "passed"},
                metadata={"source": "oecd"}
            )
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get time series data (generic interface).

        For OECD, series_id format: "GDP.USA.Q" or "CPI.USA.M"
        """
        parts = series_id.split(".")
        if len(parts) >= 2:
            indicator = parts[0].upper()
            country = parts[1] if len(parts) > 1 else "USA"
            freq = parts[2] if len(parts) > 2 else "Q"

            if indicator == "GDP":
                return self.get_gdp(country, freq, start_date, end_date)
            elif indicator == "CPI":
                return self.get_cpi(country, freq, start_date, end_date)
            elif indicator == "UNEMPLOYMENT":
                return self.get_unemployment(country, freq, start_date, end_date)

        return DataSourceResponse.error_response(f"Invalid series_id format: {series_id}")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for available series."""
        # Return available indicators
        indicators = [
            {"id": "GDP", "name": "Gross Domestic Product", "description": "Quarterly/Annual GDP data"},
            {"id": "CPI", "name": "Consumer Price Index", "description": "Monthly/Quarterly CPI data"},
            {"id": "UNEMPLOYMENT", "name": "Unemployment Rate", "description": "Monthly/Quarterly unemployment data"},
        ]

        if query:
            query_lower = query.lower()
            indicators = [i for i in indicators if query_lower in i["name"].lower() or query_lower in i["id"].lower()]

        return DataSourceResponse.success_response(indicators[:limit])

    def get_gdp(
        self,
        countries: Optional[str] = None,
        frequency: str = "Q",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get GDP data.

        Args:
            countries: Comma-separated country codes (e.g., "USA,GBR,JPN")
            frequency: "Q" (quarterly) or "A" (annual)
            start_date: Start date YYYY-MM (optional)
            end_date: End date YYYY-MM (optional)

        Returns:
            DataSourceResponse with GDP data
        """
        self._log_request("get_gdp", {
            "countries": countries,
            "frequency": frequency
        })

        try:
            if not countries:
                countries = "USA"

            # Normalize countries
            country_list = [self._normalize_country(c.strip()) for c in countries.split(",")]
            country_param = "+".join(country_list)

            # Build URL
            url = f"{self.BASE_URL}QNA/{country_param}.B1_GE.VOBARSA.{frequency}"

            if start_date or end_date:
                params = {}
                if start_date:
                    params["startPeriod"] = start_date
                if end_date:
                    params["endPeriod"] = end_date
                response = self.session.get(url, params=params, timeout=30)
            else:
                response = self.session.get(url, timeout=30)

            response.raise_for_status()

            # Parse CSV response
            data = self._parse_csv_response(response.text)

            return DataSourceResponse.success_response(
                data,
                metadata={"countries": countries, "frequency": frequency}
            )

        except Exception as e:
            return self._handle_error("get_gdp", e)

    def get_cpi(
        self,
        countries: Optional[str] = None,
        frequency: str = "M",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get CPI (Consumer Price Index) data.

        Args:
            countries: Comma-separated country codes
            frequency: "M" (monthly) or "Q" (quarterly)
            start_date: Start date YYYY-MM (optional)
            end_date: End date YYYY-MM (optional)

        Returns:
            DataSourceResponse with CPI data
        """
        self._log_request("get_cpi", {"countries": countries, "frequency": frequency})

        try:
            if not countries:
                countries = "USA"

            country_list = [self._normalize_country(c.strip()) for c in countries.split(",")]
            country_param = "+".join(country_list)

            # CPI All items
            url = f"{self.BASE_URL}PRICES_CPI/{country_param}.CPALTT01.IXOB.{frequency}"

            params = {}
            if start_date:
                params["startPeriod"] = start_date
            if end_date:
                params["endPeriod"] = end_date

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = self._parse_csv_response(response.text)

            return DataSourceResponse.success_response(
                data,
                metadata={"countries": countries, "frequency": frequency}
            )

        except Exception as e:
            return self._handle_error("get_cpi", e)

    def get_unemployment(
        self,
        countries: Optional[str] = None,
        frequency: str = "M",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get unemployment rate data.

        Args:
            countries: Comma-separated country codes
            frequency: "M" (monthly) or "Q" (quarterly)
            start_date: Start date YYYY-MM (optional)
            end_date: End date YYYY-MM (optional)

        Returns:
            DataSourceResponse with unemployment data
        """
        self._log_request("get_unemployment", {"countries": countries})

        try:
            if not countries:
                countries = "USA"

            country_list = [self._normalize_country(c.strip()) for c in countries.split(",")]
            country_param = "+".join(country_list)

            url = f"{self.BASE_URL}MO/{country_param}.LRHUTTTT.STSA.{frequency}"

            params = {}
            if start_date:
                params["startPeriod"] = start_date
            if end_date:
                params["endPeriod"] = end_date

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = self._parse_csv_response(response.text)

            return DataSourceResponse.success_response(
                data,
                metadata={"countries": countries, "frequency": frequency}
            )

        except Exception as e:
            return self._handle_error("get_unemployment", e)

    # Helper methods

    def _normalize_country(self, country: str) -> str:
        """Normalize country name to OECD code."""
        if not country:
            return "USA"

        country_lower = country.lower().strip().replace(" ", "_")

        if country_lower in self.country_codes:
            return self.country_codes[country_lower]

        # Already a code?
        if len(country) == 3 and country.isupper():
            return country

        return country.upper()

    def _parse_csv_response(self, text: str) -> List[Dict[str, Any]]:
        """Parse CSV response from OECD API."""
        try:
            import csv
            from io import StringIO

            lines = text.strip().split('\n')
            if not lines:
                return []

            reader = csv.DictReader(StringIO(text))
            data = []
            for row in reader:
                data.append(dict(row))

            return data
        except Exception as e:
            self.logger.warning(f"Failed to parse CSV: {e}")
            return []
