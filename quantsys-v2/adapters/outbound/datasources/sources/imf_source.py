"""IMF (International Monetary Fund) Source.

Provides access to IMF economic data including:
- Economic indicators (IRFCL - International Reserves and Foreign Currency Liquidity)
- Financial Soundness Indicators (FSI)
- Direction of Trade Statistics (DOTS)

Inspired by FinceptTerminal's imf_data.py implementation.
No API key required - public data access.
"""

from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import safe_call


class IMFSource(EconomicDataSource):
    """IMF economic data source.

    No API key required - uses public IMF SDMX JSON API.
    """

    BASE_URL = "http://dataservices.imf.org/REST/SDMX_JSON.svc/"

    def __init__(self):
        super().__init__(name="IMF", requires_api_key=False)
        self.session = SessionManager.get_session("imf")
        self.session.headers.update({'User-Agent': 'QuantSys-V2/1.0'})

        # Country code mappings (ISO 2-letter codes)
        self.country_to_code = {
            "united_states": "US", "usa": "US", "us": "US",
            "united_kingdom": "GB", "uk": "GB", "great_britain": "GB",
            "china": "CN", "japan": "JP", "germany": "DE", "france": "FR",
            "india": "IN", "italy": "IT", "canada": "CA", "south_korea": "KR",
            "russia": "RU", "brazil": "BR", "australia": "AU", "spain": "ES",
            "mexico": "MX", "indonesia": "ID", "netherlands": "NL", "saudi_arabia": "SA",
            "turkey": "TR", "switzerland": "CH", "poland": "PL", "sweden": "SE",
            "belgium": "BE", "argentina": "AR", "ireland": "IE", "austria": "AT",
            "norway": "NO", "israel": "IL", "uae": "AE", "egypt": "EG",
            "south_africa": "ZA", "denmark": "DK", "singapore": "SG",
        }

        # Economic indicator presets
        self.irfcl_presets = {
            "top_lines": "RAF_USD,RAFA_USD,RAFAFX_USD,RAOFA_USD,RAPFA_USD,RAFAIMF_USD,RAFASDR_USD,RAFAGOLD_USD,RACFA_USD,RAMDCD_USD,RAMFIFC_USD,RAMSR_USD",
            "reserve_assets": "RAF_USD,RAFA_USD,RAFAFX_USD,RAOFA_USD,RAPFA_USD,RAFAIMF_USD,RAFASDR_USD,RAFAGOLD_USD",
            "gold_reserves": "RAFAGOLD_USD,RAFAGOLDV_OZT",
            "derivative_assets": "RAMFDA_USD"
        }

        # Trade indicators
        self.trade_indicators = {
            "exports": "TXG_FOB_USD",
            "imports": "TMG_CIF_USD",
            "balance": "TBG_USD",
            "all": "TXG_FOB_USD+TMG_CIF_USD+TBG_USD"
        }

        # Frequency mappings
        self.frequency_map = {
            "annual": "A", "yearly": "A", "a": "A",
            "quarter": "Q", "quarterly": "Q", "q": "Q",
            "month": "M", "monthly": "M", "m": "M"
        }

        # Sector mappings for IRFCL
        self.sector_map = {
            "government": "S1311",
            "central_bank": "S121",
            "monetary_authorities": "S1X",
            "all": ""
        }

    def validate_config(self) -> bool:
        """Validate IMF configuration (no API key needed)."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test IMF API connection."""
        try:
            # Test with a simple request (US GDP data)
            result = self.get_economic_indicators(
                countries="US",
                symbols="top_lines",
                frequency="quarter"
            )

            if not result.success:
                return DataSourceResponse.error_response(result.error)

            return DataSourceResponse.success_response(
                {"status": "connected", "test": "passed"},
                metadata={"source": "imf", "test_country": "US"}
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

        For IMF, this maps to economic indicators.
        """
        return self.get_economic_indicators(
            countries="all",
            symbols=series_id,
            frequency="quarter",
            start_date=start_date,
            end_date=end_date
        )

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for available series (generic interface).

        For IMF, this maps to search_indicators.
        """
        return self.search_indicators(query=query)

    def get_economic_indicators(
        self,
        countries: Optional[str] = None,
        symbols: Optional[str] = None,
        frequency: str = "quarter",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sector: str = "monetary_authorities"
    ) -> DataSourceResponse:
        """Get economic indicators data (IRFCL).

        Args:
            countries: Comma-separated country names or codes (e.g., "US,CN,JP")
            symbols: Indicator symbols or preset name (e.g., "top_lines", "reserve_assets")
            frequency: Data frequency - "annual", "quarter", or "month"
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)
            sector: Sector filter - "government", "central_bank", "monetary_authorities", "all"

        Returns:
            DataSourceResponse with economic indicator data
        """
        self._log_request("get_economic_indicators", {
            "countries": countries,
            "symbols": symbols,
            "frequency": frequency,
            "start_date": start_date,
            "end_date": end_date,
            "sector": sector
        })

        try:
            # Default parameters
            if not countries:
                countries = "all"
            if not symbols:
                symbols = "top_lines"

            # Normalize countries
            if countries.lower() != "all":
                country_list = [c.strip() for c in countries.split(",")]
                normalized_countries = "+".join([
                    self._normalize_country(c) for c in country_list
                    if self._normalize_country(c)
                ])
            else:
                normalized_countries = ""

            # Handle symbols/presets
            if symbols in self.irfcl_presets:
                indicator_symbols = self.irfcl_presets[symbols].replace(",", "+")
            else:
                symbol_list = [s.strip().upper() for s in symbols.split(",")]
                indicator_symbols = "+".join(symbol_list)

            # Handle frequency
            freq_code = self.frequency_map.get(frequency.lower(), "Q")

            # Handle sector
            sector_code = self.sector_map.get(sector.lower(), "")

            # Adjust dates by frequency
            if start_date:
                start_date = self._adjust_date_by_frequency(start_date, frequency, True)
            if end_date:
                end_date = self._adjust_date_by_frequency(end_date, frequency, False)

            # Build URL
            date_range = f"?startPeriod={start_date}&endPeriod={end_date}" if start_date and end_date else ""
            url = f"{self.BASE_URL}CompactData/IRFCL/{freq_code}.{normalized_countries}.{indicator_symbols}.{sector_code}{date_range}"

            # Make request
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse response
            parsed_data = self._parse_compact_data(data)

            return DataSourceResponse.success_response(
                parsed_data,
                metadata={
                    "countries": countries,
                    "symbols": symbols,
                    "frequency": frequency,
                    "url": url
                }
            )

        except Exception as e:
            return self._handle_error("get_economic_indicators", e)

    def get_direction_of_trade(
        self,
        countries: Optional[str] = None,
        counterparts: Optional[str] = None,
        direction: str = "all",
        frequency: str = "quarter",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get Direction of Trade Statistics (DOTS).

        Args:
            countries: Comma-separated country names or codes
            counterparts: Comma-separated counterpart countries
            direction: Trade direction - "exports", "imports", "balance", "all"
            frequency: Data frequency - "annual", "quarter", or "month"
            start_date: Start date YYYY-MM-DD (optional)
            end_date: End date YYYY-MM-DD (optional)

        Returns:
            DataSourceResponse with trade data
        """
        self._log_request("get_direction_of_trade", {
            "countries": countries,
            "counterparts": counterparts,
            "direction": direction,
            "frequency": frequency
        })

        try:
            # Default parameters
            if not countries:
                countries = "all"
            if not counterparts:
                counterparts = "W00"  # World

            # Normalize countries
            normalized_countries = self._normalize_country_list(countries)
            normalized_counterparts = self._normalize_country_list(counterparts)

            # Handle trade indicators
            if direction in self.trade_indicators:
                indicators = self.trade_indicators[direction]
            else:
                indicators = self.trade_indicators["all"]

            # Handle frequency
            freq_code = self.frequency_map.get(frequency.lower(), "Q")

            # Adjust dates
            if start_date:
                start_date = self._adjust_date_by_frequency(start_date, frequency, True)
            if end_date:
                end_date = self._adjust_date_by_frequency(end_date, frequency, False)

            # Build URL
            date_range = f"?startPeriod={start_date}&endPeriod={end_date}" if start_date and end_date else ""
            url = f"{self.BASE_URL}CompactData/DOT/{freq_code}.{normalized_countries}.{indicators}.{normalized_counterparts}{date_range}"

            # Make request
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse response
            parsed_data = self._parse_compact_data(data)

            return DataSourceResponse.success_response(
                parsed_data,
                metadata={
                    "countries": countries,
                    "counterparts": counterparts,
                    "direction": direction,
                    "frequency": frequency
                }
            )

        except Exception as e:
            return self._handle_error("get_direction_of_trade", e)

    def search_indicators(self, query: Optional[str] = None) -> DataSourceResponse:
        """Search available IMF indicators.

        Args:
            query: Search query (optional)

        Returns:
            DataSourceResponse with available indicators
        """
        self._log_request("search_indicators", {"query": query})

        try:
            # Get dataflow information
            url = f"{self.BASE_URL}Dataflow"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Parse dataflows
            dataflows = []
            if "Structure" in data and "Dataflows" in data["Structure"]:
                for df in data["Structure"]["Dataflows"]["Dataflow"]:
                    dataflow_info = {
                        "id": df.get("@id", ""),
                        "name": df.get("Name", {}).get("#text", ""),
                        "description": df.get("Description", {}).get("#text", "")
                    }

                    # Filter by query if provided
                    if query:
                        query_lower = query.lower()
                        if (query_lower in dataflow_info["id"].lower() or
                            query_lower in dataflow_info["name"].lower() or
                            query_lower in dataflow_info["description"].lower()):
                            dataflows.append(dataflow_info)
                    else:
                        dataflows.append(dataflow_info)

            return DataSourceResponse.success_response(
                dataflows,
                metadata={"query": query, "total": len(dataflows)}
            )

        except Exception as e:
            return self._handle_error("search_indicators", e)

    # Helper methods

    def _normalize_country(self, country: str) -> str:
        """Normalize country name to ISO code."""
        if not country:
            return ""

        country_lower = country.lower().strip().replace(" ", "_")

        # Direct mapping
        if country_lower in self.country_to_code:
            return self.country_to_code[country_lower]

        # Already 2-letter code?
        if len(country) == 2 and country.isupper():
            return country

        # Partial match
        for mapped_name, code in self.country_to_code.items():
            if mapped_name in country_lower or country_lower in mapped_name:
                return code

        return country.upper()  # fallback

    def _normalize_country_list(self, countries: str) -> str:
        """Normalize comma-separated country list."""
        if countries.lower() == "all":
            return ""

        country_list = [c.strip() for c in countries.split(",")]
        normalized = [self._normalize_country(c) for c in country_list if self._normalize_country(c)]
        return "+".join(normalized)

    def _adjust_date_by_frequency(self, date_str: str, frequency: str, is_start: bool = True) -> str:
        """Adjust date based on frequency."""
        if not date_str:
            return ""

        try:
            date = pd.to_datetime(date_str)
            freq = self.frequency_map.get(frequency.lower(), "Q")

            if freq == "Q":
                period = date.to_period('Q')
            elif freq == "A":
                period = date.to_period('A')
            else:  # Monthly
                period = date.to_period('M')

            if is_start:
                adjusted_date = period.start_time
            else:
                adjusted_date = period.end_time

            return adjusted_date.strftime("%Y-%m-%d")
        except:
            return date_str

    def _parse_compact_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse IMF CompactData response."""
        parsed = []

        try:
            if "CompactData" in data and "DataSet" in data["CompactData"]:
                dataset = data["CompactData"]["DataSet"]

                if "Series" in dataset:
                    series_list = dataset["Series"]
                    if not isinstance(series_list, list):
                        series_list = [series_list]

                    for series in series_list:
                        series_info = {
                            "indicator": series.get("@INDICATOR", ""),
                            "country": series.get("@REF_AREA", ""),
                            "frequency": series.get("@FREQ", ""),
                            "observations": []
                        }

                        if "Obs" in series:
                            obs_list = series["Obs"]
                            if not isinstance(obs_list, list):
                                obs_list = [obs_list]

                            for obs in obs_list:
                                series_info["observations"].append({
                                    "period": obs.get("@TIME_PERIOD", ""),
                                    "value": obs.get("@OBS_VALUE", "")
                                })

                        parsed.append(series_info)
        except Exception as e:
            self.logger.warning(f"Failed to parse compact data: {e}")

        return parsed
