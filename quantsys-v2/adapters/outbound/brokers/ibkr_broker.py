"""
IBKR Broker Adapter - Interactive Brokers via ib_insync

Provides live trading capabilities through Interactive Brokers TWS/IB Gateway.
Supports market data, order placement, portfolio queries, and margin information.

Note: Requires ib_insync library. The adapter operates structurally even
without ib_insync installed, returning clear error messages.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..base_broker import BaseBroker
from ..trading_types import (
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
    from ib_insync import IB, Stock, Option, MarketOrder, LimitOrder, StopOrder, util
    from ib_insync import Future, Forex, Bond, MutualFund
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False


class IBKRBroker(BaseBroker):
    """
    Interactive Brokers adapter using ib_insync.

    Features:
    - Real-time quotes and historical data
    - Order placement (Market, Limit, Stop)
    - Position and portfolio queries
    - Margin information
    - Symbol search

    Connection: Requires a running TWS (Trader Workstation) or IB Gateway.
    Default connection: host=127.0.0.1, port=7497 (TWS paper), client_id=1
    """

    def __init__(self):
        """Initialize the IBKR broker adapter."""
        self._ib = None
        self._connected = False
        self._connected_event = None  # asyncio Event (set during connect)

    # ========================================================================
    # Identity & Configuration
    # ========================================================================

    def get_id(self) -> str:
        """Return the unique broker identifier."""
        return "ibkr"

    def get_name(self) -> str:
        """Return the display name."""
        return "Interactive Brokers"

    def get_profile(self) -> BrokerProfile:
        """Return broker configuration metadata."""
        return BrokerProfile(
            id="ibkr",
            display_name="Interactive Brokers",
            region="US",
            currency="USD",
            credential_fields=[
                CredentialFieldDef(
                    field=CredentialField.USER_ID,
                    label="TWS Host",
                    placeholder="127.0.0.1",
                    secret=False,
                    required=True,
                ),
                CredentialFieldDef(
                    field=CredentialField.PASSWORD,
                    label="TWS Port",
                    placeholder="7497 (paper) or 7496 (live)",
                    secret=False,
                    required=True,
                ),
                CredentialFieldDef(
                    field=CredentialField.API_KEY,
                    label="Client ID",
                    placeholder="1",
                    secret=False,
                    required=True,
                ),
            ],
            supported_exchanges=[
                "NYSE", "NASDAQ", "ARCA", "BATS", "IEX",
                "AMEX", "LSE", "TSX", "TSE", "HKEX",
                "SGX", "ASX", "EUREX", "CME", "CBOT",
                "NYMEX", "COMEX", "ICE",
            ],
            product_types=[
                ProductTypeDef(label="股票 (Stock)", value=ProductType.DELIVERY),
                ProductTypeDef(label="日内交易 (Day)", value=ProductType.INTRADAY),
                ProductTypeDef(label="保证金 (Margin)", value=ProductType.MARGIN),
            ],
            supports_intraday=True,
            supports_margin=True,
            supports_options=True,
            has_native_paper=True,
            default_paper_balance=1000000.0,
            default_watchlist=[
                "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
                "SPY", "QQQ", "IWM",
            ],
            default_symbol="AAPL",
            default_exchange="NASDAQ",
            brokerage_info="Interactive Brokers - Low commissions, global markets",
        )

    # ========================================================================
    # Authentication
    # ========================================================================

    def authenticate(self, credentials: BrokerCredentials) -> ApiResponse[bool]:
        """
        Connect to TWS/IB Gateway.

        Uses additional_data for host, port, and client_id:
        - credentials.user_id: host (default 127.0.0.1)
        - credentials.api_key: client_id (default 1)
        - credentials.additional_data['port']: port (default 7497)
        """
        if not IB_AVAILABLE:
            return ApiResponse.fail(
                "ib_insync is not installed. Install with: pip install ib_insync"
            )

        try:
            host = credentials.additional_data.get('host', '127.0.0.1')
            if credentials.user_id:
                host = credentials.user_id
            port = int(credentials.additional_data.get('port', 7497))
            if credentials.api_secret:
                try:
                    port = int(credentials.api_secret)
                except (ValueError, TypeError):
                    pass
            client_id = 1
            if credentials.api_key:
                try:
                    client_id = int(credentials.api_key)
                except (ValueError, TypeError):
                    pass

            logger.info(
                f"Connecting to IBKR at {host}:{port} with client_id={client_id}"
            )

            self._ib = IB()
            self._ib.connect(host, port, clientId=client_id)

            self._connected = True
            logger.info(f"Connected to IBKR: {host}:{port}")
            return ApiResponse.ok(True)

        except Exception as e:
            self._connected = False
            logger.error(f"Failed to connect to IBKR: {e}", exc_info=True)
            return ApiResponse.fail(f"IBKR connection failed: {str(e)}")

    def _ensure_connected(self) -> Optional[str]:
        """Return an error string if not connected, None if connected."""
        if not IB_AVAILABLE:
            return "ib_insync is not installed. Install with: pip install ib_insync"
        if not self._connected or self._ib is None:
            return "Not connected to IBKR. Call authenticate() first."
        return None

    # ========================================================================
    # Market Data
    # ========================================================================

    def get_quotes(self, symbols: List[str]) -> ApiResponse[List[BrokerQuote]]:
        """
        Get real-time quotes using snapshot market data.

        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'MSFT', 'SPY'])

        Returns:
            ApiResponse[List[BrokerQuote]]: Quote data or error
        """
        err = self._ensure_connected()
        if err:
            return ApiResponse.fail(err)

        if not IB_AVAILABLE:
            return ApiResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        try:
            quotes = []

            for symbol in symbols:
                try:
                    # Create contract (default to US stock on SMART exchange)
                    contract = Stock(symbol, 'SMART', 'USD')

                    # Request market data snapshot
                    ticker = self._ib.reqMktData(contract, '', True, False)
                    self._ib.sleep(1)  # Wait for data to arrive

                    if ticker:
                        quote = BrokerQuote(
                            symbol=symbol,
                            last_price=float(ticker.last) if ticker.last and ticker.last > 0 else 0.0,
                            open_price=float(ticker.open) if ticker.open and ticker.open > 0 else None,
                            high_price=float(ticker.high) if ticker.high and ticker.high > 0 else None,
                            low_price=float(ticker.low) if ticker.low and ticker.low > 0 else None,
                            close_price=float(ticker.close) if ticker.close and ticker.close > 0 else None,
                            bid_price=float(ticker.bid) if ticker.bid and ticker.bid > 0 else None,
                            ask_price=float(ticker.ask) if ticker.ask and ticker.ask > 0 else None,
                            volume=float(ticker.volume) if ticker.volume and ticker.volume > 0 else None,
                            timestamp=datetime.now(),
                        )
                        quotes.append(quote)

                    self._ib.cancelMktData(contract)
                except Exception as symbol_error:
                    logger.warning(f"Failed to get quote for {symbol}: {symbol_error}")
                    continue

            if not quotes:
                return ApiResponse.fail(f"No quote data available for: {symbols}")

            return ApiResponse.ok(quotes)

        except Exception as e:
            logger.error(f"Failed to get quotes: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get quotes: {str(e)}")

    def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        frequency: str = "daily"
    ) -> ApiResponse[List[BrokerCandle]]:
        """
        Get historical candlestick data.

        Args:
            symbol: Stock symbol
            start_date: Start date "YYYY-MM-DD"
            end_date: End date "YYYY-MM-DD"
            frequency: Bar size (daily, 1 min, 5 mins, etc.)

        Returns:
            ApiResponse[List[BrokerCandle]]: Historical candles
        """
        err = self._ensure_connected()
        if err:
            return ApiResponse.fail(err)

        if not IB_AVAILABLE:
            return ApiResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        try:
            # Map frequency to IB bar size
            bar_size_map = {
                "daily": "1 day",
                "1min": "1 min",
                "5min": "5 mins",
                "15min": "15 mins",
                "30min": "30 mins",
                "1h": "1 hour",
                "weekly": "1 week",
                "monthly": "1 month",
            }
            bar_size = bar_size_map.get(frequency, "1 day")

            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')

            # Convert date strings to datetime
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                duration_days = (
                    datetime.strptime(end_date, '%Y-%m-%d') -
                    datetime.strptime(start_date, '%Y-%m-%d')
                ).days + 1
            except ValueError:
                return ApiResponse.fail(f"Invalid date format. Use 'YYYY-MM-DD'")

            # Determine duration string
            if duration_days <= 365:
                duration_str = f"{duration_days} D"
            elif duration_days <= 365 * 2:
                duration_str = f"{duration_days // 30 + 1} M"
            else:
                duration_str = f"{duration_days // 365 + 1} Y"

            # Request historical data
            bars = self._ib.reqHistoricalData(
                contract,
                endDateTime=end_dt.strftime('%Y%m%d 23:59:59'),
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1,
            )

            if not bars:
                return ApiResponse.fail(f"No historical data for {symbol}")

            # Convert to BrokerCandle list
            candles = []
            for bar in bars:
                candle = BrokerCandle(
                    symbol=symbol,
                    timestamp=bar.date,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                    turnover=float(bar.volume * (bar.open + bar.close) / 2) if bar.volume > 0 else None,
                )
                candles.append(candle)

            return ApiResponse.ok(candles)

        except Exception as e:
            logger.error(f"Failed to get history for {symbol}: {e}", exc_info=True)
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
        Place an order through Interactive Brokers.

        Maps UnifiedOrder to ib_insync order types:
        - MARKET -> MarketOrder
        - LIMIT -> LimitOrder
        - STOP_LOSS -> StopOrder

        Args:
            credentials: Broker credentials (used for auth context)
            order: Unified order structure

        Returns:
            OrderPlaceResponse: Result with order ID or error
        """
        err = self._ensure_connected()
        if err:
            return OrderPlaceResponse.fail(err)

        if not IB_AVAILABLE:
            return OrderPlaceResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        try:
            # Create contract
            contract = Stock(order.symbol, 'SMART', 'USD')

            # Build IB order based on UnifiedOrder type
            action = 'BUY' if order.side == OrderSide.BUY else 'SELL'

            if order.order_type == OrderType.MARKET:
                ib_order = MarketOrder(action, order.quantity)
            elif order.order_type == OrderType.LIMIT:
                if order.price is None:
                    return OrderPlaceResponse.fail("Limit order requires a price")
                ib_order = LimitOrder(action, order.quantity, order.price)
            elif order.order_type == OrderType.STOP_LOSS:
                if order.stop_price is None:
                    return OrderPlaceResponse.fail("Stop loss order requires a stop price")
                if order.price is not None:
                    # Stop Limit
                    ib_order = StopOrder(action, order.quantity, order.stop_price)
                else:
                    # Stop Market
                    ib_order = StopOrder(action, order.quantity, order.stop_price)
            else:
                return OrderPlaceResponse.fail(f"Unsupported order type: {order.order_type}")

            # Set time-in-force
            if order.time_in_force == 'GTC':
                ib_order.tif = 'GTC'
            elif order.time_in_force == 'IOC':
                ib_order.tif = 'IOC'
            elif order.time_in_force == 'FOK':
                ib_order.tif = 'FOK'
            else:
                ib_order.tif = 'DAY'

            # Place the trade
            trade = self._ib.placeOrder(contract, ib_order)
            self._ib.sleep(0.5)  # Brief wait for acknowledgement

            if trade and trade.order:
                order_id = str(trade.order.orderId)
                logger.info(
                    f"IBKR order placed: {order_id} {order.symbol} "
                    f"{action} {order.quantity} @ {order.price or 'MKT'}"
                )
                return OrderPlaceResponse.ok(order_id)
            else:
                return OrderPlaceResponse.fail("Order submission failed - no response")

        except Exception as e:
            logger.error(f"Failed to place IBKR order: {e}", exc_info=True)
            return OrderPlaceResponse.fail(f"IBKR order failed: {str(e)}")

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
        err = self._ensure_connected()
        if err:
            return ApiResponse.fail(err)

        if not IB_AVAILABLE:
            return ApiResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        try:
            # Find the trade
            trades = self._ib.trades()
            target_trade = None
            for trade in trades:
                if str(trade.order.orderId) == order_id:
                    target_trade = trade
                    break

            if target_trade is None:
                return ApiResponse.fail(f"Order not found: {order_id}")

            self._ib.cancelOrder(target_trade.order)
            self._ib.sleep(0.3)

            result = {
                "order_id": order_id,
                "status": "cancelled",
                "timestamp": datetime.now().isoformat(),
            }
            logger.info(f"IBKR order cancelled: {order_id}")
            return ApiResponse.ok(result)

        except Exception as e:
            logger.error(f"Failed to cancel IBKR order {order_id}: {e}", exc_info=True)
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
        err = self._ensure_connected()
        if err:
            return ApiResponse.fail(err)

        if not IB_AVAILABLE:
            return ApiResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        try:
            trades = self._ib.trades()
            orders = []
            for trade in trades:
                orders.append({
                    "order_id": str(trade.order.orderId),
                    "symbol": trade.contract.symbol if trade.contract else "",
                    "action": trade.order.action,
                    "order_type": trade.order.orderType,
                    "quantity": trade.order.totalQuantity,
                    "filled": trade.order.filledQuantity if hasattr(trade.order, 'filledQuantity') else 0,
                    "price": trade.order.lmtPrice if hasattr(trade.order, 'lmtPrice') else 0,
                    "status": trade.orderStatus.status if trade.orderStatus else "unknown",
                    "timestamp": datetime.now().isoformat(),
                })
            return ApiResponse.ok(orders)

        except Exception as e:
            logger.error(f"Failed to get IBKR orders: {e}", exc_info=True)
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
        err = self._ensure_connected()
        if err:
            return ApiResponse.fail(err)

        if not IB_AVAILABLE:
            return ApiResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        try:
            positions = self._ib.positions()
            result = []

            for pos in positions:
                result.append(BrokerPosition(
                    symbol=f"{pos.contract.symbol}.{pos.contract.currency}" if pos.contract else "unknown",
                    quantity=float(pos.position),
                    available_quantity=float(pos.position),
                    avg_price=float(pos.avgCost) if pos.avgCost > 0 else 0.0,
                    current_price=0.0,  # Would need market data for this
                    unrealized_pnl=float(getattr(pos, 'unrealizedPNL', 0)),
                    realized_pnl=float(getattr(pos, 'realizedPNL', 0)),
                    side="long" if pos.position > 0 else "short",
                    exchange=pos.contract.exchange if pos.contract and pos.contract.exchange else "SMART",
                ))

            return ApiResponse.ok(result)

        except Exception as e:
            logger.error(f"Failed to get IBKR positions: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get positions: {str(e)}")

    def get_funds(self, credentials: BrokerCredentials) -> ApiResponse[BrokerFunds]:
        """
        Get account funds summary.

        Args:
            credentials: Broker credentials

        Returns:
            ApiResponse[BrokerFunds]: Account fund details
        """
        err = self._ensure_connected()
        if err:
            return ApiResponse.fail(err)

        if not IB_AVAILABLE:
            return ApiResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        try:
            # Request account summary
            account_summary = self._ib.accountSummary()
            summary_dict = {}
            for item in account_summary:
                summary_dict[item.tag] = item.value

            funds = BrokerFunds(
                available_cash=float(summary_dict.get('AvailableFunds', 0)),
                total_assets=float(summary_dict.get('NetLiquidation', 0)),
                market_value=float(summary_dict.get('GrossPositionValue', 0)),
                frozen_cash=float(summary_dict.get('InitMarginReq', 0)),
                margin_used=float(summary_dict.get('MaintMarginReq', 0)),
                margin_available=float(summary_dict.get('AvailableFunds', 0)) * 2,  # Approximate
            )

            return ApiResponse.ok(funds)

        except Exception as e:
            logger.error(f"Failed to get IBKR funds: {e}", exc_info=True)
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
        err = self._ensure_connected()
        if err:
            return ApiResponse.fail(err)

        if not IB_AVAILABLE:
            return ApiResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        try:
            # Approximate margin calculation
            price = order.price or 100.0
            order_value = order.quantity * price

            # Reg T margin: 50% initial, 25% maintenance
            initial_margin = order_value * 0.50
            maintenance_margin = order_value * 0.25

            # Get account summary for actual numbers
            try:
                account_summary = self._ib.accountSummary()
                summary_dict = {item.tag: item.value for item in account_summary}
                current_excess_liquidity = float(summary_dict.get('ExcessLiquidity', 0))
            except Exception:
                current_excess_liquidity = 0

            margin_info = {
                "order_value": round(order_value, 2),
                "initial_margin_required": round(initial_margin, 2),
                "maintenance_margin_required": round(maintenance_margin, 2),
                "current_excess_liquidity": round(current_excess_liquidity, 2),
                "sufficient_margin": current_excess_liquidity > initial_margin,
                "symbol": order.symbol,
                "quantity": order.quantity,
                "estimated_price": price,
                "timestamp": datetime.now().isoformat(),
            }
            return ApiResponse.ok(margin_info)

        except Exception as e:
            logger.error(f"Failed to calculate margin: {e}", exc_info=True)
            return ApiResponse.fail(f"Margin calculation failed: {str(e)}")

    def search_symbols(
        self,
        query: str,
        exchange: Optional[str] = None
    ) -> ApiResponse[List[Dict[str, Any]]]:
        """
        Search for symbols matching a query.

        Uses IBKR's matching symbols request.

        Args:
            query: Search keyword (symbol or name)
            exchange: Exchange filter (optional)

        Returns:
            ApiResponse[List[Dict]]: Search results
        """
        if not IB_AVAILABLE:
            return ApiResponse.fail("ib_insync is not installed. Install with: pip install ib_insync")

        if not self._connected or self._ib is None:
            return ApiResponse.fail("Not connected to IBKR. Call authenticate() first.")

        try:
            # Use reqMatchingSymbols for search
            results = []
            try:
                # IB's matching symbols requires a pattern
                details = self._ib.reqMatchingSymbols(query)
                for detail in details[:20]:
                    contract = detail.contract
                    results.append({
                        "symbol": contract.symbol,
                        "name": detail.contract.longName if hasattr(detail.contract, 'longName') else contract.symbol,
                        "exchange": contract.exchange or "SMART",
                        "currency": contract.currency or "USD",
                        "type": contract.secType or "STK",
                        "category": "search_result",
                    })
            except Exception as search_err:
                logger.debug(f"Matching symbols failed: {search_err}, trying fallback")

            return ApiResponse.ok(results)

        except Exception as e:
            logger.error(f"Failed to search symbols: {e}", exc_info=True)
            return ApiResponse.fail(f"Symbol search failed: {str(e)}")

    # ========================================================================
    # Connection Management
    # ========================================================================

    def disconnect(self):
        """Disconnect from IBKR TWS/Gateway."""
        if self._ib and self._connected:
            try:
                self._ib.disconnect()
                self._connected = False
                logger.info("Disconnected from IBKR")
            except Exception as e:
                logger.error(f"Error disconnecting from IBKR: {e}")

    def __del__(self):
        """Cleanup on deletion."""
        self.disconnect()

    def __repr__(self) -> str:
        """String representation."""
        status = "connected" if self._connected else "disconnected"
        return f"<IBKRBroker status={status}>"
