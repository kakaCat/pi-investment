"""
Base strategy class for quantitative trading strategies.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from ..utils.confidence_calibration import (
    calibrate_stop_loss_confidence,
    calibrate_take_profit_confidence
)


@dataclass
class Signal:
    """Trading signal."""
    timestamp: datetime
    symbol: str
    action: str  # 'buy', 'sell', 'hold'
    price: float
    quantity: int = 0
    reason: str = ""
    confidence: float = 0.0


@dataclass
class Position:
    """Position information."""
    symbol: str
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class Order:
    """Order information."""
    order_id: str
    symbol: str
    action: str  # 'buy', 'sell'
    quantity: int
    price: float
    filled_price: Optional[float] = None
    filled_time: Optional[datetime] = None
    status: str = 'pending'  # 'pending', 'filled', 'cancelled'


class BaseStrategy(ABC):
    """
    Base class for all trading strategies.

    Subclasses must implement:
    - calculate_signals(): Generate trading signals from market data
    """

    def __init__(self, params: Dict[str, Any]):
        """
        Initialize strategy with parameters.

        Args:
            params: Strategy parameters (e.g., MA periods, RSI thresholds)
        """
        self.params = params
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.signals: List[Signal] = []
        self.equity_curve: List[float] = []
        self.trades: List[Dict] = []

    @abstractmethod
    def calculate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Calculate trading signals from market data.

        Args:
            data: DataFrame with OHLCV data and indicators
                  Required columns: ['open', 'high', 'low', 'close', 'volume']

        Returns:
            List of Signal objects
        """
        raise NotImplementedError("Subclass must implement calculate_signals()")

    def on_bar(self, bar: Dict[str, Any]) -> Optional[Signal]:
        """
        Called on each new bar/candle.

        Args:
            bar: Dictionary with bar data (timestamp, symbol, OHLCV)

        Returns:
            Signal if generated, None otherwise
        """
        symbol = bar['symbol']
        current_price = bar['close']

        # Update current position prices
        if symbol in self.positions:
            position = self.positions[symbol]
            position.current_price = current_price
            position.unrealized_pnl = (current_price - position.entry_price) * position.quantity

            # Check stop loss
            if position.stop_loss and current_price <= position.stop_loss:
                # Calculate loss percentage for confidence calibration
                loss_pct = abs((current_price - position.entry_price) / position.entry_price)
                confidence = calibrate_stop_loss_confidence(loss_pct)

                return Signal(
                    timestamp=bar['timestamp'],
                    symbol=symbol,
                    action='sell',
                    price=current_price,
                    quantity=position.quantity,
                    reason='stop_loss_triggered',
                    confidence=confidence
                )

            # Check take profit
            if position.take_profit and current_price >= position.take_profit:
                # Calculate profit percentage for confidence calibration
                profit_pct = (current_price - position.entry_price) / position.entry_price
                confidence = calibrate_take_profit_confidence(profit_pct)

                return Signal(
                    timestamp=bar['timestamp'],
                    symbol=symbol,
                    action='sell',
                    price=current_price,
                    quantity=position.quantity,
                    reason='take_profit_triggered',
                    confidence=confidence
                )

        return None

    def on_order_filled(self, order: Order):
        """
        Called when an order is filled.

        Args:
            order: Filled order object
        """
        symbol = order.symbol

        if order.action == 'buy':
            # Open or add to position
            if symbol in self.positions:
                pos = self.positions[symbol]
                total_cost = pos.entry_price * pos.quantity + order.filled_price * order.quantity
                pos.quantity += order.quantity
                pos.entry_price = total_cost / pos.quantity
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=order.quantity,
                    entry_price=order.filled_price,
                    entry_time=order.filled_time,
                    current_price=order.filled_price
                )

        elif order.action == 'sell':
            # Close or reduce position
            if symbol in self.positions:
                pos = self.positions[symbol]
                realized_pnl = (order.filled_price - pos.entry_price) * order.quantity

                # Record trade
                self.trades.append({
                    'symbol': symbol,
                    'entry_price': pos.entry_price,
                    'exit_price': order.filled_price,
                    'quantity': order.quantity,
                    'pnl': realized_pnl,
                    'entry_time': pos.entry_time,
                    'exit_time': order.filled_time,
                    'holding_period': (order.filled_time - pos.entry_time).days
                })

                pos.quantity -= order.quantity
                if pos.quantity <= 0:
                    del self.positions[symbol]

    def set_stop_loss(self, symbol: str, stop_loss_price: float):
        """Set stop loss for a position."""
        if symbol in self.positions:
            self.positions[symbol].stop_loss = stop_loss_price

    def set_take_profit(self, symbol: str, take_profit_price: float):
        """Set take profit for a position."""
        if symbol in self.positions:
            self.positions[symbol].take_profit = take_profit_price

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for a symbol."""
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """Check if strategy has a position in symbol."""
        return symbol in self.positions

    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Calculate strategy performance metrics.

        Returns:
            Dictionary with performance metrics
        """
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0
            }

        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] < 0]

        total_pnl = sum(t['pnl'] for t in self.trades)
        avg_pnl = total_pnl / total_trades

        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / total_trades if total_trades > 0 else 0.0,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0.0,
            'avg_loss': sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0.0,
            'max_win': max((t['pnl'] for t in self.trades), default=0.0),
            'max_loss': min((t['pnl'] for t in self.trades), default=0.0),
            'profit_factor': abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades else float('inf')
        }

    def reset(self):
        """Reset strategy state."""
        self.positions.clear()
        self.orders.clear()
        self.signals.clear()
        self.equity_curve.clear()
        self.trades.clear()
