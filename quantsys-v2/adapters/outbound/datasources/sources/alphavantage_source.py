"""Alpha Vantage data source.

Provides real-time and historical stock data, forex, crypto, and technical indicators.
Free tier: 25 requests/day, 5 requests/minute.
"""

import os
from typing import List, Optional
import requests

from ..base import MarketDataSource, DataSourceResponse


class AlphaVantageSource(MarketDataSource):
    """Alpha Vantage market data source.

    Features:
    - Real-time stock quotes
    - Historical daily/intraday data
    - Technical indicators
    - Forex and crypto data
    - Company fundamentals

    API Key: Required (free tier available)
    Rate Limits: 25 requests/day, 5 requests/minute (free tier)
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="Alpha Vantage", requires_api_key=True)
        self.api_key = api_key or os.environ.get('ALPHA_VANTAGE_API_KEY', '')
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
                    "Alpha Vantage API key not configured. Set ALPHA_VANTAGE_API_KEY environment variable."
                )

            # Test with a simple quote request
            result = self.get_realtime_quote(["AAPL"])
            if result.success:
                return DataSourceResponse.success_response(
                    {"status": "connected"},
                    metadata={"message": "Alpha Vantage API connection successful"}
                )
            return result

        except Exception as e:
            return self._handle_error("test_connection", e)

    def _make_request(self, params: dict) -> dict:
        """Make API request with error handling."""
        params['apikey'] = self.api_key

        response = self.session.get(self.BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Check for API error messages
        if 'Error Message' in data:
            raise ValueError(data['Error Message'])
        if 'Note' in data:
            raise ValueError(f"API limit reached: {data['Note']}")

        return data

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get basic stock information and overview.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            DataSourceResponse with company overview data
        """
        try:
            params = {
                'function': 'OVERVIEW',
                'symbol': symbol.upper()
            }

            data = self._make_request(params)

            if not data or 'Symbol' not in data:
                return DataSourceResponse.error_response(
                    f"No data found for symbol: {symbol}"
                )

            # Parse company overview
            info = {
                'symbol': data.get('Symbol'),
                'name': data.get('Name'),
                'description': data.get('Description'),
                'exchange': data.get('Exchange'),
                'currency': data.get('Currency'),
                'country': data.get('Country'),
                'sector': data.get('Sector'),
                'industry': data.get('Industry'),
                'market_cap': data.get('MarketCapitalization'),
                'pe_ratio': data.get('PERatio'),
                'dividend_yield': data.get('DividendYield'),
                '52_week_high': data.get('52WeekHigh'),
                '52_week_low': data.get('52WeekLow'),
            }

            return DataSourceResponse.success_response(
                info,
                metadata={'symbol': symbol, 'source': 'Alpha Vantage'}
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
            period: Time period - "1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"
            start_date: Start date (YYYYMMDD format)
            end_date: End date (YYYYMMDD format)

        Returns:
            DataSourceResponse with OHLCV data
        """
        try:
            # Map period to Alpha Vantage function
            if period in ["1min", "5min", "15min", "30min", "60min"]:
                function = "TIME_SERIES_INTRADAY"
                params = {
                    'function': function,
                    'symbol': symbol.upper(),
                    'interval': period,
                    'outputsize': 'full'
                }
            elif period == "daily":
                function = "TIME_SERIES_DAILY"
                params = {
                    'function': function,
                    'symbol': symbol.upper(),
                    'outputsize': 'full'
                }
            elif period == "weekly":
                function = "TIME_SERIES_WEEKLY"
                params = {
                    'function': function,
                    'symbol': symbol.upper()
                }
            elif period == "monthly":
                function = "TIME_SERIES_MONTHLY"
                params = {
                    'function': function,
                    'symbol': symbol.upper()
                }
            else:
                return DataSourceResponse.error_response(
                    f"Invalid period: {period}. Must be one of: 1min, 5min, 15min, 30min, 60min, daily, weekly, monthly"
                )

            data = self._make_request(params)

            # Find the time series key
            time_series_key = None
            for key in data.keys():
                if 'Time Series' in key:
                    time_series_key = key
                    break

            if not time_series_key or time_series_key not in data:
                return DataSourceResponse.error_response(
                    f"No time series data found for {symbol}"
                )

            time_series = data[time_series_key]

            # Parse OHLCV data
            klines = []
            for date_str, values in time_series.items():
                kline = {
                    'date': date_str,
                    'open': float(values.get('1. open', 0)),
                    'high': float(values.get('2. high', 0)),
                    'low': float(values.get('3. low', 0)),
                    'close': float(values.get('4. close', 0)),
                    'volume': int(values.get('5. volume', 0))
                }
                klines.append(kline)

            # Sort by date
            klines.sort(key=lambda x: x['date'])

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
                params = {
                    'function': 'GLOBAL_QUOTE',
                    'symbol': symbol.upper()
                }

                data = self._make_request(params)

                if 'Global Quote' not in data:
                    continue

                quote_data = data['Global Quote']

                if not quote_data:
                    continue

                quote = {
                    'symbol': symbol.upper(),
                    'price': float(quote_data.get('05. price', 0)),
                    'change': float(quote_data.get('09. change', 0)),
                    'change_percent': quote_data.get('10. change percent', '0%').rstrip('%'),
                    'volume': int(quote_data.get('06. volume', 0)),
                    'open': float(quote_data.get('02. open', 0)),
                    'high': float(quote_data.get('03. high', 0)),
                    'low': float(quote_data.get('04. low', 0)),
                    'previous_close': float(quote_data.get('08. previous close', 0)),
                    'trading_day': quote_data.get('07. latest trading day', '')
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

    def get_technical_indicator(
        self,
        symbol: str,
        indicator: str,
        interval: str = "daily",
        time_period: int = 20,
        series_type: str = "close"
    ) -> DataSourceResponse:
        """Get technical indicator data.

        Args:
            symbol: Stock ticker symbol
            indicator: Indicator name (e.g., "SMA", "EMA", "RSI", "MACD", "BBANDS")
            interval: Time interval - "1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"
            time_period: Number of data points for calculation
            series_type: Price type - "close", "open", "high", "low"

        Returns:
            DataSourceResponse with indicator data
        """
        try:
            params = {
                'function': indicator.upper(),
                'symbol': symbol.upper(),
                'interval': interval,
                'time_period': time_period,
                'series_type': series_type
            }

            data = self._make_request(params)

            # Find the technical analysis key
            ta_key = None
            for key in data.keys():
                if 'Technical Analysis' in key:
                    ta_key = key
                    break

            if not ta_key or ta_key not in data:
                return DataSourceResponse.error_response(
                    f"No technical indicator data found for {symbol}"
                )

            indicator_data = data[ta_key]

            # Parse indicator values
            results = []
            for date_str, values in indicator_data.items():
                result = {'date': date_str}
                result.update(values)
                results.append(result)

            # Sort by date
            results.sort(key=lambda x: x['date'])

            return DataSourceResponse.success_response(
                results,
                metadata={
                    'symbol': symbol,
                    'indicator': indicator,
                    'interval': interval,
                    'time_period': time_period
                }
            )

        except Exception as e:
            return self._handle_error("get_technical_indicator", e)

    def search_symbols(self, keywords: str) -> DataSourceResponse:
        """Search for stock symbols by keywords.

        Args:
            keywords: Search keywords (company name or symbol)

        Returns:
            DataSourceResponse with matching symbols
        """
        try:
            params = {
                'function': 'SYMBOL_SEARCH',
                'keywords': keywords
            }

            data = self._make_request(params)

            if 'bestMatches' not in data:
                return DataSourceResponse.error_response(
                    f"No matches found for: {keywords}"
                )

            matches = []
            for match in data['bestMatches']:
                matches.append({
                    'symbol': match.get('1. symbol'),
                    'name': match.get('2. name'),
                    'type': match.get('3. type'),
                    'region': match.get('4. region'),
                    'currency': match.get('8. currency'),
                    'match_score': match.get('9. matchScore')
                })

            return DataSourceResponse.success_response(
                matches,
                metadata={'keywords': keywords, 'count': len(matches)}
            )

        except Exception as e:
            return self._handle_error("search_symbols", e)
