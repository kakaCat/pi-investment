"""Databento market data source.

Provides access to institutional-grade historical and real-time market data
across equities, futures, and options. API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class DatabentoSource(EconomicDataSource):
    """Databento market data source.

    Provides tick-level and aggregated market data for US equities, futures
    (CME, CBOT, COMEX, NYMEX), and options. Supports MBO (market by order),
    MBP (market by price), OHLCV bars, and corporate actions.

    API key required. Sign up at https://databento.com
    """

    BASE_URL = "https://hist.databento.com/v0"

    DATASETS = {
        "XNAS.ITCH": "Nasdaq TotalView-ITCH equities",
        "XNYS.NYSE": "NYSE integrated feed equities",
        "GLBX.MDP3": "CME Group market data platform (futures/options)",
        "OPRA": "Options price reporting authority",
        "IFEU.IMPACT": "ICE Futures Europe",
    }

    SCHEMAS = {
        "trades": "Tick-level trade data",
        "ohlcv-1s": "1-second OHLCV bars",
        "ohlcv-1m": "1-minute OHLCV bars",
        "ohlcv-1h": "1-hour OHLCV bars",
        "ohlcv-1d": "Daily OHLCV bars",
        "mbp-1": "Market by price (top of book)",
        "tbbo": "Top of book bid/ask",
        "status": "Trading status events",
    }

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="Databento", requires_api_key=True)
        self.api_key = api_key or os.getenv("DATABENTO_API_KEY", "")
        self.session = SessionManager.get_session("databento")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("Databento API key not configured. Sign up at https://databento.com")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/list",
                headers={"accept": "application/json"},
                auth=(self.api_key, ""),
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Databento"},
                metadata={"source": "Databento", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Databento connection test failed: {e}")
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
            params: Dict[str, Any] = {"dataset": series_id}
            if start_date:
                params["start"] = start_date
            if end_date:
                params["end"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/timeseries.get_range",
                params=params,
                headers={"accept": "application/json"},
                auth=(self.api_key, ""),
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Databento", "series_id": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "Databento", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        matches = [
            {"id": k, "name": v} for k, v in {**self.DATASETS, **self.SCHEMAS}.items()
            if query.lower() in k.lower() or query.lower() in v.lower()
        ]
        return DataSourceResponse.success_response(
            data=matches[:limit],
            metadata={"source": "Databento", "query": query},
        )

    def get_datasets(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.DATASETS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "Databento", "count": len(items)},
        )

    def get_schemas(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.SCHEMAS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "Databento", "count": len(items)},
        )

    def get_ohlcv(
        self,
        symbol: str,
        schema: str = "ohlcv-1d",
        start_date: str = "2024-01-01",
        end_date: str = "2025-12-31",
    ) -> DataSourceResponse:
        """Get OHLCV bars for a symbol.

        Args:
            symbol: Ticker symbol
            schema: Bar size - 'ohlcv-1s', 'ohlcv-1m', 'ohlcv-1h', 'ohlcv-1d'
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        """
        try:
            params = {
                "dataset": symbol,
                "schema": schema,
                "start": start_date,
                "end": end_date,
            }
            response = self.session.get(
                f"{self.BASE_URL}/timeseries.get_range",
                params=params,
                auth=(self.api_key, ""),
                timeout=60,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "Databento", "symbol": symbol, "schema": schema},
            )
        except Exception as e:
            return handle_request_error(e, "Databento", "get_ohlcv")
