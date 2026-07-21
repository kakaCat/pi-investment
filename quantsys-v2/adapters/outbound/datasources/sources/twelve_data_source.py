"""Twelve Data market data source.

Provides access to real-time and historical stock, forex, crypto, and
technical indicator data. API key required (free tier available).
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class TwelveDataSource(EconomicDataSource):
    """Twelve Data market data source.

    Provides real-time/historical OHLCV for stocks, forex, crypto, ETFs, and
    indices (100K+ instruments). Also delivers 100+ technical indicators,
    earnings, key statistics, and time series analysis.

    API key required. Free tier: 800 requests/day. https://twelvedata.com
    """

    BASE_URL = "https://api.twelvedata.com"

    INDICATORS = [
        "rsi", "macd", "sma", "ema", "bbands", "stoch", "adx", "obv",
        "atr", "cci", "williams", "mfi", "vwap", "ichimoku",
    ]

    def __init__(self, api_key: Optional[str] = None):
        import os
        super().__init__(name="TwelveData", requires_api_key=True)
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY", "")
        self.session = SessionManager.get_session("twelve_data")

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.warning("Twelve Data API key not configured. Register at https://twelvedata.com")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/time_series",
                params={"symbol": "AAPL", "interval": "1day", "apikey": self.api_key, "outputsize": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "TwelveData"},
                metadata={"source": "TwelveData", "base_url": self.BASE_URL},
            )
        except Exception as e:
            logger.error(f"Twelve Data connection test failed: {e}")
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
            params: Dict[str, Any] = {
                "symbol": series_id,
                "interval": "1day",
                "apikey": self.api_key,
                "outputsize": 5000,
            }
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = self.session.get(
                f"{self.BASE_URL}/time_series", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "TwelveData", "symbol": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "TwelveData", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/symbol_search",
                params={"symbol": query, "apikey": self.api_key},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json().get("data", [])
            return DataSourceResponse.success_response(
                data=data[:limit],
                metadata={"source": "TwelveData", "query": query},
            )
        except Exception as e:
            return handle_request_error(e, "TwelveData", "search_series")

    def get_realtime_quote(self, symbol: str) -> DataSourceResponse:
        """Get real-time quote for a symbol."""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/quote",
                params={"symbol": symbol, "apikey": self.api_key},
                timeout=15,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "TwelveData", "symbol": symbol},
            )
        except Exception as e:
            return handle_request_error(e, "TwelveData", "get_realtime_quote")

    def get_technical_indicator(
        self,
        symbol: str,
        indicator: str = "rsi",
        interval: str = "1day",
    ) -> DataSourceResponse:
        """Get technical indicator values.

        Args:
            symbol: Ticker symbol
            indicator: One of rsi, macd, sma, ema, bbands, stoch, adx, etc.
            interval: Time interval (1min, 5min, 15min, 30min, 1h, 1day, 1week, 1month)
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/{indicator}",
                params={"symbol": symbol, "interval": interval, "apikey": self.api_key},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "TwelveData", "symbol": symbol, "indicator": indicator},
            )
        except Exception as e:
            return handle_request_error(e, "TwelveData", "get_technical_indicator")

    def get_indicators(self) -> DataSourceResponse:
        return DataSourceResponse.success_response(
            data=self.INDICATORS,
            metadata={"source": "TwelveData", "count": len(self.INDICATORS)},
        )
