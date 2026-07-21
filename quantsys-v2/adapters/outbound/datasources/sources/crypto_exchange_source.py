"""Unified Cryptocurrency Exchange data source using CCXT.

Provides a unified interface to multiple cryptocurrency exchanges including:
- Coinbase Pro, Kraken, Bitfinex, Huobi, OKX, Bybit, Gate.io, KuCoin, and 100+ more

Uses the CCXT library for standardized exchange access.
"""

import os
from typing import List, Optional, Dict, Any
import ccxt

from ..base import MarketDataSource, DataSourceResponse


class CryptoExchangeSource(MarketDataSource):
    """Unified cryptocurrency exchange data source using CCXT.

    Supports 100+ exchanges through the CCXT library:
    - Coinbase Pro, Kraken, Bitfinex, Huobi
    - Binance, OKX, Bybit, Gate.io, KuCoin
    - And many more...

    Features:
    - Real-time ticker data
    - Historical OHLCV data
    - Order book data
    - Recent trades
    - Exchange information

    API Keys: Optional (required for private endpoints like trading)
    Rate Limits: Varies by exchange
    """

    # Popular exchanges mapping
    POPULAR_EXCHANGES = {
        'coinbase': 'Coinbase',
        'kraken': 'Kraken',
        'bitfinex': 'Bitfinex',
        'huobi': 'Huobi',
        'binance': 'Binance',
        'okx': 'OKX',
        'bybit': 'Bybit',
        'gateio': 'Gate.io',
        'kucoin': 'KuCoin',
        'bitget': 'Bitget',
        'mexc': 'MEXC',
        'cryptocom': 'Crypto.com',
        'gemini': 'Gemini',
        'bitstamp': 'Bitstamp',
    }

    def __init__(
        self,
        exchange_id: str = 'binance',
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        password: Optional[str] = None,
        sandbox: bool = False
    ):
        """Initialize crypto exchange source.

        Args:
            exchange_id: Exchange identifier (e.g., 'binance', 'kraken')
            api_key: Optional API key for authenticated requests
            secret: Optional API secret
            password: Optional API password (for some exchanges)
            sandbox: Use sandbox/testnet mode if available
        """
        super().__init__(name=f"Crypto Exchange ({exchange_id})", requires_api_key=False)

        self.exchange_id = exchange_id.lower()
        self.api_key = api_key or os.environ.get(f'{exchange_id.upper()}_API_KEY', '')
        self.secret = secret or os.environ.get(f'{exchange_id.upper()}_SECRET', '')
        self.password = password or os.environ.get(f'{exchange_id.upper()}_PASSWORD', '')
        self.sandbox = sandbox

        # Initialize CCXT exchange
        self.exchange = self._create_exchange()

    def _create_exchange(self) -> ccxt.Exchange:
        """Create and configure CCXT exchange instance."""
        if self.exchange_id not in ccxt.exchanges:
            raise ValueError(
                f"Unknown exchange: {self.exchange_id}. "
                f"Available: {', '.join(ccxt.exchanges[:10])}... ({len(ccxt.exchanges)} total)"
            )

        config = {
            'enableRateLimit': True,
            'timeout': 30000,  # 30 seconds
        }

        # Add credentials if provided
        if self.api_key:
            config['apiKey'] = self.api_key
        if self.secret:
            config['secret'] = self.secret
        if self.password:
            config['password'] = self.password

        # Create exchange instance
        exchange_class = getattr(ccxt, self.exchange_id)
        exchange = exchange_class(config)

        # Enable sandbox mode if requested
        if self.sandbox and hasattr(exchange, 'set_sandbox_mode'):
            exchange.set_sandbox_mode(True)

        return exchange

    def validate_config(self) -> bool:
        """Validate exchange configuration."""
        return self.exchange_id in ccxt.exchanges

    def test_connection(self) -> DataSourceResponse:
        """Test connection by fetching exchange status."""
        try:
            if not self.validate_config():
                return DataSourceResponse.error_response(
                    f"Invalid exchange ID: {self.exchange_id}"
                )

            # Try to load markets
            markets = self.exchange.load_markets()

            return DataSourceResponse.success_response(
                {
                    'exchange': self.exchange_id,
                    'name': self.exchange.name,
                    'markets_count': len(markets),
                    'has': {
                        'fetchTicker': self.exchange.has.get('fetchTicker', False),
                        'fetchOHLCV': self.exchange.has.get('fetchOHLCV', False),
                        'fetchOrderBook': self.exchange.has.get('fetchOrderBook', False),
                        'fetchTrades': self.exchange.has.get('fetchTrades', False),
                    }
                },
                metadata={'message': f'{self.exchange.name} connection successful'}
            )

        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """Get market information for a trading pair.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")

        Returns:
            DataSourceResponse with market information
        """
        try:
            # Load markets if not already loaded
            if not self.exchange.markets:
                self.exchange.load_markets()

            # Get market info
            if symbol not in self.exchange.markets:
                return DataSourceResponse.error_response(
                    f"Symbol {symbol} not found on {self.exchange_id}"
                )

            market = self.exchange.markets[symbol]

            info = {
                'symbol': market['symbol'],
                'id': market['id'],
                'base': market['base'],
                'quote': market['quote'],
                'active': market.get('active', True),
                'type': market.get('type', 'spot'),
                'spot': market.get('spot', False),
                'margin': market.get('margin', False),
                'future': market.get('future', False),
                'swap': market.get('swap', False),
                'option': market.get('option', False),
                'contract': market.get('contract', False),
                'precision': market.get('precision', {}),
                'limits': market.get('limits', {}),
                'info': market.get('info', {})
            }

            return DataSourceResponse.success_response(
                info,
                metadata={'exchange': self.exchange_id, 'symbol': symbol}
            )

        except Exception as e:
            return self._handle_error("get_stock_info", e)

    def get_klines(
        self,
        symbol: str,
        period: str = "1d",
        start_date: str = "20200101",
        end_date: str = "20260101"
    ) -> DataSourceResponse:
        """Get OHLCV candlestick data.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            period: Timeframe - "1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"
            start_date: Start date (YYYYMMDD format)
            end_date: End date (YYYYMMDD format)

        Returns:
            DataSourceResponse with OHLCV data
        """
        try:
            # Check if exchange supports OHLCV
            if not self.exchange.has.get('fetchOHLCV'):
                return DataSourceResponse.error_response(
                    f"{self.exchange_id} does not support OHLCV data"
                )

            # Convert date format to timestamp
            from datetime import datetime
            start_ts = int(datetime.strptime(start_date, "%Y%m%d").timestamp() * 1000)
            end_ts = int(datetime.strptime(end_date, "%Y%m%d").timestamp() * 1000)

            # Fetch OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(
                symbol,
                timeframe=period,
                since=start_ts,
                limit=1000  # Most exchanges limit to 1000 candles
            )

            # Parse OHLCV data
            klines = []
            for candle in ohlcv:
                timestamp, open_price, high, low, close, volume = candle

                # Filter by end date
                if timestamp > end_ts:
                    break

                kline = {
                    'timestamp': timestamp,
                    'date': datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume
                }
                klines.append(kline)

            return DataSourceResponse.success_response(
                klines,
                metadata={
                    'exchange': self.exchange_id,
                    'symbol': symbol,
                    'period': period,
                    'count': len(klines)
                }
            )

        except Exception as e:
            return self._handle_error("get_klines", e)

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """Get real-time ticker data for symbols.

        Args:
            symbols: List of trading pair symbols (e.g., ["BTC/USDT", "ETH/USDT"])

        Returns:
            DataSourceResponse with ticker data
        """
        try:
            # Check if exchange supports ticker
            if not self.exchange.has.get('fetchTicker'):
                return DataSourceResponse.error_response(
                    f"{self.exchange_id} does not support ticker data"
                )

            quotes = []

            for symbol in symbols:
                ticker = self.exchange.fetch_ticker(symbol)

                quote = {
                    'symbol': ticker['symbol'],
                    'timestamp': ticker.get('timestamp'),
                    'datetime': ticker.get('datetime'),
                    'high': ticker.get('high'),
                    'low': ticker.get('low'),
                    'bid': ticker.get('bid'),
                    'ask': ticker.get('ask'),
                    'last': ticker.get('last'),
                    'close': ticker.get('close'),
                    'open': ticker.get('open'),
                    'change': ticker.get('change'),
                    'percentage': ticker.get('percentage'),
                    'average': ticker.get('average'),
                    'base_volume': ticker.get('baseVolume'),
                    'quote_volume': ticker.get('quoteVolume'),
                    'vwap': ticker.get('vwap')
                }

                quotes.append(quote)

            return DataSourceResponse.success_response(
                quotes,
                metadata={
                    'exchange': self.exchange_id,
                    'symbols': symbols,
                    'count': len(quotes)
                }
            )

        except Exception as e:
            return self._handle_error("get_realtime_quote", e)

    def get_order_book(
        self,
        symbol: str,
        limit: int = 20
    ) -> DataSourceResponse:
        """Get order book (bids and asks).

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            limit: Number of orders to fetch (default 20)

        Returns:
            DataSourceResponse with order book data
        """
        try:
            if not self.exchange.has.get('fetchOrderBook'):
                return DataSourceResponse.error_response(
                    f"{self.exchange_id} does not support order book data"
                )

            orderbook = self.exchange.fetch_order_book(symbol, limit)

            data = {
                'symbol': symbol,
                'timestamp': orderbook.get('timestamp'),
                'datetime': orderbook.get('datetime'),
                'bids': orderbook.get('bids', []),
                'asks': orderbook.get('asks', []),
                'bid': orderbook['bids'][0][0] if orderbook.get('bids') else None,
                'ask': orderbook['asks'][0][0] if orderbook.get('asks') else None,
                'spread': None
            }

            # Calculate spread
            if data['bid'] and data['ask']:
                data['spread'] = data['ask'] - data['bid']

            return DataSourceResponse.success_response(
                data,
                metadata={'exchange': self.exchange_id, 'symbol': symbol}
            )

        except Exception as e:
            return self._handle_error("get_order_book", e)

    def get_recent_trades(
        self,
        symbol: str,
        limit: int = 100
    ) -> DataSourceResponse:
        """Get recent trades.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            limit: Number of trades to fetch (default 100)

        Returns:
            DataSourceResponse with recent trades
        """
        try:
            if not self.exchange.has.get('fetchTrades'):
                return DataSourceResponse.error_response(
                    f"{self.exchange_id} does not support trades data"
                )

            trades = self.exchange.fetch_trades(symbol, limit=limit)

            trades_data = []
            for trade in trades:
                trades_data.append({
                    'id': trade.get('id'),
                    'timestamp': trade.get('timestamp'),
                    'datetime': trade.get('datetime'),
                    'symbol': trade.get('symbol'),
                    'type': trade.get('type'),
                    'side': trade.get('side'),
                    'price': trade.get('price'),
                    'amount': trade.get('amount'),
                    'cost': trade.get('cost')
                })

            return DataSourceResponse.success_response(
                trades_data,
                metadata={
                    'exchange': self.exchange_id,
                    'symbol': symbol,
                    'count': len(trades_data)
                }
            )

        except Exception as e:
            return self._handle_error("get_recent_trades", e)

    def list_markets(self) -> DataSourceResponse:
        """List all available markets on the exchange.

        Returns:
            DataSourceResponse with list of markets
        """
        try:
            markets = self.exchange.load_markets()

            markets_list = []
            for symbol, market in markets.items():
                markets_list.append({
                    'symbol': symbol,
                    'base': market['base'],
                    'quote': market['quote'],
                    'active': market.get('active', True),
                    'type': market.get('type', 'spot')
                })

            return DataSourceResponse.success_response(
                markets_list,
                metadata={
                    'exchange': self.exchange_id,
                    'count': len(markets_list)
                }
            )

        except Exception as e:
            return self._handle_error("list_markets", e)

    def search_symbols(self, query: str) -> DataSourceResponse:
        """Search for trading pairs.

        Args:
            query: Search query (e.g., "BTC", "ETH")

        Returns:
            DataSourceResponse with matching symbols
        """
        try:
            if not self.exchange.markets:
                self.exchange.load_markets()

            query_upper = query.upper()
            matches = []

            for symbol, market in self.exchange.markets.items():
                if (query_upper in symbol.upper() or
                    query_upper in market['base'].upper() or
                    query_upper in market['quote'].upper()):
                    matches.append({
                        'symbol': symbol,
                        'base': market['base'],
                        'quote': market['quote'],
                        'active': market.get('active', True),
                        'type': market.get('type', 'spot')
                    })

            return DataSourceResponse.success_response(
                matches,
                metadata={
                    'exchange': self.exchange_id,
                    'query': query,
                    'count': len(matches)
                }
            )

        except Exception as e:
            return self._handle_error("search_symbols", e)

    @staticmethod
    def list_supported_exchanges() -> List[str]:
        """Get list of all supported exchanges.

        Returns:
            List of exchange IDs
        """
        return ccxt.exchanges

    @staticmethod
    def get_popular_exchanges() -> Dict[str, str]:
        """Get dictionary of popular exchanges.

        Returns:
            Dict mapping exchange ID to display name
        """
        return CryptoExchangeSource.POPULAR_EXCHANGES
