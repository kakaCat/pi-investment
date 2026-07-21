"""TradingView chart and market data source.

Provides access to TradingView chart data, technical analysis signals,
and market screener results. No API key required for public data.
"""

from typing import Optional, Dict, Any
import logging
import json

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class TradingViewSource(EconomicDataSource):
    """TradingView chart and market data source.

    Provides chart data (OHLCV), technical analysis summary (RSI, MACD,
    moving averages, oscillators), market screener results, symbol search,
    and exchange rate data. Uses public TradingView API endpoints.

    No API key required. Rate limited.
    """

    BASE_URL = "https://scanner.tradingview.com"
    CHART_URL = "https://saveload.tradingview.com"

    MARKETS = {
        "america": "US/Canada/Latin America stocks",
        "uk": "UK stocks",
        "europe": "European stocks",
        "asia": "Asian stocks",
        "crypto": "Cryptocurrencies",
        "forex": "Foreign exchange",
        "futures": "Futures contracts",
        "indices": "Global indices",
    }

    def __init__(self):
        super().__init__(name="TradingView", requires_api_key=False)
        self.session = SessionManager.get_session("tradingview")

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        try:
            response = self.session.get(
                f"{self.BASE_URL}/global/scan",
                params={"label-product": "forex", "limit": 1},
                timeout=10,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "TradingView"},
                metadata={"source": "TradingView"},
            )
        except Exception as e:
            logger.error(f"TradingView connection test failed: {e}")
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
            params: Dict[str, Any] = {"symbol": series_id, "resolution": "D"}
            if start_date:
                params["from"] = start_date
            if end_date:
                params["to"] = end_date

            response = self.session.get(
                f"{self.CHART_URL}/history", params=params, timeout=30
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "TradingView", "symbol": series_id},
            )
        except Exception as e:
            return handle_request_error(e, "TradingView", "get_series")

    def search_series(self, query: str, limit: int = 10) -> DataSourceResponse:
        try:
            response = self.session.post(
                f"{self.BASE_URL}/search",
                json={"text": query, "limit": limit},
                timeout=15,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "TradingView", "query": query},
            )
        except Exception as e:
            return handle_request_error(e, "TradingView", "search_series")

    def get_screener(
        self,
        market: str = "crypto",
        filter_name: str = "volume",
        limit: int = 50,
    ) -> DataSourceResponse:
        """Get market screener results.

        Args:
            market: Market type (america, crypto, forex, futures, etc.)
            filter_name: Sort filter (volume, change, market_cap)
            limit: Number of results

        Returns:
            DataSourceResponse with screener data
        """
        try:
            filter_map = {
                "volume": [{"left": "volume", "operation": "nempty"}],
                "change": [{"left": "change", "operation": "nempty"}],
                "market_cap": [{"left": "market_cap_basic", "operation": "nempty"}],
            }
            response = self.session.post(
                f"{self.BASE_URL}/{market}/scan",
                json={
                    "filter": filter_map.get(filter_name, filter_map["volume"]),
                    "options": {"lang": "en"},
                    "markets": [market],
                    "range": [0, limit],
                },
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "TradingView", "market": market},
            )
        except Exception as e:
            return handle_request_error(e, "TradingView", "get_screener")

    def get_technical_summary(self, symbol: str) -> DataSourceResponse:
        """Get technical analysis summary for a symbol.

        Includes oscillators (RSI, Stoch, MACD), moving averages, and pivot points.
        """
        try:
            response = self.session.get(
                f"{self.CHART_URL}/technicals",
                params={"symbol": symbol, "interval": "1d"},
                timeout=30,
            )
            response.raise_for_status()
            return DataSourceResponse.success_response(
                data=response.json(),
                metadata={"source": "TradingView", "symbol": symbol},
            )
        except Exception as e:
            return handle_request_error(e, "TradingView", "get_technical_summary")

    def get_markets(self) -> DataSourceResponse:
        items = [{"id": k, "description": v} for k, v in self.MARKETS.items()]
        return DataSourceResponse.success_response(
            data=items,
            metadata={"source": "TradingView", "count": len(items)},
        )
