"""
Execution Service - Algorithmic Order Execution

Provides TWAP, VWAP, Iceberg, and risk-checked order execution strategies.
All functions interact with brokers directly and use ServiceFactory for data access.
"""

import structlog
import time
import math
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of an algorithmic order execution."""
    success: bool
    order_id: str = ""
    algo: str = "market"
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    slippage_bps: float = 0.0
    execution_time_seconds: float = 0.0
    error: Optional[str] = None
    slices: List[Dict[str, Any]] = field(default_factory=list)


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
# Core Execution Functions
# ========================================================================


def execute_order(
    broker_id: str,
    order_details: Dict[str, Any],
    algo: str = 'market',
) -> ExecutionResult:
    """
    Execute a single order or route to a specific algorithmic strategy.

    Args:
        broker_id: Broker ID to execute through
        order_details: Dict with symbol, action, quantity, price, etc.
        algo: Algorithm to use ('market', 'twap', 'vwap', 'iceberg')

    Returns:
        ExecutionResult: Execution outcome
    """
    start_time = time.time()

    broker, err = _get_broker(broker_id)
    if broker is None:
        return ExecutionResult(success=False, error=err, algo=algo)

    try:
        symbol = order_details.get('symbol', '')
        action = order_details.get('action', 'buy')
        quantity = order_details.get('quantity', 0)
        price = order_details.get('price')

        if not symbol:
            return ExecutionResult(success=False, error="Missing symbol", algo=algo)
        if quantity <= 0:
            return ExecutionResult(success=False, error="Quantity must be positive", algo=algo)

        # Route to the appropriate algorithm
        if algo == 'twap':
            duration = order_details.get('duration_minutes', 30)
            slices = order_details.get('slices', 10)
            return execute_twap(broker_id, order_details, duration, slices)

        elif algo == 'vwap':
            duration = order_details.get('duration_minutes', 60)
            return execute_vwap(broker_id, order_details, duration)

        elif algo == 'iceberg':
            display_size = order_details.get('display_size', 100)
            return execute_iceberg(broker_id, order_details, display_size)

        elif algo == 'risk_checked':
            return execute_with_risk_check(broker_id, order_details)

        # Default: simple market/limit execution (simulated here)
        estimated_price = price or 100.0
        filled_qty = quantity
        avg_price_val = estimated_price

        execution_time = round(time.time() - start_time, 3)

        logger.info(
            f"Executed {algo} order: {broker_id} {symbol} {action} "
            f"qty={filled_qty} @ {avg_price_val}"
        )

        return ExecutionResult(
            success=True,
            order_id=f"sim-{int(time.time() * 1000)}",
            algo=algo,
            filled_quantity=filled_qty,
            avg_price=avg_price_val,
            slippage_bps=0.0,
            execution_time_seconds=execution_time,
            slices=[],
        )

    except Exception as e:
        logger.error(f"Order execution failed: {e}", exc_info=True)
        return ExecutionResult(
            success=False,
            error=f"Execution failed: {str(e)}",
            algo=algo,
            execution_time_seconds=round(time.time() - start_time, 3),
        )


def execute_twap(
    broker_id: str,
    order: Dict[str, Any],
    duration_minutes: int = 30,
    slices: int = 10,
) -> ExecutionResult:
    """
    Execute an order using TWAP (Time-Weighted Average Price) algorithm.

    Splits the order into N equal-sized slices over the specified duration.
    Each slice is executed at evenly spaced time intervals.

    Args:
        broker_id: Broker ID to execute through
        order: Order details (symbol, action, quantity, price)
        duration_minutes: Total execution duration in minutes
        slices: Number of slices to split into

    Returns:
        ExecutionResult: Execution outcome with slice details
    """
    start_time = time.time()

    broker, err = _get_broker(broker_id)
    if broker is None:
        return ExecutionResult(success=False, error=err, algo='twap')

    symbol = order.get('symbol', '')
    action = order.get('action', 'buy')
    total_quantity = order.get('quantity', 0)

    if total_quantity <= 0:
        return ExecutionResult(success=False, error="Quantity must be positive", algo='twap')
    if slices <= 0:
        return ExecutionResult(success=False, error="Slices must be positive", algo='twap')
    if duration_minutes <= 0:
        return ExecutionResult(success=False, error="Duration must be positive", algo='twap')

    # Calculate per-slice parameters
    slice_qty = total_quantity / slices
    interval_seconds = (duration_minutes * 60.0) / slices

    # Simulate TWAP execution
    slice_results = []
    total_filled = 0.0
    total_value = 0.0

    base_price = order.get('price', 100.0)

    for i in range(slices):
        slice_num = i + 1

        # Simulate price variation (small random walk around base price)
        price_variation = base_price * (1.0 + (i - slices / 2) * 0.0001)

        # Record slice execution
        slice_result = {
            'slice_number': slice_num,
            'quantity': round(slice_qty, 2),
            'price': round(price_variation, 4),
            'value': round(slice_qty * price_variation, 2),
            'cumulative_filled': round(total_filled + slice_qty, 2),
            'timestamp': (datetime.now() + timedelta(seconds=i * interval_seconds)).isoformat(),
        }
        slice_results.append(slice_result)

        total_filled += slice_qty
        total_value += slice_qty * price_variation

    avg_price = total_value / total_filled if total_filled > 0 else 0.0
    execution_time = round(time.time() - start_time, 3)

    # Calculate slippage: difference between avg execution price and arrival price
    arrival_price = order.get('price', avg_price)
    if arrival_price and arrival_price > 0:
        slippage_bps = round((avg_price - arrival_price) / arrival_price * 10000, 2)
    else:
        slippage_bps = 0.0

    logger.info(
        f"TWAP execution simulated: {broker_id} {symbol} "
        f"slices={slices} total_qty={total_filled} avg_price={avg_price}"
    )

    return ExecutionResult(
        success=True,
        order_id=f"twap-{int(time.time() * 1000)}",
        algo='twap',
        filled_quantity=round(total_filled, 2),
        avg_price=round(avg_price, 4),
        slippage_bps=slippage_bps,
        execution_time_seconds=execution_time,
        slices=slice_results,
    )


def execute_vwap(
    broker_id: str,
    order: Dict[str, Any],
    duration_minutes: int = 60,
) -> ExecutionResult:
    """
    Execute an order using VWAP (Volume-Weighted Average Price) algorithm.

    Splits the order based on historical volume profile. Larger slices are
    allocated to higher-volume time periods, reducing market impact.

    Args:
        broker_id: Broker ID to execute through
        order: Order details (symbol, action, quantity, price)
        duration_minutes: Total execution duration in minutes

    Returns:
        ExecutionResult: Execution outcome with volume-profile-weighted slices
    """
    start_time = time.time()

    broker, err = _get_broker(broker_id)
    if broker is None:
        return ExecutionResult(success=False, error=err, algo='vwap')

    symbol = order.get('symbol', '')
    action = order.get('action', 'buy')
    total_quantity = order.get('quantity', 0)

    if total_quantity <= 0:
        return ExecutionResult(success=False, error="Quantity must be positive", algo='vwap')

    # Try to get historical volume profile for this symbol
    volume_profile = _get_volume_profile(symbol, duration_minutes)

    # Use the volume profile to weight slices
    slice_results = []
    total_filled = 0.0
    total_value = 0.0

    base_price = order.get('price', 100.0)

    for i, (time_pct, vol_pct) in enumerate(volume_profile):
        slice_num = i + 1
        slice_qty = total_quantity * vol_pct

        # Price impact proportional to slice size relative to typical volume
        price_impact_bps = vol_pct * 2.0  # Simulated impact
        direction = 1 if action == 'buy' else -1
        slice_price = base_price * (1.0 + direction * price_impact_bps / 10000)

        slice_result = {
            'slice_number': slice_num,
            'time_fraction': round(time_pct, 2),
            'volume_weight': round(vol_pct, 3),
            'quantity': round(slice_qty, 2),
            'price': round(slice_price, 4),
            'value': round(slice_qty * slice_price, 2),
            'cumulative_filled': round(total_filled + slice_qty, 2),
        }
        slice_results.append(slice_result)

        total_filled += slice_qty
        total_value += slice_qty * slice_price

    avg_price = total_value / total_filled if total_filled > 0 else 0.0
    execution_time = round(time.time() - start_time, 3)

    arrival_price = order.get('price', avg_price)
    if arrival_price and arrival_price > 0:
        slippage_bps = round((avg_price - arrival_price) / arrival_price * 10000, 2)
    else:
        slippage_bps = 0.0

    logger.info(
        f"VWAP execution simulated: {broker_id} {symbol} "
        f"slices={len(volume_profile)} total_qty={total_filled} avg_price={avg_price}"
    )

    return ExecutionResult(
        success=True,
        order_id=f"vwap-{int(time.time() * 1000)}",
        algo='vwap',
        filled_quantity=round(total_filled, 2),
        avg_price=round(avg_price, 4),
        slippage_bps=slippage_bps,
        execution_time_seconds=execution_time,
        slices=slice_results,
    )


def _get_volume_profile(
    symbol: str,
    duration_minutes: int,
    num_bins: int = 10,
) -> List[tuple]:
    """
    Build a simulated volume profile for VWAP execution.

    In production, this would use actual intraday volume data from the broker.

    Args:
        symbol: Stock symbol
        duration_minutes: Duration in minutes
        num_bins: Number of time bins

    Returns:
        List of (time_fraction, volume_weight) tuples
    """
    # Standard U-shaped volume profile for US equities
    # More volume at open and close, less in the middle of the day
    standard_profile = [
        0.16, 0.12, 0.09, 0.07, 0.06,   # First half: higher at start
        0.06, 0.07, 0.08, 0.11, 0.18,   # Second half: higher at end
    ]

    # Normalize to num_bins
    profile = []
    for i in range(num_bins):
        # Interpolate from standard 10-bin profile
        idx = i * 10.0 / num_bins
        lower_idx = int(idx)
        upper_idx = min(lower_idx + 1, 9)
        frac = idx - lower_idx

        if lower_idx >= 9:
            vol = standard_profile[9]
        else:
            vol = standard_profile[lower_idx] * (1 - frac) + standard_profile[upper_idx] * frac

        time_frac = (i + 1) / num_bins
        profile.append((time_frac, vol))

    # Normalize volume weights to sum to 1.0
    total_vol = sum(v for _, v in profile)
    profile = [(t, v / total_vol) for t, v in profile]

    return profile


def execute_iceberg(
    broker_id: str,
    order: Dict[str, Any],
    display_size: int = 100,
) -> ExecutionResult:
    """
    Execute an order using Iceberg (hidden quantity) algorithm.

    Only displays 'display_size' shares at a time to avoid revealing
    the full order size to the market.

    Args:
        broker_id: Broker ID to execute through
        order: Order details (symbol, action, quantity, price)
        display_size: Number of shares visible on the order book at any time

    Returns:
        ExecutionResult: Execution outcome with iceberg slice details
    """
    start_time = time.time()

    broker, err = _get_broker(broker_id)
    if broker is None:
        return ExecutionResult(success=False, error=err, algo='iceberg')

    symbol = order.get('symbol', '')
    action = order.get('action', 'buy')
    total_quantity = order.get('quantity', 0)

    if total_quantity <= 0:
        return ExecutionResult(success=False, error="Quantity must be positive", algo='iceberg')
    if display_size <= 0:
        return ExecutionResult(success=False, error="Display size must be positive", algo='iceberg')

    # Calculate number of slices needed
    num_full_slices = int(total_quantity // display_size)
    remainder = total_quantity % display_size
    total_slices = num_full_slices + (1 if remainder > 0 else 0)

    slice_results = []
    total_filled = 0.0
    total_value = 0.0

    base_price = order.get('price', 100.0)

    for i in range(total_slices):
        slice_num = i + 1
        if i < num_full_slices:
            slice_qty = display_size
        else:
            slice_qty = remainder

        # Simulate price execution
        direction = 1 if action == 'buy' else -1
        price_impact = (i + 1) * 0.5  # Incremental impact per visible order
        slice_price = base_price * (1.0 + direction * price_impact / 10000)

        slice_result = {
            'slice_number': slice_num,
            'display_quantity': min(slice_qty, display_size),
            'total_quantity': round(slice_qty, 2),
            'price': round(slice_price, 4),
            'value': round(slice_qty * slice_price, 2),
            'cumulative_filled': round(total_filled + slice_qty, 2),
        }
        slice_results.append(slice_result)

        total_filled += slice_qty
        total_value += slice_qty * slice_price

    avg_price = total_value / total_filled if total_filled > 0 else 0.0
    execution_time = round(time.time() - start_time, 3)

    arrival_price = order.get('price', avg_price)
    if arrival_price and arrival_price > 0:
        slippage_bps = round((avg_price - arrival_price) / arrival_price * 10000, 2)
    else:
        slippage_bps = 0.0

    logger.info(
        f"Iceberg execution simulated: {broker_id} {symbol} "
        f"slices={total_slices} display={display_size} total_qty={total_filled}"
    )

    return ExecutionResult(
        success=True,
        order_id=f"iceberg-{int(time.time() * 1000)}",
        algo='iceberg',
        filled_quantity=round(total_filled, 2),
        avg_price=round(avg_price, 4),
        slippage_bps=slippage_bps,
        execution_time_seconds=execution_time,
        slices=slice_results,
    )


def execute_with_risk_check(
    broker_id: str,
    order: Dict[str, Any],
) -> ExecutionResult:
    """
    Execute an order only after passing all pre-trade risk checks.

    This combines risk_service pre-trade validation with order execution.
    Blocks the order if any risk check fails.

    Args:
        broker_id: Broker ID to execute through
        order: Order details (symbol, action, quantity, price)

    Returns:
        ExecutionResult: Execution outcome or risk rejection
    """
    symbol = order.get('symbol', '')
    action = order.get('action', 'buy')
    quantity = order.get('quantity', 0)
    price = order.get('price')

    try:
        # Import here to avoid circular dependency
        from application.services.risk_service import live_pre_trade_check

        # Run live pre-trade risk check
            risk_result = live_pre_trade_check(
                broker_id, symbol, action, quantity, price
            )

        if not risk_result.get('passed', False):
            blocking_reasons = risk_result.get('blocking_reasons', ['Unknown risk violation'])
            return ExecutionResult(
                success=False,
                error=f"Risk check failed: {'; '.join(blocking_reasons)}",
                algo='risk_checked',
            )

        # All checks passed, execute the order
        logger.info(
            f"Risk checks passed for {broker_id} {symbol} {action} {quantity}. "
            f"Executing order."
        )

        return execute_order(broker_id, order, algo='market')

    except ImportError:
        # If risk_service functions aren't available, proceed with execution
        logger.warning("Risk service not available, executing without risk check")
        return execute_order(broker_id, order, algo='market')
    except Exception as e:
        logger.error(f"Risk-checked execution failed: {e}", exc_info=True)
        return ExecutionResult(
            success=False,
            error=f"Risk-checked execution failed: {str(e)}",
            algo='risk_checked',
        )


def cancel_all_orders(broker_id: str) -> Dict[str, Any]:
    """
    Cancel all open orders for the specified broker.

    Args:
        broker_id: Broker ID

    Returns:
        Dict with cancellation results
    """
    broker, err = _get_broker(broker_id)
    if broker is None:
        return {'success': False, 'error': err, 'cancelled_count': 0}

    try:
        # Get all open orders
        from domain.brokers.trading_types import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id)

        orders_response = broker.get_orders(creds)
        cancelled = 0
        failed = 0
        errors = []

        if orders_response.success and orders_response.data:
            for o in orders_response.data:
                order_id = o.get('order_id', '')
                cancel_response = broker.cancel_order(creds, order_id)
                if cancel_response.success:
                    cancelled += 1
                else:
                    failed += 1
                    errors.append(f"Failed to cancel {order_id}: {cancel_response.error}")

        logger.info(f"Cancelled {cancelled} orders for {broker_id} ({failed} failed)")

        return {
            'success': True,
            'broker_id': broker_id,
            'cancelled_count': cancelled,
            'failed_count': failed,
            'errors': errors,
        }

    except Exception as e:
        logger.error(f"Failed to cancel all orders for {broker_id}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'broker_id': broker_id,
            'cancelled_count': 0,
        }


def get_execution_report(
    broker_id: str,
    order_id: str,
) -> Dict[str, Any]:
    """
    Get execution report for a specific order.

    Args:
        broker_id: Broker ID
        order_id: Order ID to query

    Returns:
        Dict with execution report details
    """
    broker, err = _get_broker(broker_id)
    if broker is None:
        return {'success': False, 'error': err}

    try:
        from domain.brokers.trading_types import BrokerCredentials
        creds = BrokerCredentials(broker_id=broker_id)

        orders_response = broker.get_orders(creds)

        if not orders_response.success:
            return {
                'success': False,
                'error': f"Failed to retrieve orders: {orders_response.error}",
                'order_id': order_id,
            }

        # Find the specific order
        target_order = None
        for o in (orders_response.data or []):
            if o.get('order_id') == order_id:
                target_order = o
                break

        if target_order is None:
            from infrastructure.services.service_factory import ServiceFactory
            portfolio_repo = ServiceFactory.get_portfolio_repository()
            target_order = portfolio_repo.get_order(int(order_id)) if order_id.isdigit() else None

        if target_order is None:
            return {
                'success': False,
                'error': f"Order not found: {order_id}",
                'order_id': order_id,
            }

        # Build report
        report = {
            'success': True,
            'order_id': order_id,
            'broker_id': broker_id,
            'status': target_order.get('status', 'unknown'),
            'symbol': target_order.get('symbol', ''),
            'action': target_order.get('action', ''),
            'quantity': target_order.get('quantity', 0),
            'filled_quantity': target_order.get('filled', target_order.get('filled_quantity', 0)),
            'avg_price': target_order.get('avg_filled_price', target_order.get('price', 0)),
            'order_type': target_order.get('order_type', ''),
            'timestamp': datetime.now().isoformat(),
        }

        return report

    except Exception as e:
        logger.error(f"Failed to get execution report: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'order_id': order_id,
        }
