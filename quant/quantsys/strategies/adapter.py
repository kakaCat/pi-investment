"""
Strategy adapter for integrating with the new backtest engine.

This module provides an adapter layer that allows strategies built with
the BaseStrategy class to work with the event-driven backtest engine.
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from .base import BaseStrategy


class StrategyAdapter:
    """
    Adapter to make BaseStrategy compatible with BacktestEngine.

    The BacktestEngine expects strategies to implement:
        calculate_signals(date: str, data: pd.DataFrame) -> List[Dict]

    This adapter wraps BaseStrategy to provide that interface and
    maintains state for event-driven signal generation.
    """

    def __init__(self, strategy: BaseStrategy):
        """
        Initialize adapter with a strategy.

        Args:
            strategy: BaseStrategy instance
        """
        self.strategy = strategy
        self.strategy_name = strategy.__class__.__name__
        self._price_history = []
        self._has_position = False
        self._position_symbol = None

    def calculate_signals(self, date: str, data: pd.DataFrame) -> List[Dict]:
        """
        Calculate signals for the given date using event-driven approach.

        This method is called by BacktestEngine on each trading day.

        Args:
            date: Current date (YYYY-MM-DD)
            data: Historical data up to current date

        Returns:
            List of signal dictionaries:
            [
                {
                    'symbol': '000001',
                    'action': 'buy',  # or 'sell'
                    'reason': 'golden_cross_ma5_ma20'
                },
                ...
            ]
        """
        # Filter data up to current date
        current_data = data[data['date'] <= date].copy()

        if current_data.empty:
            return []

        # Get current bar
        today_data = current_data[current_data['date'] == date]
        if today_data.empty:
            return []

        bar = today_data.iloc[0].to_dict()

        # Update price history
        self._price_history.append(bar['close'])

        # Generate signal based on strategy type
        signals = []

        if self.strategy_name == 'MACrossStrategy':
            signal = self._ma_cross_signal(bar)
        elif self.strategy_name == 'RSIReversalStrategy':
            signal = self._rsi_reversal_signal(bar)
        elif self.strategy_name == 'BollingerBreakoutStrategy':
            signal = self._bollinger_breakout_signal(bar)
        else:
            signal = None

        if signal:
            signals.append(signal)

            # Update position state
            if signal['action'] == 'buy':
                self._has_position = True
                self._position_symbol = signal['symbol']
            elif signal['action'] == 'sell':
                self._has_position = False
                self._position_symbol = None

        return signals

    def _ma_cross_signal(self, bar: Dict) -> Dict:
        """Generate MA Cross signal."""
        fast_period = self.strategy.params.get('fast_period', 5)
        slow_period = self.strategy.params.get('slow_period', 20)

        if len(self._price_history) < slow_period:
            return None

        fast_ma = np.mean(self._price_history[-fast_period:])
        slow_ma = np.mean(self._price_history[-slow_period:])
        prev_fast_ma = np.mean(self._price_history[-fast_period-1:-1])
        prev_slow_ma = np.mean(self._price_history[-slow_period-1:-1])

        # Golden cross - buy signal (only if no position)
        if fast_ma > slow_ma and prev_fast_ma <= prev_slow_ma and not self._has_position:
            return {
                'symbol': bar['symbol'],
                'action': 'buy',
                'reason': f'golden_cross_ma{fast_period}_ma{slow_period}'
            }

        # Death cross - sell signal (only if has position)
        if fast_ma < slow_ma and prev_fast_ma >= prev_slow_ma and self._has_position:
            return {
                'symbol': bar['symbol'],
                'action': 'sell',
                'reason': f'death_cross_ma{fast_period}_ma{slow_period}'
            }

        return None

    def _rsi_reversal_signal(self, bar: Dict) -> Dict:
        """Generate RSI Reversal signal."""
        period = self.strategy.params.get('period', 14)
        oversold = self.strategy.params.get('oversold', 30)
        overbought = self.strategy.params.get('overbought', 70)

        if len(self._price_history) < period + 1:
            return None

        # Calculate RSI
        prices = np.array(self._price_history[-(period+1):])
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # Oversold - buy signal (only if no position)
        if rsi < oversold and not self._has_position:
            return {
                'symbol': bar['symbol'],
                'action': 'buy',
                'reason': f'rsi_oversold_{rsi:.1f}'
            }

        # Overbought - sell signal (only if has position)
        if rsi > overbought and self._has_position:
            return {
                'symbol': bar['symbol'],
                'action': 'sell',
                'reason': f'rsi_overbought_{rsi:.1f}'
            }

        return None

    def _bollinger_breakout_signal(self, bar: Dict) -> Dict:
        """Generate Bollinger Breakout signal."""
        period = self.strategy.params.get('period', 20)
        std_dev = self.strategy.params.get('std_dev', 2)

        if len(self._price_history) < period:
            return None

        prices = np.array(self._price_history[-period:])
        sma = np.mean(prices)
        std = np.std(prices)
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)

        current_price = bar['close']

        # Price at/below lower band - buy signal (mean reversion, only if no position)
        if current_price <= lower_band and not self._has_position:
            return {
                'symbol': bar['symbol'],
                'action': 'buy',
                'reason': f'lower_band_touch_{current_price:.2f}<={lower_band:.2f}'
            }

        # Price at/above upper band - sell signal (mean reversion, only if has position)
        if current_price >= upper_band and self._has_position:
            return {
                'symbol': bar['symbol'],
                'action': 'sell',
                'reason': f'upper_band_touch_{current_price:.2f}>={upper_band:.2f}'
            }

        return None

    def get_strategy_info(self) -> Dict[str, Any]:
        """Get underlying strategy information."""
        return self.strategy.get_strategy_info()

    def reset(self):
        """Reset strategy state."""
        self.strategy.reset()
        self._price_history = []
        self._has_position = False
        self._position_symbol = None
