"""EIA Electricity data source.

Provides US electricity generation, consumption, prices, and grid data.
API key required (free from www.eia.gov).
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EIAElectricitySource(EconomicDataSource):
    """EIA (U.S. Energy Information Administration) electricity data source.

    Provides electricity generation by fuel type (coal, natural gas, nuclear,
    renewables), retail electricity prices by state and sector, total
    consumption, net generation, and wholesale electricity market data.

    API key required. Free registration at https://www.eia.gov/opendata/
    """

    BASE_URL = "https://api.eia.gov/v2"

    SERIES = {
        "total_generation": "ELEC.GEN.ALL-US-99.M",
        "coal_generation": "ELEC.GEN.COW-US-99.M",
        "nat_gas_generation": "ELEC.GEN.NG-US-99.M",
        "nuclear_generation": "ELEC.GEN.NUC-US-99.M",
        "solar_generation": "ELEC.GEN.SUN-US-99.M",
        "wind_generation": "ELEC.GEN.WND-US-99.M",
        "hydro_generation": "ELEC.GEN.HYC-US-99.M",
        "retail_price_residential": "ELEC.PRICE.US-RES.M",
        "retail_price_commercial": "ELEC.PRICE.US-COM.M",
        "retail_price_industrial": "ELEC.PRICE.US-IND.M",
        "total_consumption": "ELEC.CONS_TOT.US-M",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="EIAElectricity", requires_api_key=True)
        self.api_key = api_key or os.getenv("EIA_API_KEY", "")
        self.session = SessionManager.get_session("eia_elec")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("EIA API key not configured. Register at https://www.eia.gov/opendata/")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/electricity/retail-sales/data",
                params={"api_key": self.api_key, "length": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "EIA_Electricity"},
                metadata={"source": "EIA", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"EIA Electricity connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DataSourceResponse:
        try:
            params: Dict[str, Any] = {"api_key": self.api_key, "length": 5000}
            if start_date:
                params["start"] = start_date
            if end_date:
                params["end"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/electricity/retail-sales/data",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EIA_Electricity", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "EIAElectricity", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.SERIES.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "EIA_Electricity", "query": query},
        )

    def get_generation_by_source(self) -> DataSourceResponse:
        """Get electricity generation breakdown by fuel source."""
        return self.get_series("total_generation")

    def get_retail_prices(self) -> DataSourceResponse:
        """Get retail electricity prices by sector."""
        return self.get_series("retail_price_residential")

    def get_series_list(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.SERIES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "EIA_Electricity", "count": len(items)},
        )
