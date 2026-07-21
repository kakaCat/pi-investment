"""Bank of England (BoE) central bank data source.
Provides UK monetary, financial, and statistical data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BankOfEnglandSource(EconomicDataSource):
    """Bank of England statistical data source.
    Bank Rate, M4 money supply, GBP exchange rates, gilt yields, credit conditions."""

    BASE_URL = "https://www.bankofengland.co.uk/boeapps/database"
    SERIES_GROUPS = {"bank_rate": "IUMABEDR", "m4": "LPMB3VQ", "gbp_usd": "XUMAUSS",
        "gbp_eur": "XUMAERS", "10yr_yield": "IUMAMNPY", "cpi": "D7G7"}

    def __init__(self):
        super().__init__(name="BankOfEngland", requires_api_key=False)
        self.session = SessionManager.get_session("boe")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/FromShowColumnsSeries.asp",
                params={"CSVF": "TN", "SeriesCodes": "IUMABEDR", "UsingCodes": "Y"}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "BoE"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_series(self, series_code: str) -> DataSourceResponse:
        try:
            params = {"CSVF": "TN", "SeriesCodes": series_code, "UsingCodes": "Y"}
            r = self.session.get(f"{self.BASE_URL}/FromShowColumnsSeries.asp", params=params, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"csv_data": r.text},
                metadata={"source": "BankOfEngland", "series_code": series_code})
        except Exception as e:
            return handle_request_error(e, "BankOfEngland", "get_series")

    def get_bank_rate(self) -> DataSourceResponse:
        return self.get_series("IUMABEDR")

    def get_exchange_rates(self) -> DataSourceResponse:
        return self.get_series("XUMAUSS,XUMAERS,XUMADSS,XUMAJYS")

    def get_series_groups(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "code": c} for n, c in self.SERIES_GROUPS.items()],
            metadata={"source": "BankOfEngland", "count": len(self.SERIES_GROUPS)})
