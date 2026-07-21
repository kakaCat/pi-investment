"""People's Bank of China (PBoC) central bank data source.
Provides China's monetary policy, financial, and economic data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class PeopleBankOfChinaSource(EconomicDataSource):
    """People's Bank of China monetary and financial data source.
    LPR rates, MLF, RRR, M2 money supply, TSF, forex reserves, RMB central parity."""

    BASE_URL = "http://www.pbc.gov.cn"
    SERIES_CATEGORIES = {"interest_rates": "LPR, MLF, SLF, repo", "money_supply": "M0/M1/M2",
        "credit": "TSF, new RMB loans", "fx_reserves": "Forex reserves", "exchange_rates": "RMB parity"}

    def __init__(self):
        super().__init__(name="PeopleBankOfChina", requires_api_key=False)
        self.session = SessionManager.get_session("pbc")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/zhengcehuobisi/125207/125213/index.html", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "PBoC"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_lpr_rates(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/zhengcehuobisi/125207/125213/125435/125435.json", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "PBoC", "indicator": "LPR", "tenors": ["1Y", "5Y"]})
        except Exception as e:
            return handle_request_error(e, "PBoC", "get_lpr_rates")

    def get_money_supply(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/diaochatongjisi/116219/116319/index.html", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"indicators": ["M0", "M1", "M2"]},
                metadata={"source": "PBoC", "category": "money_supply"})
        except Exception as e:
            return handle_request_error(e, "PBoC", "get_money_supply")

    def get_series_categories(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "description": d} for n, d in self.SERIES_CATEGORIES.items()],
            metadata={"source": "PBoC", "count": len(self.SERIES_CATEGORIES)})
