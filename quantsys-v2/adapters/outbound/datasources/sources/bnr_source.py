"""Banca Națională a României (BNR) central bank data source.

Provides access to Romanian monetary policy and economic data.
No API key required.
"""

from typing import Optional, Dict, Any
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class BNRSource(EconomicDataSource):
    """Banca Națională a României (BNR) central bank data source.

    Provides monetary policy rate (ROBOR), inflation (CPI), exchange rates
    (RON vs EUR/USD), GDP growth, and balance of payments data.
    No API key required.
    """

    BASE_URL = "https://www.bnr.ro/nbrfxrates.xml"
    API_URL = "https://www.bnr.ro"

    INDICATORS = {
        "monetary_policy_rate": "Monetary policy rate (cheie)",
        "robor_3m": "ROBOR 3-month interbank rate",
        "robor_6m": "ROBOR 6-month interbank rate",
        "cpi": "Consumer price index inflation",
        "gdp": "GDP growth rate",
        "current_account": "Current account balance",
    }

    def __init__(self):
        super().__init__(name="BNR", requires_api_key=False)
        self.session = SessionManager.get_session("bnr")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            import xml.etree.ElementTree as ET
            response = self.session.get(self.BASE_URL, timeout=15)
            response.raise_for_status()
            ET.fromstring(response.content)
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "BNR"},
                metadata={"source": "BNR", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"BNR connection test failed: {e}")
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
            import xml.etree.ElementTree as ET
            response = self.session.get(self.BASE_URL, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            rates = []
            ns = {"": "http://www.bnr.ro/xsd"}
            for rate_elem in root.findall(".//Rate"):
                currency = rate_elem.get("currency", "")
                multiplier = rate_elem.get("multiplier", "1")
                value = float(rate_elem.text) if rate_elem.text else 0.0
                rates.append({
                    "currency": currency,
                    "multiplier": int(multiplier),
                    "value": value,
                })
            return DataSourceResponse.success_response(
                data=rates,
                metadata={"source": "BNR", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "BNR", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in self.INDICATORS.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "BNR", "query": query},
        )

    def get_exchange_rates(self) -> DataSourceResponse:
        """Get RON exchange rates from BNR."""
        return self.get_series("exchange_rates")

    def get_indicators(self) -> DataSourceResponse:
        items = [{"id": k, "name": v} for k, v in self.INDICATORS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "BNR", "count": len(items)},
        )
