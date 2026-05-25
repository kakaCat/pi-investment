"""
Bollinger Bands Breakout Strategy.

Price touches lower band -> Buy
Price touches upper band -> Sell
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from ..base import BaseStrategy, Signal
from datetime import datetime
from ...utils.confidence_calibration import calibrate_bollinger_confidence


class BollingerBreakoutStrategy(BaseStrategy):
    """
    Bollinger Bands Breakout Strategy.

    Parameters:
        bb_period: Bollinger Bands period (default: 20)
        bb_std: Number of standard deviations (default: 2.0)
        stop_loss_pct: Stop loss percentage (default: 0.05 = 5%)
        take_profit_pct: Take profit percentage (default: 0.10 = 10%)
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            'bb_period': 20,
            'bb_std': 2.0,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.10
        }
        if params:
            default_params.update(params)

        super().__init__(default_params)
        self.name = 'Bollinger_Breakout'

    def calculate_bollinger_bands(
        self,
        prices: pd.Series,
        period: int = 20,
        num_std: float = 2.0
    ) -> tuple:
        """
        Calculate Bollinger Bands.

        Args:
            prices: Series of closing prices
            period: Moving average period
            num_std: Number of standard deviations

        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        middle_band = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper_band = middle_band + (std * num_std)
        lower_band = middle_band - (std * num_std)

        return upper_band, middle_band, lower_band

    def calculate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Calculate Bollinger Bands breakout signals.

        Args:
            data: DataFrame with columns ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']

        Returns:
            List of Signal objects
        """
        signals = []

        if len(data) < self.params['bb_period']:
            return signals

        # Calculate Bollinger Bands
        data = data.copy()
        upper, middle, lower = self.calculate_bollinger_bands(
            data['close'],
            self.params['bb_period'],
            self.params['bb_std']
        )

        data['bb_upper'] = upper
        data['bb_middle'] = middle
        data['bb_lower'] = lower

        # Calculate band width for volatility assessment
        data['bb_width'] = (data['bb_upper'] - data['bb_lower']) / data['bb_middle']

        # Previous values for detecting touches
        data['close_prev'] = data['close'].shift(1)
        data['bb_lower_prev'] = data['bb_lower'].shift(1)
        data['bb_upper_prev'] = data['bb_upper'].shift(1)

        # Generate signals
        for idx, row in data.iterrows():
            if pd.isna(row['bb_upper']) or pd.isna(row['bb_lower']):
                continue

            symbol = row.get('symbol', 'UNKNOWN')
            timestamp = row.get('timestamp', datetime.now())
            close_price = row['close']

            # Lower band touch - Buy Signal
            # Price was above lower band and now touches or crosses below it
            if (row['close'] <= row['bb_lower'] and
                not pd.isna(row['close_prev']) and
                row['close_prev'] > row['bb_lower_prev']):

                # Only buy if we don't already have a position
                if not self.has_position(symbol):
                    signal = Signal(
                        timestamp=timestamp,
                        symbol=symbol,
                        action='buy',
                        price=close_price,
                        reason=f'bb_lower_touch_{row["bb_width"]:.3f}',
                        confidence=self._calculate_confidence(row, 'buy')
                    )
                    signals.append(signal)

                    # Set stop loss and take profit
                    stop_loss = close_price * (1 - self.params['stop_loss_pct'])
                    take_profit = close_price * (1 + self.params['take_profit_pct'])
                    self.set_stop_loss(symbol, stop_loss)
                    self.set_take_profit(symbol, take_profit)

            # Upper band touch - Sell Signal
            # Price was below upper band and now touches or crosses above it
            elif (row['close'] >= row['bb_upper'] and
                  not pd.isna(row['close_prev']) and
                  row['close_prev'] < row['bb_upper_prev'] and
                  self.has_position(symbol)):

                position = self.get_position(symbol)
                signal = Signal(
                    timestamp=timestamp,
                    symbol=symbol,
                    action='sell',
                    price=close_price,
                    quantity=position.quantity if position else 0,
                    reason=f'bb_upper_touch_{row["bb_width"]:.3f}',
                    confidence=self._calculate_confidence(row, 'sell')
                )
                signals.append(signal)

            # Mean reversion to middle band (optional exit)
            elif self.has_position(symbol) and row['close'] >= row['bb_middle']:
                position = self.get_position(symbol)
                # Only exit if we have profit
                if position and close_price > position.entry_price * 1.02:  # 2% profit
                    signal = Signal(
                        timestamp=timestamp,
                        symbol=symbol,
                        action='sell',
                        price=close_price,
                        quantity=position.quantity,
                        reason='bb_mean_reversion',
                        confidence=0.6
                    )
                    signals.append(signal)

        return signals

    def _calculate_confidence(self, row: pd.Series, action: str) -> float:
        """
        Calculate signal confidence based on band width and price position using Bayesian calibration.

        Args:
            row: DataFrame row with Bollinger Bands values
            action: 'buy' or 'sell'

        Returns:
            Confidence score (0-0.85)
        """
        if action == 'buy':
            # How far below lower band
            distance_pct = abs((row['bb_lower'] - row['close']) / row['bb_lower'])
        elif action == 'sell':
            # How far above upper band
            distance_pct = abs((row['close'] - row['bb_upper']) / row['bb_upper'])
        else:
            distance_pct = 0.0

        # Use Bayesian calibration
        confidence = calibrate_bollinger_confidence(distance_pct)

        # Band width (volatility) adjustment
        bb_width = row['bb_width']
        if bb_width > 0.1:  # High volatility - boost confidence slightly
            confidence = min(confidence * 1.05, 0.85)
        elif bb_width < 0.03:  # Low volatility - reduce confidence slightly
            confidence = confidence * 0.95

        # Volume confirmation
        if 'volume' in row and not pd.isna(row['volume']):
            if row['volume'] > 0:
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
            'description': f'Bollinger Bands: {self.params["bb_period"]}-period, {self.params["bb_std"]}σ',
            'entry_rules': [
                f'Buy when price touches lower Bollinger Band',
                f'Stop loss: {self.params["stop_loss_pct"]*100}%',
                f'Take profit: {self.params["take_profit_pct"]*100}%'
            ],
            'exit_rules': [
                'Sell when price touches upper Bollinger Band',
                'Or price reverts to middle band with profit',
                'Or stop loss/take profit triggered'
            ]
        }
