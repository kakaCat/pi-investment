"""
TA-Lib Bridge Layer

Provides seamless integration between polars DataFrames and TA-Lib (C library).
"""
import polars as pl
import talib
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TALibBridge:
    """Bridge between polars DataFrames and TA-Lib technical indicators"""

    @staticmethod
    def add_indicators(df: pl.DataFrame) -> pl.DataFrame:
        """
        Add technical indicators to polars DataFrame using TA-Lib

        Args:
            df: DataFrame with OHLCV columns (open, high, low, close, volume)

        Returns:
            DataFrame with added indicator columns (rsi, macd, atr, bollinger bands)

        Raises:
            TALibBridgeError: If required columns are missing or conversion fails
        """
        from domain.quantlib.exceptions import TALibBridgeError

        # Validate required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise TALibBridgeError(f"Missing required columns: {missing_cols}")

        try:
            # Convert to numpy arrays (TA-Lib input format)
            close = df['close'].to_numpy()
            high = df['high'].to_numpy()
            low = df['low'].to_numpy()
            volume = df['volume'].to_numpy()

            # Calculate indicators using TA-Lib (C implementation - fast)
            rsi = talib.RSI(close, timeperiod=14)
            macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            atr = talib.ATR(high, low, close, timeperiod=14)
            bollinger_upper, bollinger_middle, bollinger_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)

            # Add indicators back to polars DataFrame
            result = df.with_columns([
                pl.Series("rsi", rsi),
                pl.Series("macd", macd),
                pl.Series("macd_signal", macd_signal),
                pl.Series("macd_hist", macd_hist),
                pl.Series("atr", atr),
                pl.Series("bollinger_upper", bollinger_upper),
                pl.Series("bollinger_middle", bollinger_middle),
                pl.Series("bollinger_lower", bollinger_lower),
            ])

            return result

        except Exception as e:
            logger.error(f"TA-Lib bridge error: {e}")
            raise TALibBridgeError(f"Failed to calculate indicators: {e}")

    @staticmethod
    def add_moving_averages(df: pl.DataFrame, periods: Optional[list] = None) -> pl.DataFrame:
        """
        Add simple moving averages to DataFrame

        Args:
            df: DataFrame with 'close' column
            periods: List of periods (default: [5, 10, 20, 60])

        Returns:
            DataFrame with ma5, ma10, ma20, ma60 columns
        """
        from domain.quantlib.exceptions import TALibBridgeError

        if 'close' not in df.columns:
            raise TALibBridgeError("Missing 'close' column for moving averages")

        if periods is None:
            periods = [5, 10, 20, 60]

        close = df['close'].to_numpy()

        ma_series = []
        for period in periods:
            ma = talib.SMA(close, timeperiod=period)
            ma_series.append(pl.Series(f"ma{period}", ma))

        return df.with_columns(ma_series)
