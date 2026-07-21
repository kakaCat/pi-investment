"""Tiingo data source.

Provides EOD stock prices, intraday IEX data, crypto prices, forex, and news.
Generous free tier available.
"""

import os
from typing import List, Optional
import requests

from ..base import MarketDataSource, DataSourceResponse


class TiingoSource(MarketDataSource):
    """Tiingo market data source.

    Features:
    - EOD (End of Day) stock prices
    - Intraday IEX data
    - Cryptocurrency prices
    - Forex rates
    - News articles
    - Ticker metadata

    API Key: Required (generous free tier)
    Rate Limits: Varies by plan
    """

    BASE_URL = "https://api.tiingo.com"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="Tiingo", requires_api_key=True)
        self.api_key = api_key or os.environ.get('TIINGO_API_KEY', '')
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
        """Test connection by fetching ticker metadata."""
        try:
            if not self.validate_config():
                return DataSourceResponse.error_response(
                    "Tiingo API key not configured. Set TIINGO_API_KEY environment variable."
                )

            # Test with a simple metadata request
            result = self.get_stock_info("AAPL")
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected"},
                    metadata={"message": "Tiingo API connection successful"}
                )
            return result

        except Exception as e:
            return self._handle_error("test_connection", e)

    def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make API request with error handling."""
        if params is None:
            params = {}

        url = f"{self.BASE_URL}/{endpoint}" if not endpoint.startswith('http') else endpoint

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_key}"
        }

        response = self.session.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        return response.json()

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get ticker metadata and information.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            DataSourceResponse with ticker metadata
        """
        try:
            data = self._make_request(f"tiingo/daily/{symbol.upper()}")

            if not data:
                return DataSourceResponse.error_response(
                    f"No data found for symbol: {symbol}"
                )

            info = {
                'symbol': data.get('ticker'),
                'name': data.get('name'),
                'exchange': data.get('exchangeCode'),
                'description': data.get('description'),
                'start_date': data.get('startDate'),
                'end_date': data.get('endDate')
            }

            return DataSourceResponse.success_response(
                info,
                metadata={'symbol': symbol, 'source': 'Tiingo'}
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
            period: Time period - "daily" for EOD data
            start_date: Start date (YYYYMMDD format)
            end_date: End date (YYYYMMDD format)

        Returns:
            DataSourceResponse with OHLCV data
        """
        try:
            # Convert date format from YYYYMMDD to YYYY-MM-DD
            from datetime import datetime
            start = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")

            params = {
                'startDate': start,
                'endDate': end
            }

            data = self._make_request(f"tiingo/daily/{symbol.upper()}/prices", params)

            if not data:
                return DataSourceResponse.error_response(
                    f"No price data found for {symbol}"
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
                    'volume': item.get('volume'),
                    'adj_open': item.get('adjOpen'),
                    'adj_high': item.get('adjHigh'),
                    'adj_low': item.get('adjLow'),
                    'adj_close': item.get('adjClose'),
                    'adj_volume': item.get('adjVolume'),
                    'div_cash': item.get('divCash'),
                    'split_factor': item.get('splitFactor')
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
        """Get real-time quotes for symbols (latest EOD prices).

        Args:
            symbols: List of stock ticker symbols

        Returns:
            DataSourceResponse with latest price data
        """
        try:
            quotes = []

            for symbol in symbols:
                # Get latest price (most recent EOD)
                data = self._make_request(f"tiingo/daily/{symbol.upper()}/prices")

                if not data or len(data) == 0:
                    continue

                latest = data[0]  # Most recent data point

                quote = {
                    'symbol': symbol.upper(),
                    'date': latest.get('date'),
                    'close': latest.get('close'),
                    'open': latest.get('open'),
                    'high': latest.get('high'),
                    'low': latest.get('low'),
                    'volume': latest.get('volume'),
                    'adj_close': latest.get('adjClose')
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

    def get_intraday_prices(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        resample_freq: str = "5min"
    ) -> DataSourceResponse:
        """Get intraday IEX prices.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            resample_freq: Resample frequency - "1min", "5min", "15min", "30min", "1hour", "4hour"

        Returns:
            DataSourceResponse with intraday price data
        """
        try:
            params = {'resampleFreq': resample_freq}

            if start_date:
                params['startDate'] = start_date
            if end_date:
                params['endDate'] = end_date

            data = self._make_request(f"iex/{symbol.upper()}/prices", params)

            if not data:
                return DataSourceResponse.error_response(
                    f"No intraday data found for {symbol}"
                )

            return DataSourceResponse.success_response(
                data,
                metadata={
                    'symbol': symbol,
                    'resample_freq': resample_freq,
                    'count': len(data)
                }
            )

        except Exception as e:
            return self._handle_error("get_intraday_prices", e)

    def get_crypto_prices(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        resample_freq: str = "1hour"
    ) -> DataSourceResponse:
        """Get cryptocurrency prices.

        Args:
            ticker: Crypto ticker (e.g., "btcusd", "ethusd")
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            resample_freq: Resample frequency - "1min", "5min", "15min", "1hour", "1day"

        Returns:
            DataSourceResponse with crypto price data
        """
        try:
            params = {'resampleFreq': resample_freq}

            if start_date:
                params['startDate'] = start_date
            if end_date:
                params['endDate'] = end_date

            data = self._make_request(f"tiingo/crypto/prices", params)

            if not data:
                return DataSourceResponse.error_response(
                    f"No crypto data found for {ticker}"
                )

            return DataSourceResponse.success_response(
                data,
                metadata={
                    'ticker': ticker,
                    'resample_freq': resample_freq,
                    'count': len(data)
                }
            )

        except Exception as e:
            return self._handle_error("get_crypto_prices", e)

    def get_forex_prices(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        resample_freq: str = "1hour"
    ) -> DataSourceResponse:
        """Get forex exchange rates.

        Args:
            ticker: Forex pair (e.g., "eurusd", "gbpusd")
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            resample_freq: Resample frequency - "1min", "5min", "15min", "1hour", "1day"

        Returns:
            DataSourceResponse with forex rate data
        """
        try:
            params = {
                'tickers': ticker.lower(),
                'resampleFreq': resample_freq
            }

            if start_date:
                params['startDate'] = start_date
            if end_date:
                params['endDate'] = end_date

            data = self._make_request("tiingo/fx/prices", params)

            if not data:
                return DataSourceResponse.error_response(
                    f"No forex data found for {ticker}"
                )

            return DataSourceResponse.success_response(
                data,
                metadata={
                    'ticker': ticker,
                    'resample_freq': resample_freq,
                    'count': len(data)
                }
            )

        except Exception as e:
            return self._handle_error("get_forex_prices", e)

    def get_news(
        self,
        tickers: Optional[str] = None,
        tags: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> DataSourceResponse:
        """Get news articles.

        Args:
            tickers: Comma-separated ticker symbols (e.g., "aapl,msft")
            tags: Comma-separated tags to filter by
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            limit: Maximum number of articles to return

        Returns:
            DataSourceResponse with news articles
        """
        try:
            params = {'limit': limit}

            if tickers:
                params['tickers'] = tickers
            if tags:
                params['tags'] = tags
            if start_date:
                params['startDate'] = start_date
            if end_date:
                params['endDate'] = end_date

            data = self._make_request("tiingo/news", params)

            if not data:
                return DataSourceResponse.error_response(
                    "No news articles found"
                )

            news = []
            for article in data:
                news.append({
                    'id': article.get('id'),
                    'title': article.get('title'),
                    'url': article.get('url'),
                    'description': article.get('description'),
                    'published_date': article.get('publishedDate'),
                    'crawl_date': article.get('crawlDate'),
                    'source': article.get('source'),
                    'tickers': article.get('tickers'),
                    'tags': article.get('tags')
                })

            return DataSourceResponse.success_response(
                news,
                metadata={'count': len(news)}
            )

        except Exception as e:
            return self._handle_error("get_news", e)

    def search_symbols(self, query: str) -> DataSourceResponse:
        """Search for stock symbols (not directly supported by Tiingo).

        Args:
            query: Search query

        Returns:
            DataSourceResponse indicating feature not available
        """
        return DataSourceResponse.error_response(
            "Symbol search is not directly supported by Tiingo API. Use get_stock_info() to validate specific symbols."
        )
