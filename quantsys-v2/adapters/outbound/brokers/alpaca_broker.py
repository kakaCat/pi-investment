"""
Alpaca Broker Adapter - Alpaca Markets via alpaca-py

Provides live and paper trading capabilities through Alpaca Markets API.
Supports US equities with market data, order placement, and portfolio queries.

Note: Requires alpaca-py library. The adapter operates structurally even
without alpaca-py installed, returning clear error messages.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from domain.brokers.base_broker import BaseBroker
from domain.brokers.trading_types import (
    BrokerProfile,
    UnifiedOrder,
    OrderPlaceResponse,
    ApiResponse,
    BrokerQuote,
    BrokerCandle,
    BrokerPosition,
    BrokerHolding,
    BrokerFunds,
    BrokerCredentials,
    CredentialFieldDef,
    CredentialField,
    ProductTypeDef,
    ProductType,
    OrderSide,
    OrderType,
)

logger = logging.getLogger(__name__)

# Graceful import handling
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest
    from alpaca.trading.requests import TrailingStopOrderRequest
    from alpaca.trading.enums import OrderSide as AlpacaSide
    from alpaca.trading.enums import OrderType as AlpacaType
    from alpaca.trading.enums import TimeInForce
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    import alpaca
    ALPACA_AVAILABLE = True

    # Map our timeframe to Alpaca TimeFrame
    _TIMEFRAME_MAP = {
        "minute": TimeFrame.Minute,
        "hour": TimeFrame.Hour,
        "day": TimeFrame.Day,
        "week": TimeFrame.Week,
        "month": TimeFrame.Month,
    }

except ImportError:
    ALPACA_AVAILABLE = False


class AlpacaBroker(BaseBroker):
    """
    Alpaca Markets adapter using alpaca-py.

    Features:
    - Real-time quotes and historical data (US equities)
    - Order placement (Market, Limit, Stop, Trailing Stop)
    - Position and portfolio queries
    - Paper and live trading modes
    - Margin and short selling support

    Credentials:
    - api_key: Alpaca API Key
    - api_secret: Alpaca API Secret
    - additional_data['paper']: True for paper trading, False for live (default: True)
    """

    def __init__(self):
        """Initialize the Alpaca broker adapter."""
        self._trading_client = None
        self._data_client = None
        self._paper_mode = True
        self._authenticated = False

    # ========================================================================
    # Identity & Configuration
    # ========================================================================

    def get_id(self) -> str:
        """Return the unique broker identifier."""
        return "alpaca"

    def get_name(self) -> str:
        """Return the display name."""
        return "Alpaca Markets"

    def get_profile(self) -> BrokerProfile:
        """Return broker configuration metadata."""
        return BrokerProfile(
            id="alpaca",
            display_name="Alpaca Markets",
            region="US",
            currency="USD",
            credential_fields=[
                CredentialFieldDef(
                    field=CredentialField.API_KEY,
                    label="API Key",
                    placeholder="PK...",
                    secret=True,
                    required=True,
                ),
                CredentialFieldDef(
                    field=CredentialField.API_SECRET,
                    label="Secret Key",
                    placeholder="SK...",
                    secret=True,
                    required=True,
                ),
            ],
            supported_exchanges=[
                "NYSE", "NASDAQ", "ARCA", "BATS", "IEX", "AMEX",
            ],
            product_types=[
                ProductTypeDef(label="股票 (Equity)", value=ProductType.DELIVERY),
                ProductTypeDef(label="日内交易 (Day)", value=ProductType.INTRADAY),
                ProductTypeDef(label="保证金 (Margin)", value=ProductType.MARGIN),
                ProductTypeDef(label="括号订单 (Bracket)", value=ProductType.BRACKET_ORDER),
            ],
            supports_intraday=True,
            supports_margin=True,
            supports_options=False,  # Alpaca doesn't support options yet
            has_native_paper=True,
            default_paper_balance=100000.0,
            default_watchlist=[
                "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
                "SPY", "QQQ", "IWM", "NVDA", "META",
            ],
            default_symbol="AAPL",
            default_exchange="NASDAQ",
            brokerage_info=(
                "Alpaca Markets - Commission-free trading, "
                "paper trading available, crypto support"
            ),
        )

    # ========================================================================
    # Authentication
    # ========================================================================

    def authenticate(self, credentials: BrokerCredentials) -> ApiResponse[bool]:
        """
        Authenticate with Alpaca using API key and secret.

        Args:
            credentials: Must contain api_key and api_secret.
                         additional_data['paper'] controls paper vs live mode.

        Returns:
            ApiResponse[bool]: Authentication result
        """
        if not ALPACA_AVAILABLE:
            return ApiResponse.fail(
                "alpaca-py is not installed. Install with: pip install alpaca-py"
            )

        if not credentials.api_key or not credentials.api_secret:
            return ApiResponse.fail("Alpaca requires API Key and Secret Key")

        try:
            self._paper_mode = credentials.additional_data.get('paper', True)

            base_url = "https://paper-api.alpaca.markets" if self._paper_mode \
                else "https://api.alpaca.markets"

            data_url = "https://data.alpaca.markets"

            self._trading_client = TradingClient(
                api_key=credentials.api_key,
                secret_key=credentials.api_secret,
                paper=self._paper_mode,
                url_override=base_url,
            )

            self._data_client = StockHistoricalDataClient(
                api_key=credentials.api_key,
                secret_key=credentials.api_secret,
                url_override=data_url,
            )

            # Verify credentials by fetching account
            account = self._trading_client.get_account()
            if account:
                self._authenticated = True
                mode = "paper" if self._paper_mode else "live"
                logger.info(
                    f"Alpaca authentication successful ({mode} mode). "
                    f"Account: {account.id}, Status: {account.status}"
                )
                return ApiResponse.ok(True)
            else:
                return ApiResponse.fail("Alpaca authentication failed: no account returned")

        except Exception as e:
            self._authenticated = False
            self._trading_client = None
            self._data_client = None
            logger.error(f"Alpaca authentication failed: {e}", exc_info=True)
            return ApiResponse.fail(f"Alpaca authentication failed: {str(e)}")

    def _ensure_authenticated(self) -> Optional[str]:
        """Return an error string if not authenticated, None if authenticated."""
        if not ALPACA_AVAILABLE:
            return "alpaca-py is not installed. Install with: pip install alpaca-py"
        if not self._authenticated or self._trading_client is None:
            return "Not authenticated with Alpaca. Call authenticate() first."
        return None

    # ========================================================================
    # Market Data
    # ========================================================================

    def get_quotes(self, symbols: List[str]) -> ApiResponse[List[BrokerQuote]]:
        """
        Get real-time quotes for symbols.

        Args:
            symbols: List of stock symbols

        Returns:
            ApiResponse[List[BrokerQuote]]: Quote data
        """
        err = self._ensure_authenticated()
        if err:
            return ApiResponse.fail(err)

        if not ALPACA_AVAILABLE:
            return ApiResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        try:
            # Use the latest quote endpoint
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            response = self._data_client.get_stock_latest_quote(request)

            quotes = []

            for symbol in symbols:
                quote_data = response.get(symbol)
                if quote_data is None:
                    logger.warning(f"No quote data for {symbol}")
                    continue

                quote = BrokerQuote(
                    symbol=symbol,
                    last_price=float(quote_data.ask_price + quote_data.bid_price) / 2
                    if quote_data.ask_price and quote_data.bid_price else 0.0,
                    bid_price=float(quote_data.bid_price) if quote_data.bid_price else None,
                    ask_price=float(quote_data.ask_price) if quote_data.ask_price else None,
                    timestamp=datetime.fromisoformat(quote_data.timestamp.isoformat())
                    if quote_data.timestamp else datetime.now(),
                )
                quotes.append(quote)

            if not quotes:
                return ApiResponse.fail(f"No quote data available for: {symbols}")

            return ApiResponse.ok(quotes)

        except Exception as e:
            logger.error(f"Failed to get Alpaca quotes: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get quotes: {str(e)}")

    def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        frequency: str = "daily"
    ) -> ApiResponse[List[BrokerCandle]]:
        """
        Get historical candlestick data from Alpaca.

        Args:
            symbol: Stock symbol
            start_date: Start date "YYYY-MM-DD"
            end_date: End date "YYYY-MM-DD"
            frequency: Bar frequency (daily, 1min, 5min, 15min, 1h)

        Returns:
            ApiResponse[List[BrokerCandle]]: Historical candles
        """
        err = self._ensure_authenticated()
        if err:
            return ApiResponse.fail(err)

        if not ALPACA_AVAILABLE:
            return ApiResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        try:
            # Map frequency to Alpaca TimeFrame
            if frequency in ("daily", "day"):
                tf = TimeFrame.Day
                tf_mult = 1
                adjustment = ""
            elif frequency == "weekly" or frequency == "week":
                tf = TimeFrame.Week
                tf_mult = 1
                adjustment = ""
            elif frequency == "monthly" or frequency == "month":
                tf = TimeFrame.Month
                tf_mult = 1
                adjustment = ""
            elif frequency == "1min" or frequency == "1m":
                tf = TimeFrame.Minute
                tf_mult = 1
                adjustment = ""
            elif frequency == "5min" or frequency == "5m":
                tf = TimeFrame.Minute
                tf_mult = 5
                adjustment = ""
            elif frequency == "15min" or frequency == "15m":
                tf = TimeFrame.Minute
                tf_mult = 15
                adjustment = ""
            elif frequency == "30min" or frequency == "30m":
                tf = TimeFrame.Minute
                tf_mult = 30
                adjustment = ""
            elif frequency == "1h" or frequency == "hour":
                tf = TimeFrame.Hour
                tf_mult = 1
                adjustment = ""
            else:
                tf = TimeFrame.Day
                tf_mult = 1
                adjustment = ""

            # Build timeframe
            if adjustment:
                timeframe = TimeFrame(tf_mult, tf, adjustment)
            else:
                timeframe = TimeFrame(tf_mult, tf)

            # Parse dates
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                return ApiResponse.fail(f"Invalid date format. Use 'YYYY-MM-DD'")

            # Create request
            request = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=timeframe,
                start=start_dt,
                end=end_dt,
                limit=10000,
            )

            # Fetch bars
            bars_response = self._data_client.get_stock_bars(request)
            bars = bars_response.data.get(symbol, [])

            if not bars:
                return ApiResponse.fail(f"No historical data for {symbol}")

            # Convert to BrokerCandle list
            candles = []
            for bar in bars:
                candle = BrokerCandle(
                    symbol=symbol,
                    timestamp=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                    turnover=float(bar.volume * bar.vwap) if bar.vwap and bar.volume > 0 else None,
                )
                candles.append(candle)

            return ApiResponse.ok(candles)

        except Exception as e:
            logger.error(f"Failed to get Alpaca history for {symbol}: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get history: {str(e)}")

    # ========================================================================
    # Trading
    # ========================================================================

    def place_order(
        self,
        credentials: BrokerCredentials,
        order: UnifiedOrder
    ) -> OrderPlaceResponse:
        """
        Place an order through Alpaca.

        Maps UnifiedOrder to Alpaca order request types:
        - MARKET -> MarketOrderRequest
        - LIMIT -> LimitOrderRequest
        - STOP_LOSS -> StopOrderRequest

        Args:
            credentials: Broker credentials
            order: Unified order structure

        Returns:
            OrderPlaceResponse: Result with order ID or error
        """
        err = self._ensure_authenticated()
        if err:
            return OrderPlaceResponse.fail(err)

        if not ALPACA_AVAILABLE:
            return OrderPlaceResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        try:
            # Map side
            if order.side == OrderSide.BUY:
                side = AlpacaSide.BUY
            else:
                side = AlpacaSide.SELL

            # Map time in force
            tif = TimeInForce.DAY
            if order.time_in_force == 'GTC':
                tif = TimeInForce.GTC
            elif order.time_in_force == 'IOC':
                tif = TimeInForce.IOC
            elif order.time_in_force == 'FOK':
                tif = TimeInForce.FOK
            elif order.time_in_force == 'CLS':
                tif = TimeInForce.CLS

            # Build the appropriate order request
            if order.order_type == OrderType.MARKET:
                request_params = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=side,
                    time_in_force=tif,
                )
            elif order.order_type == OrderType.LIMIT:
                if order.price is None:
                    return OrderPlaceResponse.fail("Limit order requires a price")
                request_params = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=side,
                    limit_price=order.price,
                    time_in_force=tif,
                )
            elif order.order_type == OrderType.STOP_LOSS:
                if order.stop_price is None:
                    return OrderPlaceResponse.fail("Stop loss order requires a stop price")
                if order.price is not None:
                    # Stop limit
                    request_params = StopOrderRequest(
                        symbol=order.symbol,
                        qty=order.quantity,
                        side=side,
                        stop_price=order.stop_price,
                        limit_price=order.price,
                        time_in_force=tif,
                    )
                else:
                    # Stop market
                    request_params = StopOrderRequest(
                        symbol=order.symbol,
                        qty=order.quantity,
                        side=side,
                        stop_price=order.stop_price,
                        time_in_force=tif,
                    )
            else:
                return OrderPlaceResponse.fail(f"Unsupported order type: {order.order_type}")

            # Submit the order
            alpaca_order = self._trading_client.submit_order(order_data=request_params)

            if alpaca_order:
                logger.info(
                    f"Alpaca order placed: {alpaca_order.id} {order.symbol} "
                    f"{side.value} {order.quantity} @ {order.price or 'MKT'}"
                )
                return OrderPlaceResponse.ok(str(alpaca_order.id))
            else:
                return OrderPlaceResponse.fail("Alpaca order submission failed - no response")

        except Exception as e:
            logger.error(f"Failed to place Alpaca order: {e}", exc_info=True)
            return OrderPlaceResponse.fail(f"Alpaca order failed: {str(e)}")

    def cancel_order(
        self,
        credentials: BrokerCredentials,
        order_id: str
    ) -> ApiResponse[Dict[str, Any]]:
        """
        Cancel an existing order.

        Args:
            credentials: Broker credentials
            order_id: Order ID to cancel

        Returns:
            ApiResponse[Dict]: Cancellation result
        """
        err = self._ensure_authenticated()
        if err:
            return ApiResponse.fail(err)

        if not ALPACA_AVAILABLE:
            return ApiResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        try:
            self._trading_client.cancel_order_by_id(order_id)
            result = {
                "order_id": order_id,
                "status": "cancelled",
                "timestamp": datetime.now().isoformat(),
            }
            logger.info(f"Alpaca order cancelled: {order_id}")
            return ApiResponse.ok(result)

        except Exception as e:
            logger.error(f"Failed to cancel Alpaca order {order_id}: {e}", exc_info=True)
            return ApiResponse.fail(f"Cancel failed: {str(e)}")

    def get_orders(
        self,
        credentials: BrokerCredentials
    ) -> ApiResponse[List[Dict[str, Any]]]:
        """
        Get all open and recent orders.

        Args:
            credentials: Broker credentials

        Returns:
            ApiResponse[List[Dict]]: Orders list
        """
        err = self._ensure_authenticated()
        if err:
            return ApiResponse.fail(err)

        if not ALPACA_AVAILABLE:
            return ApiResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        try:
            orders = self._trading_client.get_orders(
                status="all",
                limit=100,
            )

            result = []
            for o in orders:
                result.append({
                    "order_id": str(o.id),
                    "symbol": o.symbol,
                    "action": o.side.value,
                    "order_type": o.type.value,
                    "quantity": float(o.qty) if o.qty else 0,
                    "filled": float(o.filled_qty) if o.filled_qty else 0,
                    "price": float(o.limit_price) if o.limit_price else 0,
                    "status": o.status.value,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                })

            return ApiResponse.ok(result)

        except Exception as e:
            logger.error(f"Failed to get Alpaca orders: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get orders: {str(e)}")

    # ========================================================================
    # Portfolio
    # ========================================================================

    def get_positions(
        self,
        credentials: BrokerCredentials
    ) -> ApiResponse[List[BrokerPosition]]:
        """
        Get current positions.

        Args:
            credentials: Broker credentials

        Returns:
            ApiResponse[List[BrokerPosition]]: Current positions
        """
        err = self._ensure_authenticated()
        if err:
            return ApiResponse.fail(err)

        if not ALPACA_AVAILABLE:
            return ApiResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        try:
            positions = self._trading_client.get_all_positions()
            result = []

            for pos in positions:
                result.append(BrokerPosition(
                    symbol=pos.symbol,
                    quantity=float(pos.qty),
                    available_quantity=float(pos.qty_available) if pos.qty_available else float(pos.qty),
                    avg_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price) if pos.current_price else 0.0,
                    unrealized_pnl=float(pos.unrealized_pl) if pos.unrealized_pl else 0.0,
                    realized_pnl=float(pos.realized_pl) if hasattr(pos, 'realized_pl') and pos.realized_pl else 0.0,
                    side="long" if float(pos.qty) > 0 else "short",
                    exchange=pos.exchange if hasattr(pos, 'exchange') else "",
                    product_type="margin" if pos.asset_marginable else "cash",
                ))

            return ApiResponse.ok(result)

        except Exception as e:
            logger.error(f"Failed to get Alpaca positions: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get positions: {str(e)}")

    def get_funds(self, credentials: BrokerCredentials) -> ApiResponse[BrokerFunds]:
        """
        Get account funds summary from Alpaca.

        Args:
            credentials: Broker credentials

        Returns:
            ApiResponse[BrokerFunds]: Account fund details
        """
        err = self._ensure_authenticated()
        if err:
            return ApiResponse.fail(err)

        if not ALPACA_AVAILABLE:
            return ApiResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        try:
            account = self._trading_client.get_account()

            funds = BrokerFunds(
                available_cash=float(account.cash) if account.cash else 0.0,
                total_assets=float(account.portfolio_value) if account.portfolio_value else 0.0,
                market_value=float(account.long_market_value) + float(account.short_market_value)
                if account.long_market_value else 0.0,
                frozen_cash=float(account.accrued_fees) if account.accrued_fees else 0.0,
                margin_used=float(account.initial_margin) if account.initial_margin else 0.0,
                margin_available=float(account.buying_power) * 0.5 if account.buying_power else 0.0,
            )

            return ApiResponse.ok(funds)

        except Exception as e:
            logger.error(f"Failed to get Alpaca funds: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get funds: {str(e)}")

    # ========================================================================
    # Advanced Features
    # ========================================================================

    def get_margin_info(
        self,
        credentials: BrokerCredentials,
        order: UnifiedOrder
    ) -> ApiResponse[Dict[str, Any]]:
        """
        Calculate margin requirement for a proposed order.

        Args:
            credentials: Broker credentials
            order: Proposed order for margin calculation

        Returns:
            ApiResponse[Dict]: Margin information
        """
        err = self._ensure_authenticated()
        if err:
            return ApiResponse.fail(err)

        if not ALPACA_AVAILABLE:
            return ApiResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        try:
            account = self._trading_client.get_account()

            price = order.price or 100.0
            order_value = order.quantity * price

            # Reg T: 50% initial margin for long, 150% for short
            if order.side == OrderSide.BUY:
                initial_margin = order_value * 0.50
            else:
                initial_margin = order_value * 1.50  # Short selling

            maintenance_margin = order_value * 0.25

            buying_power = float(account.buying_power) if account.buying_power else 0
            sufficient = buying_power > initial_margin

            margin_info = {
                "order_value": round(order_value, 2),
                "initial_margin_required": round(initial_margin, 2),
                "maintenance_margin_required": round(maintenance_margin, 2),
                "current_buying_power": round(buying_power, 2),
                "sufficient_margin": sufficient,
                "order_side": order.side.value,
                "symbol": order.symbol,
                "quantity": order.quantity,
                "estimated_price": price,
                "timestamp": datetime.now().isoformat(),
            }
            return ApiResponse.ok(margin_info)

        except Exception as e:
            logger.error(f"Failed to calculate Alpaca margin: {e}", exc_info=True)
            return ApiResponse.fail(f"Margin calculation failed: {str(e)}")

    def search_symbols(
        self,
        query: str,
        exchange: Optional[str] = None
    ) -> ApiResponse[List[Dict[str, Any]]]:
        """
        Search for tradable symbols on Alpaca.

        Uses Alpaca asset search if available, or returns a structured
        response indicating the query was received.

        Args:
            query: Search keyword
            exchange: Exchange filter (optional)

        Returns:
            ApiResponse[List[Dict]]: Search results
        """
        if not ALPACA_AVAILABLE:
            return ApiResponse.fail("alpaca-py is not installed. Install with: pip install alpaca-py")

        if not self._authenticated:
            return ApiResponse.fail("Not authenticated with Alpaca. Call authenticate() first.")

        try:
            # Use get_asset or search
            query_upper = query.upper().strip()
            results = []

            try:
                # Try to get exact symbol match first
                asset = self._trading_client.get_asset(query_upper)
                if asset and asset.tradable:
                    results.append({
                        "symbol": asset.symbol,
                        "name": asset.name or asset.symbol,
                        "exchange": asset.exchange or "NASDAQ",
                        "currency": "USD",
                        "type": asset.asset_class or "us_equity",
                        "tradable": asset.tradable,
                        "category": "asset",
                    })
            except Exception:
                pass

            # For broader search, try a substring match
            if not results:
                results.append({
                    "symbol": query_upper,
                    "name": query_upper,
                    "exchange": exchange or "NASDAQ",
                    "currency": "USD",
                    "type": "us_equity",
                    "tradable": True,
                    "category": "search",
                    "note": "Verify exact symbol on Alpaca dashboard",
                })

            return ApiResponse.ok(results)

        except Exception as e:
            logger.error(f"Failed to search Alpaca symbols: {e}", exc_info=True)
            return ApiResponse.fail(f"Symbol search failed: {str(e)}")

    # ========================================================================
    # Connection Management
    # ========================================================================

    def disconnect(self):
        """Reset connection state (Alpaca is REST-based, no persistent connection)."""
        self._trading_client = None
        self._data_client = None
        self._authenticated = False
        logger.info("Alpaca connection state cleared")

    def __repr__(self) -> str:
        """String representation."""
        mode = "paper" if self._paper_mode else "live"
        status = "authenticated" if self._authenticated else "not authenticated"
        return f"<AlpacaBroker mode={mode} status={status}>"
