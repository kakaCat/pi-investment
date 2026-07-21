"""Port congestion monitoring data source.

Provides global port congestion and shipping delay data for supply chain
bottleneck analysis. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class PortCongestionSource(EconomicDataSource):
    """Port congestion monitoring data source.

    Provides vessel count at anchorage (waiting to berth), average waiting
    times, congestion indices by port, and global supply chain pressure
    indicators. Tracks major ports: LA/Long Beach, Shanghai, Rotterdam,
    Singapore, Savannah, and others.

    Port congestion data is a leading indicator for:
    - Goods inflation (delayed deliveries → lower supply → higher prices)
    - Retail inventory levels
    - Manufacturing PMI supplier delivery times

    No API key required.
    """

    BASE_URL = "https://portcalls.com/api"

    PORTS = {
        "la_lb": "Los Angeles / Long Beach (US West Coast)",
        "ny_nj": "New York / New Jersey (US East Coast)",
        "savannah": "Savannah (US South Atlantic)",
        "houston": "Houston (US Gulf Coast)",
        "shanghai": "Shanghai (China)",
        "ningbo": "Ningbo-Zhoushan (China)",
        "shenzhen": "Shenzhen / Yantian (China)",
        "singapore": "Singapore (Southeast Asia hub)",
        "rotterdam": "Rotterdam (Europe hub)",
        "antwerp": "Antwerp (Europe)",
        "busan": "Busan (South Korea)",
    }

    def __init__(self):
        super().__init__(name="PortCongestion", requires_api_key=False)
        self.session = SessionManager.get_session("port_congestion")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/congestion/global",
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "PortCongestion"},
                metadata={"source": "PortCongestion", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Port congestion connection test failed: {e}")
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
            params: Dict[str, Any] = {"port": series_id}
            if start_date:
                params["from"] = start_date
            if end_date:
                params["to"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/congestion", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "PortCongestion", "port": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "PortCongestion", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.PORTS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "PortCongestion", "query": query},
        )

    def get_global_congestion(self) -> DataSourceResponse:
        """Get global port congestion overview."""
        return self.get_series("global")

    def get_port_status(self, port: str = "la_lb") -> DataSourceResponse:
        """Get detailed congestion data for a specific port."""
        if port not in self.PORTS:
            return DataSourceResponse.error_response(
                error=f"Unknown port: {port}. Use get_ports()."
            )
        return self.get_series(port)

    def get_ports(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.PORTS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "PortCongestion", "count": len(items)},
        )
