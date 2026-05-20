"""
Moving Average Crossover Strategy.

Golden Cross (5-day MA crosses above 20-day MA) -> Buy
Death Cross (5-day MA crosses below 20-day MA) -> Sell
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from ..base import BaseStrategy, Signal
from datetime import datetime
from ...utils.confidence_calibration import calibrate_ma_confidence


class MACrossStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy.

    Parameters:
        fast_period: Fast MA period (default: 5)
        slow_period: Slow MA period (default: 20)
        stop_loss_pct: Stop loss percentage (default: 0.05 = 5%)
        take_profit_pct: Take profit percentage (default: 0.15 = 15%)
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            'fast_period': 5,
            'slow_period': 20,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.15
        }
        if params:
            default_params.update(params)

        super().__init__(default_params)
        self.name = 'MA_Cross'

    def calculate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Calculate MA crossover signals.

        Args:
            data: DataFrame with columns ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']

        Returns:
            List of Signal objects
        """
        signals = []

        if len(data) < self.params['slow_period']:
            return signals

        # Calculate moving averages
        data = data.copy()
        data['ma_fast'] = data['close'].rolling(window=self.params['fast_period']).mean()
        data['ma_slow'] = data['close'].rolling(window=self.params['slow_period']).mean()

        # Calculate crossover signals
        data['ma_diff'] = data['ma_fast'] - data['ma_slow']
        data['ma_diff_prev'] = data['ma_diff'].shift(1)

        # Detect crossovers
        data['golden_cross'] = (data['ma_diff'] > 0) & (data['ma_diff_prev'] <= 0)
        data['death_cross'] = (data['ma_diff'] < 0) & (data['ma_diff_prev'] >= 0)

        # Generate signals
        for idx, row in data.iterrows():
            if pd.isna(row['ma_fast']) or pd.isna(row['ma_slow']):
                continue

            symbol = row.get('symbol', 'UNKNOWN')
            timestamp = row.get('timestamp', datetime.now())
            close_price = row['close']

            # Golden Cross - Buy Signal
            if row['golden_cross']:
                # Only buy if we don't already have a position
                if not self.has_position(symbol):
                    signal = Signal(
                        timestamp=timestamp,
                        symbol=symbol,
                        action='buy',
                        price=close_price,
                        reason=f'golden_cross_ma{self.params["fast_period"]}_ma{self.params["slow_period"]}',
                        confidence=self._calculate_confidence(row)
                    )
                    signals.append(signal)

                    # Set stop loss and take profit
                    stop_loss = close_price * (1 - self.params['stop_loss_pct'])
                    take_profit = close_price * (1 + self.params['take_profit_pct'])
                    self.set_stop_loss(symbol, stop_loss)
                    self.set_take_profit(symbol, take_profit)

            # Death Cross - Sell Signal
            elif row['death_cross'] and self.has_position(symbol):
                position = self.get_position(symbol)
                signal = Signal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=close_price,
                    quantity=position.quantity if position else 0,
                    reason=f'death_cross_ma{self.params["fast_period"]}_ma{self.params["slow_period"]}',
                    confidence=self._calculate_confidence(row)
                )
                signals.append(signal)

        return signals

    def _calculate_confidence(self, row: pd.Series) -> float:
        """
        Calculate signal confidence based on MA separation using Bayesian calibration.

        Args:
            row: DataFrame row with MA values

        Returns:
            Confidence score (0-0.85)
        """
        # MA separation (larger separation = higher confidence)
        ma_diff_pct = abs(row['ma_diff']) / row['ma_slow']

        # Use Bayesian calibration
        confidence = calibrate_ma_confidence(ma_diff_pct)

        # Volume confirmation boost (small adjustment)
        if 'volume' in row and not pd.isna(row['volume']):
            if row['volume'] > 0:
                # Add up to 5% boost for volume confirmation
                confidence = min(confidence * 1.05, 0.85)

        return confidence

    def on_bar(self, bar: Dict[str, Any]) -> Signal:
        """
        Process each bar and check for stop loss/take profit.

        Args:
            bar: Bar data dictionary

        Returns:
            Signal if stop loss or take profit triggered
        """
        # Call parent method for stop loss/take profit checks
        signal = super().on_bar(bar)
        if signal:
            return signal

        # Additional logic can be added here
        return None

    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information."""
        return {
            'name': self.name,
            'type': 'trend_following',
            'parameters': self.params,
            'description': f'MA Crossover: {self.params["fast_period"]}/{self.params["slow_period"]}',
            'entry_rules': [
                f'Buy when MA{self.params["fast_period"]} crosses above MA{self.params["slow_period"]}',
                f'Stop loss: {self.params["stop_loss_pct"]*100}%',
                f'Take profit: {self.params["take_profit_pct"]*100}%'
            ],
            'exit_rules': [
                f'Sell when MA{self.params["fast_period"]} crosses below MA{self.params["slow_period"]}',
                'Or stop loss/take profit triggered'
            ]
        }
