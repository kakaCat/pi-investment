"""World Bank data source.

Provides access to World Bank commodity prices and economic indicators.
Inspired by FinceptTerminal's world_bank_commodity_data.py implementation.
"""

from typing import Optional, List, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import normalize_date

logger = logging.getLogger(__name__)


class WorldBankSource(EconomicDataSource):
    """World Bank data source.

    Provides access to:
    - Commodity prices (Pink Sheet - 70+ commodities from 1960)
    - Economic indicators
    - Development data

    No API key required.
    """

    BASE_URL = "https://api.worldbank.org/v2/en/indicator"

    # World Bank commodity indicators (Pink Sheet)
    COMMODITY_INDICATORS = {
        # Energy
        "crude_oil_avg": "PCOALBBGUSDM",
        "crude_oil_brent": "POILBREUSDM",
        "crude_oil_wti": "POILWTIUSDM",
        "crude_oil_dubai": "POILDUBAUSDM",
        "natural_gas_us": "PNGASUSDM",
        "natural_gas_eu": "PNGASEUUSDM",
        "coal": "PCOALBTUUSDM",

        # Agricultural
        "wheat": "PWHEAMTUSDM",
        "corn": "PMAIZMTUSDM",
        "rice": "PRICENPQUSDM",
        "soybean": "PSOYBUSDM",
        "soybeanmeal": "PSOYMEUSDM",
        "soybeanoil": "PSOYOUSDM",
        "sugar": "PSUGAISAUSDM",
        "coffee_arabica": "PCOFFAUSDM",
        "coffee_robusta": "PCOFFRBUSDM",
        "cocoa": "PCOCOUSDM",
        "tea": "PTEAUSDM",
        "palm_oil": "PPOILUSDM",
        "cotton": "PCOTTINDUSDM",
        "tobacco": "PTOBAUSDM",
        "rubber": "PRUBBINDNAUSDM",
        "bananas": "PBANSOPUSDM",
        "oranges": "PORANGCWUSDM",

        # Metals
        "aluminum": "PALUMUSDM",
        "copper": "PCOPPUSDM",
        "iron_ore": "PIORECRUSDM",
        "lead": "PLEADUSDM",
        "nickel": "PNICKUSDM",
        "tin": "PTINUSDM",
        "zinc": "PZINCUSDM",
        "gold": "PGOLDUSDM",
        "silver": "PSILVERUSDM",
        "platinum": "PPLATINUMUSDM",

        # Fertilizers
        "urea": "PUREAEURUSDM",
        "dap": "PDAPUSDM",
        "potassium_chloride": "PPOTUSDM",
        "phosphate_rock": "PPHOSBUSDM",
    }

    INDEX_INDICATORS = {
        "energy_index": "PENERGYINDEXM",
        "non_energy_index": "PNRGINDEXM",
        "agriculture_index": "PAGRIINDEXM",
        "metals_index": "PMETALSINDEXM",
        "fertilizer_index": "PFERTILIZERINDEXM"
    }

    def __init__(self):
        super().__init__(name="WorldBank", requires_api_key=False)
        self.session = SessionManager.get_session("world_bank")

    def validate_config(self) -> bool:
        """World Bank API doesn't require configuration."""
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test World Bank API connection."""
        try:
            # Test with crude oil Brent price
            result = self._make_request("POILBREUSDM", 2023, 2023)
            if isinstance(result, dict) and "error" in result:
                return DataSourceResponse.error_response(result["error"])

            return DataSourceResponse.success_response(
                {"status": "connected", "test": "passed"},
                metadata={"source": "world_bank"}
            )
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataSourceResponse:
        """Get World Bank indicator series.

        Args:
            series_id: World Bank indicator code
            start_date: Start year (YYYY) or None for default
            end_date: End year (YYYY) or None for default

        Returns:
            DataSourceResponse with series data
        """
        self._log_request("get_series", {
            "series_id": series_id,
            "start_date": start_date,
            "end_date": end_date
        })

        try:
            start_year = int(start_date[:4]) if start_date else 2000
            end_year = int(end_date[:4]) if end_date else 2024

            data = self._make_request(series_id, start_year, end_year)

            if isinstance(data, dict) and "error" in data:
                return DataSourceResponse.error_response(data["error"])

            if isinstance(data, list):
                self._log_success("get_series", len(data))
                return DataSourceResponse.success_response(
                    data,
                    metadata={"series_id": series_id}
                )

            return DataSourceResponse.error_response("Invalid response format")

        except Exception as e:
            return self._handle_error("get_series", e)

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        """Search for commodity series.

        Args:
            query: Search query (commodity name)
            limit: Maximum results

        Returns:
            DataSourceResponse with matching commodities
        """
        self._log_request("search_series", {"query": query, "limit": limit})

        try:
            query_lower = query.lower()
            matches = []

            # Search in commodity indicators
            for name, code in self.COMMODITY_INDICATORS.items():
                if query_lower in name.lower():
                    matches.append({
                        "id": code,
                        "name": name,
                        "type": "commodity",
                        "category": self._get_commodity_category(name)
                    })

            # Search in index indicators
            for name, code in self.INDEX_INDICATORS.items():
                if query_lower in name.lower():
                    matches.append({
                        "id": code,
                        "name": name,
                        "type": "index"
                    })

            matches = matches[:limit]
            self._log_success("search_series", len(matches))
            return DataSourceResponse.success_response(matches)

        except Exception as e:
            return self._handle_error("search_series", e)

    def get_oil_prices(
        self,
        start_year: int = 2000,
        end_year: int = 2024
    ) -> DataSourceResponse:
        """Get oil prices (Brent, WTI, Dubai).

        Args:
            start_year: Start year
            end_year: End year

        Returns:
            DataSourceResponse with oil price data
        """
        self._log_request("get_oil_prices", {
            "start_year": start_year,
            "end_year": end_year
        })

        try:
            results = {}
            for name in ["crude_oil_brent", "crude_oil_wti", "crude_oil_dubai"]:
                indicator = self.COMMODITY_INDICATORS[name]
                data = self._make_request(indicator, start_year, end_year)
                if not isinstance(data, dict) or "error" not in data:
                    results[name] = data

            if results:
                self._log_success("get_oil_prices", len(results))
                return DataSourceResponse.success_response({
                    "category": "oil",
                    "start_year": start_year,
                    "end_year": end_year,
                    "unit": "USD/bbl",
                    "data": results
                })

            return DataSourceResponse.error_response("Failed to fetch oil prices")

        except Exception as e:
            return self._handle_error("get_oil_prices", e)

    def get_commodity_price(
        self,
        commodity: str,
        start_year: int = 2000,
        end_year: int = 2024
    ) -> DataSourceResponse:
        """Get price data for a specific commodity.

        Args:
            commodity: Commodity name (e.g., "gold", "wheat", "copper")
            start_year: Start year
            end_year: End year

        Returns:
            DataSourceResponse with commodity price data
        """
        self._log_request("get_commodity_price", {
            "commodity": commodity,
            "start_year": start_year,
            "end_year": end_year
        })

        try:
            indicator = self.COMMODITY_INDICATORS.get(commodity.lower())
            if not indicator:
                available = list(self.COMMODITY_INDICATORS.keys())
                return DataSourceResponse.error_response(
                    f"Unknown commodity '{commodity}'. Available: {', '.join(available[:10])}..."
                )

            data = self._make_request(indicator, start_year, end_year)

            if isinstance(data, dict) and "error" in data:
                return DataSourceResponse.error_response(data["error"])

            self._log_success("get_commodity_price", len(data) if isinstance(data, list) else 0)
            return DataSourceResponse.success_response({
                "commodity": commodity,
                "indicator": indicator,
                "start_year": start_year,
                "end_year": end_year,
                "data": data
            })

        except Exception as e:
            return self._handle_error("get_commodity_price", e)

    def get_commodity_index(
        self,
        index_name: str,
        start_year: int = 2000,
        end_year: int = 2024
    ) -> DataSourceResponse:
        """Get commodity index data.

        Args:
            index_name: Index name (energy_index, agriculture_index, metals_index, etc.)
            start_year: Start year
            end_year: End year

        Returns:
            DataSourceResponse with index data
        """
        self._log_request("get_commodity_index", {
            "index_name": index_name,
            "start_year": start_year,
            "end_year": end_year
        })

        try:
            indicator = self.INDEX_INDICATORS.get(index_name.lower())
            if not indicator:
                available = list(self.INDEX_INDICATORS.keys())
                return DataSourceResponse.error_response(
                    f"Unknown index '{index_name}'. Available: {', '.join(available)}"
                )

            data = self._make_request(indicator, start_year, end_year)

            if isinstance(data, dict) and "error" in data:
                return DataSourceResponse.error_response(data["error"])

            self._log_success("get_commodity_index", len(data) if isinstance(data, list) else 0)
            return DataSourceResponse.success_response({
                "index": index_name,
                "indicator": indicator,
                "start_year": start_year,
                "end_year": end_year,
                "data": data
            })

        except Exception as e:
            return self._handle_error("get_commodity_index", e)

    def list_commodities(self) -> DataSourceResponse:
        """List all available commodities.

        Returns:
            DataSourceResponse with commodity list
        """
        self._log_request("list_commodities", {})

        try:
            commodities = []
            for name, code in self.COMMODITY_INDICATORS.items():
                commodities.append({
                    "name": name,
                    "code": code,
                    "category": self._get_commodity_category(name)
                })

            self._log_success("list_commodities", len(commodities))
            return DataSourceResponse.success_response(commodities)

        except Exception as e:
            return self._handle_error("list_commodities", e)

    def _make_request(
        self,
        indicator: str,
        start_year: int,
        end_year: int
    ) -> Any:
        """Make request to World Bank API.

        Args:
            indicator: World Bank indicator code
            start_year: Start year
            end_year: End year

        Returns:
            List of data records or error dict
        """
        url = f"{self.BASE_URL}/{indicator}"
        params = {
            "format": "json",
            "date": f"{start_year}:{end_year}",
            "per_page": 1000
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and len(data) > 1:
                records = data[1] or []
                return [
                    {
                        "date": r.get("date"),
                        "value": r.get("value"),
                        "country": r.get("country", {}).get("value")
                    }
                    for r in records
                ]
            return data

        except Exception as e:
            logger.error(f"World Bank API request failed: {e}")
            return {"error": str(e)}

    @staticmethod
    def _get_commodity_category(name: str) -> str:
        """Get category for a commodity."""
        if any(x in name for x in ["oil", "gas", "coal"]):
            return "energy"
        elif any(x in name for x in ["aluminum", "copper", "iron", "lead", "nickel", "tin", "zinc", "gold", "silver", "platinum"]):
            return "metals"
        elif any(x in name for x in ["urea", "dap", "potassium", "phosphate"]):
            return "fertilizers"
        else:
            return "agricultural"
