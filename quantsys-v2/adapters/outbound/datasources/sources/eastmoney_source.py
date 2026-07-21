"""East Money data source with enhanced error handling.

Wraps EastMoneyAdapter with the unified data source architecture.
"""

from typing import List
import logging

from adapters.outbound.datasources.base import MarketDataSource, DataSourceResponse
from domain.quantlib.adapters.eastmoney_adapter import EastMoneyAdapter

logger = logging.getLogger(__name__)


class EastMoneySource(MarketDataSource):
    """East Money data source implementation.

    Primary strength: Comprehensive market data (quotes, sectors, fund flow)
    Coverage: A-share, indices, sectors
    """

    def __init__(self):
        super().__init__(name="EastMoney", requires_api_key=False)
        self.adapter = EastMoneyAdapter()

    def validate_config(self) -> bool:
        """Validate EastMoney adapter is available."""
        return True  # No special config needed

    def test_connection(self) -> DataSourceResponse:
        """Test EastMoney connection by fetching a quote."""
        try:
            # Try to fetch a quote
            result = self.adapter.get_realtime_quote(["600000.SH"])
            if result:
                return DataSourceResponse.success_response(
                    {"status": "connected", "test": "passed"},
                    metadata={"source": "eastmoney"}
                )
            return DataSourceResponse.error_response("No data returned")
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get stock information."""
        self._log_request("get_stock_info", {"symbol": symbol})

        try:
            info = self.adapter.get_stock_info(symbol)
            if info:
                self._log_success("get_stock_info", 1)
                return DataSourceResponse.success_response(info)
            return DataSourceResponse.error_response("No stock info returned")
        except Exception as e:
            return self._handle_error("get_stock_info", e)

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get K-line data (not well supported by EastMoney yet)."""
        return DataSourceResponse.error_response(
            "K-line data not yet implemented for EastMoney source"
        )

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """Get real-time quotes.

        Args:
            symbols: List of stock symbols

        Returns:
            DataSourceResponse with quote data
        """
        self._log_request("get_realtime_quote", {"symbols": symbols})

        if not symbols:
            return DataSourceResponse.error_response("No symbols provided")

        try:
            quotes = self.adapter.get_realtime_quote(symbols)
            if quotes:
                self._log_success("get_realtime_quote", len(quotes))
                return DataSourceResponse.success_response(
                    quotes,
                    metadata={"symbols": symbols}
                )
            return DataSourceResponse.error_response("No quote data returned")
        except Exception as e:
            return self._handle_error("get_realtime_quote", e)

    def get_index_data(
        self,
        index_code: str,
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get index data (not yet implemented)."""
        return DataSourceResponse.error_response(
            "Index data not yet implemented for EastMoney source"
        )

    def get_sector_list(self) -> DataSourceResponse:
        """Get sector list (EastMoney's strength).

        Returns:
            DataSourceResponse with sector list
        """
        self._log_request("get_sector_list", {})

        try:
            sectors = self.adapter.get_sector_list()
            if sectors:
                self._log_success("get_sector_list", len(sectors))
                return DataSourceResponse.success_response(sectors)
            return DataSourceResponse.error_response("No sector data returned")
        except Exception as e:
            return self._handle_error("get_sector_list", e)

    def get_north_flow(
        self,
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get north flow data (not yet implemented)."""
        return DataSourceResponse.error_response(
            "North flow data not yet implemented for EastMoney source"
        )

    def get_market_news(
        self,
        symbol: str = "",
        limit: int = 20
    ) -> DataSourceResponse:
        """Get market news (not yet implemented)."""
        return DataSourceResponse.error_response(
            "Market news not yet implemented for EastMoney source"
        )

    def get_financial_data(self, symbol: str) -> DataSourceResponse:
        """Get financial data (not yet implemented)."""
        return DataSourceResponse.error_response(
            "Financial data not yet implemented for EastMoney source"
        )
