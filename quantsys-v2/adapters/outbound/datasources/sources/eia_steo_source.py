"""EIA Short-Term Energy Outlook (STEO) data source.

Provides monthly energy price and production forecasts used by policymakers
and energy market participants.
API key required (free from www.eia.gov).
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EIASTEOSource(EconomicDataSource):
    """EIA Short-Term Energy Outlook (STEO) forecast data source.

    Provides monthly forecasts for crude oil prices (WTI, Brent), natural gas
    spot price (Henry Hub), US production, global supply/demand balances,
    gasoline/diesel prices, electricity prices, and CO2 emissions.

    Essential for energy sector investment strategy, inflation forecasting,
    and commodity trading. Released monthly.

    API key required. Free registration at https://www.eia.gov/opendata/
    """

    BASE_URL = "https://api.eia.gov/v2"

    FORECASTS = {
        "wti_price": "WTI crude oil spot price forecast ($/barrel)",
        "brent_price": "Brent crude oil spot price forecast ($/barrel)",
        "henry_hub": "Henry Hub natural gas spot price forecast ($/MMBtu)",
        "crude_production": "US crude oil production forecast (million bbl/day)",
        "nat_gas_production": "US dry natural gas production forecast (Bcf/day)",
        "gasoline_price": "US retail regular gasoline price forecast ($/gal)",
        "diesel_price": "US diesel fuel price forecast ($/gal)",
        "electricity_price": "US residential electricity price forecast (cents/kWh)",
        "coal_production": "US coal production forecast (million short tons)",
        "co2_emissions": "US energy-related CO2 emissions forecast (million mt)",
        "global_oil_demand": "Global oil demand forecast (million bbl/day)",
        "global_oil_supply": "Global oil supply forecast (million bbl/day)",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="EIASTEO", requires_api_key=True)
        self.api_key = api_key or os.getenv("EIA_API_KEY", "")
        self.session = SessionManager.get_session("eia_steo")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("EIA API key not configured. Register at https://www.eia.gov/opendata/")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/steo/data",
                params={"api_key": self.api_key, "length": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "EIA_STEO"},
                metadata={"source": "EIA", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"EIA STEO connection test failed: {e}")
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
                f"{self.BASE_URL}/steo/data",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EIA_STEO", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "EIASTEO", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.FORECASTS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "EIA_STEO", "query": query},
        )

    def get_oil_price_forecast(self) -> DataSourceResponse:
        """Get WTI and Brent crude oil price forecasts."""
        return self.get_series("wti_price")

    def get_nat_gas_forecast(self) -> DataSourceResponse:
        """Get Henry Hub natural gas price forecast."""
        return self.get_series("henry_hub")

    def get_forecasts(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.FORECASTS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "EIA_STEO", "count": len(items)},
        )
