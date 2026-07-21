"""Finnhub data source.

Provides real-time stock data, company fundamentals, earnings, news, and sentiment analysis.
Free tier: 60 API calls/minute.
"""

import os
from typing import List, Optional
import requests

from ..base import MarketDataSource, DataSourceResponse


class FinnhubSource(MarketDataSource):
    """Finnhub market data source.

    Features:
    - Real-time stock quotes
    - Company profiles and fundamentals
    - Earnings calendar
    - SEC filings
    - News and sentiment analysis
    - Forex and crypto data

    API Key: Required (free tier available)
    Rate Limits: 60 calls/minute (free tier)
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="Finnhub", requires_api_key=True)
        self.api_key = api_key or os.environ.get('FINNHUB_API_KEY', '')
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
                    "Finnhub API key not configured. Set FINNHUB_API_KEY environment variable."
                )

            # Test with a simple quote request
            result = self.get_realtime_quote(["AAPL"])
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected"},
                    metadata={"message": "Finnhub API connection successful"}
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
        """Get company profile and basic information.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            DataSourceResponse with company profile data
        """
        try:
            data = self._make_request("stock/profile2", {"symbol": symbol.upper()})

            if not data or 'name' not in data:
                return DataSourceResponse.error_response(
                    f"No data found for symbol: {symbol}"
                )

            info = {
                'symbol': data.get('ticker'),
                'name': data.get('name'),
                'country': data.get('country'),
                'currency': data.get('currency'),
                'exchange': data.get('exchange'),
                'ipo': data.get('ipo'),
                'market_cap': data.get('marketCapitalization'),
                'shares_outstanding': data.get('shareOutstanding'),
                'logo': data.get('logo'),
                'phone': data.get('phone'),
                'weburl': data.get('weburl'),
                'industry': data.get('finnhubIndustry')
            }

            return DataSourceResponse.success_response(
                info,
                metadata={'symbol': symbol, 'source': 'Finnhub'}
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
            period: Time period - "1", "5", "15", "30", "60", "D", "W", "M"
            start_date: Start date (YYYYMMDD format)
            end_date: End date (YYYYMMDD format)

        Returns:
            DataSourceResponse with OHLCV data
        """
        try:
            # Convert period format
            resolution_map = {
                "1min": "1",
                "5min": "5",
                "15min": "15",
                "30min": "30",
                "60min": "60",
                "daily": "D",
                "weekly": "W",
                "monthly": "M"
            }
            resolution = resolution_map.get(period, period)

            # Convert date format to Unix timestamp
            from datetime import datetime
            start_ts = int(datetime.strptime(start_date, "%Y%m%d").timestamp())
            end_ts = int(datetime.strptime(end_date, "%Y%m%d").timestamp())

            params = {
                'symbol': symbol.upper(),
                'resolution': resolution,
                'from': start_ts,
                'to': end_ts
            }

            data = self._make_request("stock/candle", params)

            if data.get('s') != 'ok':
                return DataSourceResponse.error_response(
                    f"No candle data found for {symbol}"
                )

            # Parse OHLCV data
            klines = []
            timestamps = data.get('t', [])
            opens = data.get('o', [])
            highs = data.get('h', [])
            lows = data.get('l', [])
            closes = data.get('c', [])
            volumes = data.get('v', [])

            for i in range(len(timestamps)):
                kline = {
                    'timestamp': timestamps[i],
                    'date': datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d %H:%M:%S'),
                    'open': opens[i],
                    'high': highs[i],
                    'low': lows[i],
                    'close': closes[i],
                    'volume': volumes[i]
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
                data = self._make_request("quote", {"symbol": symbol.upper()})

                if not data or 'c' not in data:
                    continue

                quote = {
                    'symbol': symbol.upper(),
                    'price': data.get('c'),  # Current price
                    'change': data.get('d'),  # Change
                    'change_percent': data.get('dp'),  # Percent change
                    'high': data.get('h'),  # High price of the day
                    'low': data.get('l'),  # Low price of the day
                    'open': data.get('o'),  # Open price of the day
                    'previous_close': data.get('pc'),  # Previous close price
                    'timestamp': data.get('t')  # Timestamp
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

    def get_company_news(
        self,
        symbol: str,
        from_date: str,
        to_date: str
    ) -> DataSourceResponse:
        """Get company news.

        Args:
            symbol: Stock ticker symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            DataSourceResponse with news articles
        """
        try:
            params = {
                'symbol': symbol.upper(),
                'from': from_date,
                'to': to_date
            }

            data = self._make_request("company-news", params)

            if not data:
                return DataSourceResponse.error_response(
                    f"No news found for {symbol}"
                )

            news = []
            for article in data:
                news.append({
                    'headline': article.get('headline'),
                    'summary': article.get('summary'),
                    'source': article.get('source'),
                    'url': article.get('url'),
                    'datetime': article.get('datetime'),
                    'category': article.get('category'),
                    'image': article.get('image')
                })

            return DataSourceResponse.success_response(
                news,
                metadata={'symbol': symbol, 'count': len(news)}
            )

        except Exception as e:
            return self._handle_error("get_company_news", e)

    def get_earnings_calendar(
        self,
        from_date: str,
        to_date: str,
        symbol: Optional[str] = None
    ) -> DataSourceResponse:
        """Get earnings calendar.

        Args:
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            symbol: Optional stock ticker symbol to filter

        Returns:
            DataSourceResponse with earnings calendar data
        """
        try:
            params = {
                'from': from_date,
                'to': to_date
            }

            if symbol:
                params['symbol'] = symbol.upper()

            data = self._make_request("calendar/earnings", params)

            if not data or 'earningsCalendar' not in data:
                return DataSourceResponse.error_response(
                    "No earnings calendar data found"
                )

            earnings = data['earningsCalendar']

            return DataSourceResponse.success_response(
                earnings,
                metadata={'from': from_date, 'to': to_date, 'count': len(earnings)}
            )

        except Exception as e:
            return self._handle_error("get_earnings_calendar", e)

    def get_financials(
        self,
        symbol: str,
        statement: str = "ic",
        freq: str = "annual"
    ) -> DataSourceResponse:
        """Get financial statements.

        Args:
            symbol: Stock ticker symbol
            statement: Statement type - "ic" (income), "bs" (balance sheet), "cf" (cash flow)
            freq: Frequency - "annual" or "quarterly"

        Returns:
            DataSourceResponse with financial data
        """
        try:
            params = {
                'symbol': symbol.upper(),
                'freq': freq
            }

            data = self._make_request("stock/financials-reported", params)

            if not data or 'data' not in data:
                return DataSourceResponse.error_response(
                    f"No financial data found for {symbol}"
                )

            return DataSourceResponse.success_response(
                data['data'],
                metadata={'symbol': symbol, 'statement': statement, 'freq': freq}
            )

        except Exception as e:
            return self._handle_error("get_financials", e)

    def get_forex_rates(self, base: str = "USD") -> DataSourceResponse:
        """Get forex exchange rates.

        Args:
            base: Base currency (e.g., "USD")

        Returns:
            DataSourceResponse with forex rates
        """
        try:
            params = {'base': base.upper()}

            data = self._make_request("forex/rates", params)

            if not data or 'quote' not in data:
                return DataSourceResponse.error_response(
                    f"No forex rates found for base: {base}"
                )

            return DataSourceResponse.success_response(
                data['quote'],
                metadata={'base': base}
            )

        except Exception as e:
            return self._handle_error("get_forex_rates", e)

    def search_symbols(self, query: str) -> DataSourceResponse:
        """Search for stock symbols.

        Args:
            query: Search query (company name or symbol)

        Returns:
            DataSourceResponse with matching symbols
        """
        try:
            params = {'q': query}

            data = self._make_request("search", params)

            if not data or 'result' not in data:
                return DataSourceResponse.error_response(
                    f"No matches found for: {query}"
                )

            matches = []
            for item in data['result']:
                matches.append({
                    'symbol': item.get('symbol'),
                    'description': item.get('description'),
                    'type': item.get('type'),
                    'displaySymbol': item.get('displaySymbol')
                })

            return DataSourceResponse.success_response(
                matches,
                metadata={'query': query, 'count': len(matches)}
            )

        except Exception as e:
            return self._handle_error("search_symbols", e)
