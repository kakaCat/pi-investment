"""IEX Cloud data source.

Provides US stock market data, news, earnings, financials, and economic indicators.
Free tier available with limited requests.
"""

import os
from typing import List, Optional
import requests

from ..base import MarketDataSource, DataSourceResponse


class IEXCloudSource(MarketDataSource):
    """IEX Cloud market data source.

    Features:
    - Real-time and delayed stock quotes
    - Historical price data
    - Company financials and earnings
    - News articles
    - Economic indicators
    - Batch requests

    API Key: Required (free tier available)
    Rate Limits: Varies by plan
    """

    BASE_URL = "https://cloud.iexapis.com/stable"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="IEX Cloud", requires_api_key=True)
        self.api_key = api_key or os.environ.get('IEX_CLOUD_API_KEY', '')
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=3
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def validate_config(self) -> bool:
        """Validate API key is configured."""
        return bool(self.api_key)

    def test_connection(self) -> DataSourceResponse:
        """Test connection by fetching a quote."""
        try:
            if not self.validate_config():
                return DataSourceResponse.error_response(
                    "IEX Cloud API key not configured. Set IEX_CLOUD_API_KEY environment variable."
                )

            # Test with a simple quote request
            result = self.get_realtime_quote(["AAPL"])
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected"},
                    metadata={"message": "IEX Cloud API connection successful"}
                )
            return result

        except Exception as e:
            return self._handle_error("test_connection", e)

    def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make API request with error handling."""
        if params is None:
            params = {}

        params['token'] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}" if not endpoint.startswith('http') else endpoint

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get company information.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            DataSourceResponse with company data
        """
        try:
            data = self._make_request(f"stock/{symbol.upper()}/company")

            if not data:
                return DataSourceResponse.error_response(
                    f"No data found for symbol: {symbol}"
                )

            info = {
                'symbol': data.get('symbol'),
                'name': data.get('companyName'),
                'exchange': data.get('exchange'),
                'industry': data.get('industry'),
                'website': data.get('website'),
                'description': data.get('description'),
                'ceo': data.get('CEO'),
                'sector': data.get('sector'),
                'employees': data.get('employees'),
                'address': data.get('address'),
                'city': data.get('city'),
                'state': data.get('state'),
                'zip': data.get('zip'),
                'country': data.get('country'),
                'phone': data.get('phone')
            }

            return DataSourceResponse.success_response(
                info,
                metadata={'symbol': symbol, 'source': 'IEX Cloud'}
            )

        except Exception as e:
            return self._handle_error("get_stock_info", e)

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get OHLCV kline/candlestick data.

        Args:
            symbol: Stock ticker symbol
            period: Time period - "1m", "3m", "6m", "1y", "2y", "5y", "max", "ytd"
            start_date: Start date (YYYYMMDD format) - not used, use period instead
            end_date: End date (YYYYMMDD format) - not used, use period instead

        Returns:
            DataSourceResponse with OHLCV data
        """
        try:
            # Map period format
            range_map = {
                "daily": "1m",
                "weekly": "3m",
                "monthly": "1y"
            }
            range_param = range_map.get(period, period)

            data = self._make_request(f"stock/{symbol.upper()}/chart/{range_param}")

            if not data:
                return DataSourceResponse.error_response(
                    f"No chart data found for {symbol}"
                )

            # Parse OHLCV data
            klines = []
            for item in data:
                kline = {
                    'date': item.get('date'),
                    'open': item.get('open'),
                    'high': item.get('high'),
                    'low': item.get('low'),
                    'close': item.get('close'),
                    'volume': item.get('volume')
                }
                klines.append(kline)

            return DataSourceResponse.success_response(
                klines,
                metadata={
                    'symbol': symbol,
                    'period': period,
                    'count': len(klines)
                }
            )

        except Exception as e:
            return self._handle_error("get_klines", e)

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """Get real-time quotes for symbols.

        Args:
            symbols: List of stock ticker symbols

        Returns:
            DataSourceResponse with real-time quote data
        """
        try:
            quotes = []

            for symbol in symbols:
                data = self._make_request(f"stock/{symbol.upper()}/quote")

                if not data:
                    continue

                quote = {
                    'symbol': data.get('symbol'),
                    'name': data.get('companyName'),
                    'price': data.get('latestPrice'),
                    'change': data.get('change'),
                    'change_percent': data.get('changePercent'),
                    'volume': data.get('latestVolume'),
                    'open': data.get('open'),
                    'high': data.get('high'),
                    'low': data.get('low'),
                    'previous_close': data.get('previousClose'),
                    'market_cap': data.get('marketCap'),
                    'pe_ratio': data.get('peRatio'),
                    'week_52_high': data.get('week52High'),
                    'week_52_low': data.get('week52Low'),
                    'ytd_change': data.get('ytdChange'),
                    'latest_time': data.get('latestTime'),
                    'latest_source': data.get('latestSource')
                }

                quotes.append(quote)

            if not quotes:
                return DataSourceResponse.error_response(
                    f"No quote data found for symbols: {', '.join(symbols)}"
                )

            return DataSourceResponse.success_response(
                quotes,
                metadata={'symbols': symbols, 'count': len(quotes)}
            )

        except Exception as e:
            return self._handle_error("get_realtime_quote", e)

    def get_financials(
        self,
        symbol: str,
        period: str = "annual"
    ) -> DataSourceResponse:
        """Get financial statements.

        Args:
            symbol: Stock ticker symbol
            period: Period - "annual" or "quarterly"

        Returns:
            DataSourceResponse with financial data
        """
        try:
            params = {'period': period}

            data = self._make_request(f"stock/{symbol.upper()}/financials", params)

            if not data or 'financials' not in data:
                return DataSourceResponse.error_response(
                    f"No financial data found for {symbol}"
                )

            return DataSourceResponse.success_response(
                data['financials'],
                metadata={'symbol': symbol, 'period': period}
            )

        except Exception as e:
            return self._handle_error("get_financials", e)

    def get_earnings(
        self,
        symbol: str,
        last: int = 4
    ) -> DataSourceResponse:
        """Get earnings data.

        Args:
            symbol: Stock ticker symbol
            last: Number of quarters to retrieve

        Returns:
            DataSourceResponse with earnings data
        """
        try:
            data = self._make_request(f"stock/{symbol.upper()}/earnings/{last}")

            if not data or 'earnings' not in data:
                return DataSourceResponse.error_response(
                    f"No earnings data found for {symbol}"
                )

            return DataSourceResponse.success_response(
                data['earnings'],
                metadata={'symbol': symbol, 'quarters': last}
            )

        except Exception as e:
            return self._handle_error("get_earnings", e)

    def get_news(
        self,
        symbol: str,
        last: int = 10
    ) -> DataSourceResponse:
        """Get company news.

        Args:
            symbol: Stock ticker symbol
            last: Number of news items to retrieve

        Returns:
            DataSourceResponse with news articles
        """
        try:
            data = self._make_request(f"stock/{symbol.upper()}/news/last/{last}")

            if not data:
                return DataSourceResponse.error_response(
                    f"No news found for {symbol}"
                )

            news = []
            for article in data:
                news.append({
                    'datetime': article.get('datetime'),
                    'headline': article.get('headline'),
                    'source': article.get('source'),
                    'url': article.get('url'),
                    'summary': article.get('summary'),
                    'related': article.get('related'),
                    'image': article.get('image')
                })

            return DataSourceResponse.success_response(
                news,
                metadata={'symbol': symbol, 'count': len(news)}
            )

        except Exception as e:
            return self._handle_error("get_news", e)

    def get_economic_data(self, indicator: str = "US_FEDFUNDS") -> DataSourceResponse:
        """Get economic indicator data.

        Args:
            indicator: Economic indicator code (e.g., "US_FEDFUNDS", "US_GDP", "US_UNEMPLOYMENT")

        Returns:
            DataSourceResponse with economic data
        """
        try:
            data = self._make_request(f"data-points/market/{indicator}")

            if data is None:
                return DataSourceResponse.error_response(
                    f"No data found for indicator: {indicator}"
                )

            return DataSourceResponse.success_response(
                {'value': data},
                metadata={'indicator': indicator}
            )

        except Exception as e:
            return self._handle_error("get_economic_data", e)

    def get_batch(
        self,
        symbols: List[str],
        types: str = "quote,news"
    ) -> DataSourceResponse:
        """Get batch data for multiple symbols.

        Args:
            symbols: List of stock ticker symbols
            types: Comma-separated data types (e.g., "quote,news,chart")

        Returns:
            DataSourceResponse with batch data
        """
        try:
            params = {
                'symbols': ','.join(symbols),
                'types': types
            }

            data = self._make_request("stock/market/batch", params)

            if not data:
                return DataSourceResponse.error_response(
                    f"No batch data found for symbols: {', '.join(symbols)}"
                )

            return DataSourceResponse.success_response(
                data,
                metadata={'symbols': symbols, 'types': types}
            )

        except Exception as e:
            return self._handle_error("get_batch", e)

    def search_symbols(self, query: str) -> DataSourceResponse:
        """Search for stock symbols.

        Args:
            query: Search query (company name or symbol fragment)

        Returns:
            DataSourceResponse with matching symbols
        """
        try:
            data = self._make_request(f"search/{query}")

            if not data:
                return DataSourceResponse.error_response(
                    f"No matches found for: {query}"
                )

            matches = []
            for item in data:
                matches.append({
                    'symbol': item.get('symbol'),
                    'name': item.get('securityName'),
                    'exchange': item.get('exchange'),
                    'type': item.get('securityType'),
                    'region': item.get('region')
                })

            return DataSourceResponse.success_response(
                matches,
                metadata={'query': query, 'count': len(matches)}
            )

        except Exception as e:
            return self._handle_error("search_symbols", e)
