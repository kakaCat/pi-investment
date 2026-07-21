"""World Gold Council gold market data source.
Provides gold demand, supply, and central bank holdings data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class WorldGoldCouncilSource(EconomicDataSource):
    """World Gold Council gold market data source.
    Gold demand trends, ETF flows, central bank reserves, supply/demand balance."""

    BASE_URL = "https://www.gold.org/api/v1"
    DEMAND_SECTORS = ["jewelry", "technology", "investment_bars_coins",
        "etfs", "central_banks", "total_demand"]

    def __init__(self):
        super().__init__(name="WorldGoldCouncil", requires_api_key=False)
        self.session = SessionManager.get_session("worldgold")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get("https://www.gold.org/goldhub/data/gold-demand-trends", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "WGC"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_demand_trends(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/gold-demand-trends", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "WGC", "dataset": "gold_demand_trends"})
        except Exception as e:
            return handle_request_error(e, "WGC", "get_demand_trends")

    def get_central_bank_holdings(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/central-bank-gold-reserves", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "WGC", "dataset": "central_bank_gold_reserves"})
        except Exception as e:
            return handle_request_error(e, "WGC", "get_central_bank_holdings")

    def get_demand_sectors(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.DEMAND_SECTORS,
            metadata={"source": "WGC", "count": len(self.DEMAND_SECTORS)})
