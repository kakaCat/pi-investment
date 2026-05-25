"""
RSI Reversal Strategy.

RSI < 30 (oversold) -> Buy
RSI > 70 (overbought) -> Sell
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from ..base import BaseStrategy, Signal
from datetime import datetime
from ...utils.confidence_calibration import calibrate_rsi_confidence


class RSIReversalStrategy(BaseStrategy):
    """
    RSI Reversal Strategy.

    Parameters:
        rsi_period: RSI calculation period (default: 14)
        oversold_threshold: Oversold level (default: 30)
        overbought_threshold: Overbought level (default: 70)
        stop_loss_pct: Stop loss percentage (default: 0.05 = 5%)
        take_profit_pct: Take profit percentage (default: 0.10 = 10%)
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            'rsi_period': 14,
            'oversold_threshold': 30,
            'overbought_threshold': 70,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.10
        }
        if params:
            default_params.update(params)

        super().__init__(default_params)
        self.name = 'RSI_Reversal'

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index).

        Args:
            prices: Series of closing prices
            period: RSI period

        Returns:
            Series of RSI values
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Calculate RSI reversal signals.

        Args:
            data: DataFrame with columns ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']

        Returns:
            List of Signal objects
        """
        signals = []

        if len(data) < self.params['rsi_period'] + 1:
            return signals

        # Calculate RSI
        data = data.copy()
        data['rsi'] = self.calculate_rsi(data['close'], self.params['rsi_period'])

        # Previous RSI for detecting crossovers
        data['rsi_prev'] = data['rsi'].shift(1)

        # Generate signals
        for idx, row in data.iterrows():
            if pd.isna(row['rsi']) or pd.isna(row['rsi_prev']):
                continue

            symbol = row.get('symbol', 'UNKNOWN')
            timestamp = row.get('timestamp', datetime.now())
            close_price = row['close']
            rsi = row['rsi']
            rsi_prev = row['rsi_prev']

            # Oversold condition - Buy Signal
            if rsi < self.params['oversold_threshold'] and rsi_prev >= self.params['oversold_threshold']:
                # Only buy if we don't already have a position
                if not self.has_position(symbol):
                    signal = Signal(
                        timestamp=timestamp,
                        symbol=symbol,
                        action='buy',
                        price=close_price,
                        reason=f'rsi_oversold_{rsi:.1f}',
                        confidence=self._calculate_confidence(row, 'buy')
                    )
                    signals.append(signal)

                    # Set stop loss and take profit
                    stop_loss = close_price * (1 - self.params['stop_loss_pct'])
                    take_profit = close_price * (1 + self.params['take_profit_pct'])
                    self.set_stop_loss(symbol, stop_loss)
                    self.set_take_profit(symbol, take_profit)

            # Overbought condition - Sell Signal
            elif rsi > self.params['overbought_threshold'] and rsi_prev <= self.params['overbought_threshold']:
                if self.has_position(symbol):
                    position = self.get_position(symbol)
                    signal = Signal(
                        timestamp=timestamp,
                        symbol=symbol,
                        action='sell',
                        price=close_price,
                        quantity=position.quantity if position else 0,
                        reason=f'rsi_overbought_{rsi:.1f}',
                        confidence=self._calculate_confidence(row, 'sell')
                    )
                    signals.append(signal)

        return signals

    def _calculate_confidence(self, row: pd.Series, action: str) -> float:
        """
        Calculate signal confidence based on RSI extremity using Bayesian calibration.

        Args:
            row: DataFrame row with RSI values
            action: 'buy' or 'sell'

        Returns:
            Confidence score (0-0.85)
        """
        rsi = row['rsi']

        if action == 'buy':
            threshold = self.params['oversold_threshold']
            confidence = calibrate_rsi_confidence(rsi, threshold, 'buy')
        else:  # sell
            threshold = self.params['overbought_threshold']
            confidence = calibrate_rsi_confidence(rsi, threshold, 'sell')

        # Volume confirmation boost (small adjustment)
        if 'volume' in row and not pd.isna(row['volume']):
            if row['volume'] > 0:
                # Add up to 5% boost for volume confirmation, but respect max cap
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
        return super().on_bar(bar)

    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information."""
        return {
            'name': self.name,
            'type': 'mean_reversion',
            'parameters': self.params,
            'description': f'RSI Reversal: {self.params["rsi_period"]}-period RSI',
            'entry_rules': [
                f'Buy when RSI crosses below {self.params["oversold_threshold"]} (oversold)',
                f'Stop loss: {self.params["stop_loss_pct"]*100}%',
                f'Take profit: {self.params["take_profit_pct"]*100}%'
            ],
            'exit_rules': [
                f'Sell when RSI crosses above {self.params["overbought_threshold"]} (overbought)',
                'Or stop loss/take profit triggered'
            ]
        }
