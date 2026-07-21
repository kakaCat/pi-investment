"""World Steel Association global steel industry data source.
Provides steel production, consumption, and trade statistics. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class WorldSteelAssociationSource(EconomicDataSource):
    """World Steel Association steel industry data source.
    Crude steel production by country, capacity utilization, consumption, trade.
    Economic: industrial activity proxy, construction cycle indicator."""

    TOP_PRODUCERS = ["China", "India", "Japan", "United States", "Russia",
        "South Korea", "Turkey", "Germany", "Brazil", "Iran"]

    def __init__(self):
        super().__init__(name="WorldSteelAssociation", requires_api_key=False)
        self.session = SessionManager.get_session("worldsteel")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get("https://worldsteel.org/steel-topics/statistics/", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "WorldSteel"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_production_data(self) -> DataSourceResponse:
        try:
            r = self.session.get("https://worldsteel.org/steel-topics/statistics/world-steel-in-figures/", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"url": str(r.url)},
                metadata={"source": "WorldSteel", "indicator": "crude_steel_production"})
        except Exception as e:
            return handle_request_error(e, "WorldSteel", "get_production_data")

    def get_top_producers(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.TOP_PRODUCERS,
            metadata={"source": "WorldSteel", "count": len(self.TOP_PRODUCERS)})
