"""EIA Natural Gas data source.

Provides US natural gas storage, production, consumption, prices, and LNG data.
API key required (free from www.eia.gov).
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class EIANaturalGasSource(EconomicDataSource):
    """EIA Natural Gas data source.

    Provides weekly natural gas storage (critical for NG traders), Henry Hub
    spot price, production (gross withdrawals), consumption, LNG exports,
    pipeline imports/exports, and rig counts.

    Weekly storage report is one of the most market-moving energy data releases.

    API key required. Free registration at https://www.eia.gov/opendata/
    """

    BASE_URL = "https://api.eia.gov/v2"

    SERIES = {
        "weekly_storage": "NG.STO.US.W",                 # Weekly working gas in storage
        "henry_hub_spot": "NG.RNGC1.D",                  # Henry Hub daily spot price
        "gross_production": "NG.GPROD.US.M",             # Gross natural gas production
        "total_consumption": "NG.CONS_TOT.US.M",         # Total consumption
        "lng_exports": "NG.EXP_LNG.US.M",                # LNG exports
        "pipeline_exports": "NG.EXP_PIPE.US.M",          # Pipeline exports to Mexico/Canada
        "rig_count": "NG.RIGS.US.W",                     # Natural gas rotary rig count
        "storage_capacity": "NG.STO_CAP.US",             # Total storage capacity
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="EIANaturalGas", requires_api_key=True)
        self.api_key = api_key or os.getenv("EIA_API_KEY", "")
        self.session = SessionManager.get_session("eia_ng")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("EIA API key not configured. Register at https://www.eia.gov/opendata/")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/natural-gas/stor/wkly/data",
                params={"api_key": self.api_key, "length": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "EIA_NatGas"},
                metadata={"source": "EIA", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"EIA Natural Gas connection test failed: {e}")
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
                f"{self.BASE_URL}/natural-gas/stor/wkly/data",
                params=params, timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EIA_NatGas", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "EIANaturalGas", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.SERIES.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "EIA_NatGas", "query": query},
        )

    def get_storage(self) -> DataSourceResponse:
        """Get weekly natural gas storage report (most market-moving metric)."""
        return self.get_series("weekly_storage")

    def get_henry_hub_price(self) -> DataSourceResponse:
        """Get Henry Hub daily spot natural gas price."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/natural-gas/pri/fut/data",
                params={"api_key": self.api_key, "length": 500},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "EIA_NatGas", "series": "henry_hub"},
            )
        except Exception as e:
            return handle_request_error(e, "EIANaturalGas", "get_henry_hub_price")

    def get_series_list(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.SERIES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "EIA_NatGas", "count": len(items)},
        )
