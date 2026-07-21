"""SEC EDGAR company filings data source.
Provides access to SEC filings (10-K, 10-Q, 8-K, etc.) from public companies. No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class SECEDGARSource(EconomicDataSource):
    """SEC EDGAR public company filings data source.
    Provides 10-K, 10-Q, 8-K, XBRL financials, insider trading data."""

    BASE_URL = "https://data.sec.gov"
    FILING_TYPES = ["10-K", "10-Q", "8-K", "20-F", "6-K", "S-1", "13F-HR", "3", "4", "5"]

    def __init__(self):
        super().__init__(name="SEC_EDGAR", requires_api_key=False)
        self.session = SessionManager.get_session("sec_edgar")
        self.session.headers.update({"User-Agent": "QuantSysV2/1.0 (research@quant.dev)"})

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            r = self.session.get("https://data.sec.gov/submissions/CIK0000320193.json", timeout=10)
            r.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected"}, metadata={"source": "SEC"})
        except Exception as e:
            return DataSourceResponse.error_response(error=str(e))

    def get_company_submissions(self, cik: str) -> DataSourceResponse:
        try:
            cik_padded = cik.zfill(10)
            r = self.session.get(f"https://data.sec.gov/submissions/CIK{cik_padded}.json", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "SEC_EDGAR", "cik": cik_padded})
        except Exception as e:
            return handle_request_error(e, "SEC", "get_company_submissions")

    def get_company_facts(self, cik: str) -> DataSourceResponse:
        try:
            cik_padded = cik.zfill(10)
            r = self.session.get(f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik_padded}.json", timeout=30)
            r.raise_for_status()
            return DataSourceResponse.success_response(data=r.json(),
                metadata={"source": "SEC_EDGAR", "cik": cik_padded})
        except Exception as e:
            return handle_request_error(e, "SEC", "get_company_facts")

    def get_filing_types(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(data=self.FILING_TYPES,
            metadata={"source": "SEC", "count": len(self.FILING_TYPES)})
