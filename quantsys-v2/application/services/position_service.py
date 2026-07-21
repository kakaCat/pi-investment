"""
Position Service - Live Position Management

Functions for fetching, analyzing, and managing live brokerage positions.
All functions follow the module-level pattern with 'ds: DataService' as the
first parameter.
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from application.services.data_service import DataService

logger = structlog.get_logger(__name__)


def _get_broker_registry():
    """Lazy-load broker registry."""
    from domain.brokers.broker_registry import BrokerRegistry
    return BrokerRegistry.instance()


def _get_broker(broker_id: str):
    """Get a broker instance by ID. Returns None with error message if not found."""
    registry = _get_broker_registry()
    broker = registry.get(broker_id)
    if broker is None:
        return None, f"Broker not found: {broker_id}"
    return broker, None


# ========================================================================
# Position Queries
# ========================================================================


def get_live_positions(ds: DataService, broker_id: str) -> Dict[str, Any]:
    """
    Fetch live positions from the broker and structure them by symbol.

    Args:
        ds: DataService instance
        broker_id: Broker ID to fetch from

    Returns:
        Dict containing:
        - positions: Dict keyed by symbol with position details
        - total_market_value: Sum of all position values
        - total_unrealized_pnl: Sum of unrealized P&L
        - position_count: Number of positions
        - broker_id: Source broker
        - timestamp: Query time
    """
    broker, err = _get_broker(broker_id)
    if broker is None:
        return {
            'success': False,
            'error': err,
            'positions': {},
            'position_count': 0,
            'broker_id': broker_id,
        }

    try:
        from domain.brokers.trading_types import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id)

        response = broker.get_positions(creds)

        if not response.success:
            return {
                'success': False,
                'error': response.error or "Failed to fetch positions",
                'positions': {},
                'position_count': 0,
                'broker_id': broker_id,
                'timestamp': datetime.now().isoformat(),
            }

        positions = response.data or []
        positions_by_symbol = {}
        total_market_value = 0.0
        total_unrealized_pnl = 0.0

        for pos in positions:
            symbol = pos.symbol
            market_value = pos.quantity * pos.current_price

            positions_by_symbol[symbol] = {
                'symbol': symbol,
                'quantity': pos.quantity,
                'available_quantity': pos.available_quantity,
                'avg_price': pos.avg_price,
                'current_price': pos.current_price,
                'market_value': round(market_value, 2),
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl,
                'side': pos.side,
                'exchange': pos.exchange,
                'pnl_pct': round(
                    (pos.current_price - pos.avg_price) / pos.avg_price * 100, 2
                ) if pos.avg_price > 0 else 0.0,
            }

            total_market_value += market_value
            total_unrealized_pnl += pos.unrealized_pnl

        result = {
            'success': True,
            'positions': positions_by_symbol,
            'total_market_value': round(total_market_value, 2),
            'total_unrealized_pnl': round(total_unrealized_pnl, 2),
            'position_count': len(positions_by_symbol),
            'broker_id': broker_id,
            'timestamp': datetime.now().isoformat(),
        }

        logger.info(
            f"Fetched {result['position_count']} positions from {broker_id} "
            f"(market value: {result['total_market_value']})"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to get live positions: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'positions': {},
            'position_count': 0,
            'broker_id': broker_id,
            'timestamp': datetime.now().isoformat(),
        }


def calculate_live_pnl(ds: DataService, broker_id: str) -> Dict[str, Any]:
    """
    Calculate total and per-position unrealized P&L from live positions.

    Args:
        ds: DataService instance
        broker_id: Broker ID

    Returns:
        Dict with:
        - total_unrealized_pnl: Total P&L across all positions
        - total_realized_pnl: Total realized P&L
        - total_pnl: Combined P&L
        - positions: Per-position P&L breakdown
        - broker_id: Source broker
    """
    positions_result = get_live_positions(ds, broker_id)

    if not positions_result.get('success'):
        return {
            'success': False,
            'error': positions_result.get('error', 'Failed to get positions'),
            'total_unrealized_pnl': 0.0,
            'total_realized_pnl': 0.0,
            'total_pnl': 0.0,
            'positions': [],
            'broker_id': broker_id,
        }

    positions = positions_result.get('positions', {})
    total_unrealized_pnl = 0.0
    total_realized_pnl = 0.0
    pnl_breakdown = []

    for symbol, pos in positions.items():
        unrealized = pos.get('unrealized_pnl', 0.0)
        realized = pos.get('realized_pnl', 0.0)

        total_unrealized_pnl += unrealized
        total_realized_pnl += realized

        pnl_breakdown.append({
            'symbol': symbol,
            'quantity': pos.get('quantity', 0),
            'avg_cost': pos.get('avg_price', 0),
            'current_price': pos.get('current_price', 0),
            'market_value': pos.get('market_value', 0),
            'unrealized_pnl': unrealized,
            'realized_pnl': realized,
            'pnl_pct': pos.get('pnl_pct', 0.0),
            'total_pnl': unrealized + realized,
        })

    # Sort by total P&L descending
    pnl_breakdown.sort(key=lambda x: x['total_pnl'], reverse=True)

    total_pnl = total_unrealized_pnl + total_realized_pnl

    result = {
        'success': True,
        'total_unrealized_pnl': round(total_unrealized_pnl, 2),
        'total_realized_pnl': round(total_realized_pnl, 2),
        'total_pnl': round(total_pnl, 2),
        'positions': pnl_breakdown,
        'position_count': len(pnl_breakdown),
        'broker_id': broker_id,
        'timestamp': datetime.now().isoformat(),
    }

    logger.info(
        f"P&L calculation for {broker_id}: "
        f"unrealized={total_unrealized_pnl:.2f} realized={total_realized_pnl:.2f}"
    )

    return result


def get_position_risk(
    ds: DataService,
    broker_id: str,
    symbol: str,
) -> Dict[str, Any]:
    """
    Calculate risk contribution of a single position.

    Includes position Greeks contribution (approximation), VaR contribution,
    and portfolio concentration percentage.

    Args:
        ds: DataService instance
        broker_id: Broker ID
        symbol: Stock symbol to analyze

    Returns:
        Dict containing position risk metrics
    """
    positions_result = get_live_positions(ds, broker_id)

    if not positions_result.get('success'):
        return {
            'success': False,
            'error': positions_result.get('error', 'Failed to get positions'),
            'symbol': symbol,
            'broker_id': broker_id,
        }

    positions = positions_result.get('positions', {})
    pos = positions.get(symbol)

    if pos is None:
        return {
            'success': False,
            'error': f"Position not found for {symbol}",
            'symbol': symbol,
            'broker_id': broker_id,
        }

    total_market_value = positions_result.get('total_market_value', 0)
    position_value = pos.get('market_value', 0)

    # Concentration percentage
    concentration_pct = (
        (position_value / total_market_value * 100) if total_market_value > 0 else 0.0
    )

    # Approximate Greeks (simplified for equities)
    # Delta: 1.0 for long, -1.0 for short (per share delta)
    delta = 1.0 if pos.get('side', 'long') == 'long' else -1.0

    # Gamma: 0 for linear instruments (equities)
    gamma = 0.0

    # Theta: estimated daily decay based on volatility assumption
    theta = 0.0  # Equities don't have time decay like options

    # Vega: 0 for equities
    vega = 0.0

    # Approximate VaR contribution (95% confidence, 1-day)
    # Using simplified parametric VaR: position_value * 1.65 * daily_volatility
    estimated_volatility = 0.02  # Assumed 2% daily vol
    var_95 = position_value * 1.65 * estimated_volatility

    # VaR contribution as percentage of total portfolio
    var_contribution_pct = (
        (var_95 / total_market_value * 100) if total_market_value > 0 else 0.0
    )

    risk_metrics = {
        'success': True,
        'symbol': symbol,
        'broker_id': broker_id,
        'position_value': round(position_value, 2),
        'concentration_pct': round(concentration_pct, 2),
        'greeks': {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'delta_dollar': round(delta * position_value, 2),
        },
        'var': {
            'var_95_1d': round(var_95, 2),
            'var_contribution_pct': round(var_contribution_pct, 2),
            'method': 'parametric_simplified',
        },
        'quantity': pos.get('quantity', 0),
        'avg_price': pos.get('avg_price', 0),
        'current_price': pos.get('current_price', 0),
        'unrealized_pnl': pos.get('unrealized_pnl', 0),
        'timestamp': datetime.now().isoformat(),
    }

    return risk_metrics


def rebalance_positions(
    ds: DataService,
    broker_id: str,
    target_weights: Dict[str, float],
) -> Dict[str, Any]:
    """
    Calculate the trades needed to rebalance a portfolio to target weights.

    Args:
        ds: DataService instance
        broker_id: Broker ID
        target_weights: Dict mapping symbol to target portfolio weight (0.0 to 1.0)

    Returns:
        Dict with trades needed: {symbol: {'action': 'buy'|'sell', 'quantity': int}}
    """
    positions_result = get_live_positions(ds, broker_id)

    if not positions_result.get('success'):
        return {
            'success': False,
            'error': positions_result.get('error', 'Failed to get positions'),
            'trades': {},
            'broker_id': broker_id,
        }

    # Get total capital from broker funds
    try:
        broker, err = _get_broker(broker_id)
        if broker is None:
            return {'success': False, 'error': err, 'trades': {}}

        from domain.brokers.trading_types import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id)
        funds_response = broker.get_funds(creds)

        if funds_response.success and funds_response.data:
            total_assets = funds_response.data.total_assets
        else:
            total_assets = positions_result.get('total_market_value', 100000)
    except Exception:
        total_assets = positions_result.get('total_market_value', 100000)

    if total_assets <= 0:
        return {
            'success': False,
            'error': "No assets available for rebalancing",
            'trades': {},
            'broker_id': broker_id,
        }

    positions = positions_result.get('positions', {})
    trades = {}
    total_trade_value = 0.0

    # Get the latest prices for symbols from position data
    for symbol, target_weight in target_weights.items():
        pos = positions.get(symbol, {})
        current_price = pos.get('current_price', 100.0)
        current_qty = pos.get('quantity', 0)
        current_value = current_qty * current_price

        target_value = total_assets * target_weight
        value_diff = target_value - current_value
        quantity_diff = int(value_diff / current_price)

        if quantity_diff == 0:
            continue

        if quantity_diff > 0:
            trades[symbol] = {
                'action': 'buy',
                'quantity': quantity_diff,
                'estimated_price': current_price,
                'current_value': round(current_value, 2),
                'target_value': round(target_value, 2),
                'value_diff': round(value_diff, 2),
            }
        else:
            # Can't sell more than we hold
            sell_qty = min(abs(quantity_diff), current_qty)
            if sell_qty > 0:
                trades[symbol] = {
                    'action': 'sell',
                    'quantity': sell_qty,
                    'estimated_price': current_price,
                    'current_value': round(current_value, 2),
                    'target_value': round(target_value, 2),
                    'value_diff': round(value_diff, 2),
                }
                total_trade_value += sell_qty * current_price

    result = {
        'success': True,
        'trades': trades,
        'total_assets': round(total_assets, 2),
        'positions_affected': len(trades),
        'broker_id': broker_id,
        'timestamp': datetime.now().isoformat(),
    }

    logger.info(
        f"Rebalance calculated for {broker_id}: {len(trades)} trades needed "
        f"(total assets: {total_assets})"
    )

    return result


def close_position(
    ds: DataService,
    broker_id: str,
    symbol: str,
) -> Dict[str, Any]:
    """
    Close (flatten) a specific position with a market order.

    Args:
        ds: DataService instance
        broker_id: Broker ID
        symbol: Stock symbol to close

    Returns:
        Dict with close result including order details
    """
    positions_result = get_live_positions(ds, broker_id)

    if not positions_result.get('success'):
        return {
            'success': False,
            'error': positions_result.get('error', 'Failed to get positions'),
            'symbol': symbol,
            'broker_id': broker_id,
        }

    positions = positions_result.get('positions', {})
    pos = positions.get(symbol)

    if pos is None:
        return {
            'success': False,
            'error': f"No position found for {symbol}",
            'symbol': symbol,
            'broker_id': broker_id,
        }

    # Determine the action to close
    current_side = pos.get('side', 'long')
    quantity = pos.get('available_quantity', pos.get('quantity', 0))

    if current_side == 'long':
        close_action = 'sell'
    else:
        close_action = 'buy'

    order_details = {
        'symbol': symbol,
        'action': close_action,
        'quantity': quantity,
        'price': pos.get('current_price'),  # For reference
        'reason': 'close_position',
    }

    logger.info(
        f"Closing position: {broker_id} {symbol} "
        f"{close_action} {quantity} shares"
    )

    return {
        'success': True,
        'symbol': symbol,
        'broker_id': broker_id,
        'action': close_action,
        'quantity': quantity,
        'current_price': pos.get('current_price', 0),
        'current_pnl': pos.get('unrealized_pnl', 0),
        'order_details': order_details,
        'message': (
            f"Position close order ready: {close_action} {quantity} shares of {symbol}"
        ),
        'timestamp': datetime.now().isoformat(),
    }


def get_average_cost_basis(
    ds: DataService,
    trades: List[Dict[str, Any]],
    symbol: str,
) -> Dict[str, Any]:
    """
    Calculate the weighted average cost basis from a list of trades.

    Weighted average = sum(trade_qty * trade_price) / sum(trade_qty)

    Args:
        ds: DataService instance
        trades: List of trade records, each with at least 'quantity' and 'price'
        symbol: Stock symbol for labelling

    Returns:
        Dict with cost basis details
    """
    if not trades:
        return {
            'success': True,
            'symbol': symbol,
            'average_cost': 0.0,
            'total_quantity': 0,
            'total_cost': 0.0,
            'buys': 0,
            'sells': 0,
        }

    total_qty = 0.0
    total_cost = 0.0
    buy_count = 0
    sell_count = 0

    for trade in trades:
        qty = float(trade.get('quantity', 0))
        price = float(trade.get('price', 0))
        action = trade.get('action', 'buy')

        if action == 'buy':
            total_qty += qty
            total_cost += qty * price
            buy_count += 1
        elif action == 'sell':
            sell_count += 1

    avg_cost = total_cost / total_qty if total_qty > 0 else 0.0

    result = {
        'success': True,
        'symbol': symbol,
        'average_cost': round(avg_cost, 4),
        'total_quantity': total_qty,
        'total_cost': round(total_cost, 2),
        'buys': buy_count,
        'sells': sell_count,
        'method': 'weighted_average',
        'calculation': (
            f"sum(qty * price) / sum(qty) = "
            f"{total_cost:.2f} / {total_qty:.2f} = {avg_cost:.4f}"
        ),
        'timestamp': datetime.now().isoformat(),
    }

    return result
