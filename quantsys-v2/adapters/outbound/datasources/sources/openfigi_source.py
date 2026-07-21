"""OpenFIGI financial instrument identifier mapping data source.

Provides access to Bloomberg FIGI (Financial Instrument Global Identifier)
mapping service. Maps tickers, ISINs, CUSIPs, SEDOLs across exchanges.
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class OpenFIGISource(EconomicDataSource):
    """OpenFIGI (Bloomberg) financial instrument identifier data source.

    Maps between financial instrument identifiers: ticker ↔ ISIN ↔ CUSIP ↔
    SEDOL ↔ FIGI. Essential for multi-data-source integration where different
    providers use different identifiers for the same security.

    No API key required. Rate limit: ~25 requests/minute.
    """

    BASE_URL = "https://api.openfigi.com/v3"

    ID_TYPES = {
        "TICKER": "Stock ticker symbol",
        "ISIN": "International Securities Identification Number",
        "CUSIP": "CUSIP identifier (US/Canada)",
        "SEDOL": "SEDOL identifier (UK)",
        "FIGI": "Financial Instrument Global Identifier",
        "ID_BB_GLOBAL": "Bloomberg Global ID",
        "ID_BB_UNIQUE": "Bloomberg Unique ID",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="OpenFIGI", requires_api_key=False)
        self.api_key = api_key or os.getenv("OPENFIGI_API_KEY", "")
        self.session = SessionManager.get_session("openfigi")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.post(
                f"{self.BASE_URL}/search",
                json=[{"idType": "TICKER", "idValue": "AAPL", "exchCode": "US"}],
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "OpenFIGI"},
                metadata={"source": "OpenFIGI", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"OpenFIGI connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def get_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DataSourceResponse:
        return self.lookup("TICKER", series_id)

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        try:
            response = self.session.post(
                f"{self.BASE_URL}/search",
                json=[{"idType": "TICKER", "idValue": query.upper()}],
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            return DataSourceResponse.success_response(
                data=data[:limit] if isinstance(data, list) else data,
                metadata={"source": "OpenFIGI", "query": query},
            )
        except Exception as e:
            return handle_request_error(e, "OpenFIGI", "search_series")

    def lookup(
        self,
        id_type: str,
        id_value: str,
        exch_code: str = "",
    ) -> DataSourceResponse:
        """Map an identifier to all known equivalents.

        Args:
            id_type: Identifier type (TICKER, ISIN, CUSIP, SEDOL, FIGI)
            id_value: The identifier value to look up
            exch_code: Exchange code (e.g., 'US', 'LN', 'JP'). Optional for ISIN.

        Returns:
            DataSourceResponse with mapped identifiers
        """
        try:
            body = {"idType": id_type.upper(), "idValue": id_value.upper()}
            if exch_code:
                body["exchCode"] = exch_code.upper()

            response = self.session.post(
                f"{self.BASE_URL}/mapping",
                json=[body],
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "OpenFIGI", "id_type": id_type, "id_value": id_value},
            )
        except Exception as e:
            return handle_request_error(e, "OpenFIGI", "lookup")

    def batch_lookup(
        self,
        identifiers: List[Dict[str, str]],
    ) -> DataSourceResponse:
        """Batch map multiple identifiers at once.

        Args:
            identifiers: List of dicts with 'idType' and 'idValue' keys

        Returns:
            DataSourceResponse with mapped identifiers for all inputs
        """
        try:
            if len(identifiers) > 100:
                return DataSourceResponse.error_response(
                    error=f"Batch size exceeds 100 limit (got {len(identifiers)})"
                )
            response = self.session.post(
                f"{self.BASE_URL}/mapping",
                json=identifiers,
                timeout=60,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "OpenFIGI", "batch_size": len(identifiers)},
            )
        except Exception as e:
            return handle_request_error(e, "OpenFIGI", "batch_lookup")

    def get_id_types(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.ID_TYPES.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "OpenFIGI", "count": len(items)},
        )
