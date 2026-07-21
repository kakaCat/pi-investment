"""Banco Central do Brasil (BCB) central bank data source.
Provides Brazilian monetary, financial, and economic data. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BancoCentralBrasilSource(EconomicDataSource):
    """Banco Central do Brasil data source.
    SELIC rate, IPCA inflation, BRL/USD PTAX, Focus survey, international reserves."""

    BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"
    OLINDA_URL = "https://olinda.bcb.gov.br/olinda/servico"
    SERIES_CODES = {"selic_target": 432, "ipca": 433, "brl_usd_ptax": 1,
        "foreign_reserves": 3546, "gdp": 7326, "unemployment": 24369}

    def __init__(self):
        super().__init__(name="BancoCentralBrasil", requires_api_key=False)
        self.session = SessionManager.get_session("bcb")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/432/dados", params={"formato": "json"}, timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(data={"status": "connected"}, metadata={"source": "BCB"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_series(self, series_code: int = 432) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.BASE_URL}/{series_code}/dados",
                params={"formato": "json"}, timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "BCB_SGS", "series_code": series_code})
        except Exception as e:
            return handle_request_error(e, "BCB", "get_series")

    def get_selic_rate(self) -> DataSourceResponse:
        return self.get_series(432)

    def get_ipca(self) -> DataSourceResponse:
        return self.get_series(433)

    def get_exchange_rate(self) -> DataSourceResponse:
        return self.get_series(1)

    def get_focus_report(self) -> DataSourceResponse:
        try:
            r = self.session.get(f"{self.OLINDA_URL}/Expectativas/ver/ExpectativasMercadoAnuais", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "BCB_Focus"})
        except Exception as e:
            return handle_request_error(e, "BCB", "get_focus_report")

    def get_series_codes(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=[{"name": n, "code": c} for n, c in self.SERIES_CODES.items()],
            metadata={"source": "BCB", "count": len(self.SERIES_CODES)})
