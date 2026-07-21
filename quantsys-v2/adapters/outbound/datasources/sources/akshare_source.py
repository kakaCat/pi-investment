"""AkShare data source with enhanced error handling and connection pooling.

Wraps the existing AkShareAdapter with the new data source architecture.
"""

from typing import List, Optional
import logging

try:
    import akshare as ak
except ImportError:
    ak = None

from adapters.outbound.datasources.base import MarketDataSource, DataSourceResponse
from adapters.outbound.datasources.error_handler import safe_call, validate_symbol

logger = logging.getLogger(__name__)


class AkShareSource(MarketDataSource):
    """AkShare data source implementation.

    Direct akshare integration without adapter dependency to avoid TA-Lib issues.
    """

    def __init__(self):
        super().__init__(name="AkShare", requires_api_key=False)
        # Don't use AkShareAdapter to avoid TA-Lib dependency
        self.adapter = None

    def validate_config(self) -> bool:
        """Validate AkShare is available."""
        if ak is None:
            self.logger.error("AkShare is not installed. Install with: pip install akshare")
            return False
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test AkShare connection by fetching a simple dataset."""
        if not self.validate_config():
            return DataSourceResponse.error_response("AkShare not installed")

        try:
            # Try to fetch Shanghai index data (simple test)
            result = safe_call(
                ak.stock_zh_index_spot_em,
                max_retries=1
            )
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected", "test": "passed"},
                    metadata={"source": "akshare"}
                )
            return result
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get stock information.

        Args:
            symbol: Stock symbol (e.g., "000001.SZ")

        Returns:
            DataSourceResponse with stock info
        """
        self._log_request("get_stock_info", {"symbol": symbol})

        if not validate_symbol(symbol):
            return DataSourceResponse.error_response(f"Invalid symbol: {symbol}")

        try:
            import akshare as ak
            # 获取实时行情（包含基本信息）
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                # 移除后缀获取纯代码
                clean_symbol = symbol.split('.')[0]
                stock = df[df['代码'] == clean_symbol]
                if not stock.empty:
                    info = stock.iloc[0].to_dict()
                    self._log_success("get_stock_info", 1)
                    return DataSourceResponse.success_response(info)
            return DataSourceResponse.error_response(f"Stock {symbol} not found")
        except Exception as e:
            return self._handle_error("get_stock_info", e)

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get OHLCV kline data.

        Args:
            symbol: Stock symbol
            period: Period (daily/weekly/monthly)
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)

        Returns:
            DataSourceResponse with kline data
        """
        self._log_request("get_klines", {
            "symbol": symbol,
            "period": period,
            "start_date": start_date,
            "end_date": end_date
        })

        if not validate_symbol(symbol):
            return DataSourceResponse.error_response(f"Invalid symbol: {symbol}")

        try:
            klines = self.adapter.get_klines(symbol, period, start_date, end_date)
            if klines:
                self._log_success("get_klines", len(klines))
                return DataSourceResponse.success_response(
                    klines,
                    metadata={
                        "symbol": symbol,
                        "period": period,
                        "start_date": start_date,
                        "end_date": end_date
                    }
                )
            return DataSourceResponse.error_response("No kline data returned")
        except Exception as e:
            return self._handle_error("get_klines", e)

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

        # Validate symbols
        invalid = [s for s in symbols if not validate_symbol(s)]
        if invalid:
            return DataSourceResponse.error_response(
                f"Invalid symbols: {', '.join(invalid)}"
            )

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
        """Get index data.

        Args:
            index_code: Index code (e.g., "000001" for Shanghai Composite)
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)

        Returns:
            DataSourceResponse with index data
        """
        self._log_request("get_index_data", {
            "index_code": index_code,
            "start_date": start_date,
            "end_date": end_date
        })

        try:
            data = self.adapter.get_index_data(index_code, start_date, end_date)
            if data:
                self._log_success("get_index_data", len(data))
                return DataSourceResponse.success_response(
                    data,
                    metadata={"index_code": index_code}
                )
            return DataSourceResponse.error_response("No index data returned")
        except Exception as e:
            return self._handle_error("get_index_data", e)

    def get_sector_list(self) -> DataSourceResponse:
        """Get list of sectors/industries.

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

    def get_concept_list(self) -> DataSourceResponse:
        """Get list of concept sectors.

        Returns:
            DataSourceResponse with concept list
        """
        self._log_request("get_concept_list", {})

        try:
            import akshare as ak
            df = ak.stock_board_concept_name_em()
            if df is not None and not df.empty:
                concepts = df.to_dict('records')
                self._log_success("get_concept_list", len(concepts))
                return DataSourceResponse.success_response(concepts)
            return DataSourceResponse.error_response("No concept data returned")
        except Exception as e:
            return self._handle_error("get_concept_list", e)

    def get_concept_stocks(self, concept: str) -> DataSourceResponse:
        """Get stocks in a concept sector.

        Args:
            concept: Concept name (e.g., '人工智能', '新能源')

        Returns:
            DataSourceResponse with stock list
        """
        self._log_request("get_concept_stocks", {"concept": concept})

        try:
            import akshare as ak
            df = ak.stock_board_concept_cons_em(symbol=concept)
            if df is not None and not df.empty:
                stocks = df.to_dict('records')
                self._log_success("get_concept_stocks", len(stocks))
                return DataSourceResponse.success_response(stocks)
            return DataSourceResponse.error_response(f"No stocks found for concept: {concept}")
        except Exception as e:
            return self._handle_error("get_concept_stocks", e)

    def get_north_flow(
        self,
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get northbound capital flow data.

        Args:
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)

        Returns:
            DataSourceResponse with flow data
        """
        self._log_request("get_north_flow", {
            "start_date": start_date,
            "end_date": end_date
        })

        try:
            data = self.adapter.get_north_flow(start_date, end_date)
            if data:
                self._log_success("get_north_flow", len(data))
                return DataSourceResponse.success_response(data)
            return DataSourceResponse.error_response("No flow data returned")
        except Exception as e:
            return self._handle_error("get_north_flow", e)

    def get_market_news(
        self,
        symbol: str = "",
        limit: int = 20
    ) -> DataSourceResponse:
        """Get market news.

        Args:
            symbol: Stock symbol (empty for general market news)
            limit: Maximum number of news items

        Returns:
            DataSourceResponse with news data
        """
        self._log_request("get_market_news", {"symbol": symbol, "limit": limit})

        try:
            news = self.adapter.get_market_news(symbol, limit)
            if news:
                self._log_success("get_market_news", len(news))
                return DataSourceResponse.success_response(news)
            return DataSourceResponse.error_response("No news data returned")
        except Exception as e:
            return self._handle_error("get_market_news", e)

    def get_financial_data(self, symbol: str) -> DataSourceResponse:
        """Get financial data for a stock.

        Args:
            symbol: Stock symbol

        Returns:
            DataSourceResponse with financial data
        """
        self._log_request("get_financial_data", {"symbol": symbol})

        if not validate_symbol(symbol):
            return DataSourceResponse.error_response(f"Invalid symbol: {symbol}")

        try:
            import akshare as ak
            # 移除后缀获取纯代码
            clean_symbol = symbol.split('.')[0]

            # 尝试获取财务分析指标
            df = ak.stock_financial_analysis_indicator(symbol=clean_symbol)
            if df is not None and not df.empty:
                data = df.to_dict('records')
                self._log_success("get_financial_data", 1)
                return DataSourceResponse.success_response({
                    'symbol': symbol,
                    'indicators': data,
                    'source': 'akshare'
                })
            return DataSourceResponse.error_response(
                f"No financial data available for {symbol}"
            )
        except Exception as e:
            return self._handle_error("get_financial_data", e)
