"""Reserve Bank of India (RBI) central bank data source.
Provides Indian monetary policy, financial, and economic data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class ReserveBankIndiaSource(EconomicDataSource):
    """Reserve Bank of India monetary and financial data source.
    Repo rate, CPI/WPI inflation, INR exchange rates, forex reserves, bank credit."""

    BASE_URL = "https://api.rbi.org.in/api/v1"
    DBIE_URL = "https://dbie.rbi.org.in/api"
    KEY_INDICATORS = {"repo_rate": "Policy repo rate", "crr": "Cash Reserve Ratio",
        "cpi": "Consumer Price Index", "wpi": "Wholesale Price Index",
        "forex_reserves": "Forex reserves", "gdp_growth": "GDP growth rate"}

    def __init__(self):
        super().__init__(name="ReserveBankIndia", requires_api_key=False)
        self.session = SessionManager.get_session("rbi")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.DBIE_URL}/home", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "RBI"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_policy_rates(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.DBIE_URL}/dbie_services/rates", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "RBI", "type": "policy_rates"})
        except Exception as e:
            return handle_request_error(e, "RBI", "get_policy_rates")

    def get_inflation(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.DBIE_URL}/dbie_services/inflation", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "RBI", "type": "inflation"})
        except Exception as e:
            return handle_request_error(e, "RBI", "get_inflation")

    def get_indicators(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "description": d} for n, d in self.KEY_INDICATORS.items()],
            metadata={"source": "RBI", "count": len(self.KEY_INDICATORS)})
