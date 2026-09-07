"""
Backtrader Data Feed Adapter
=============================

Converts pandas DataFrame to Backtrader data feeds.

Supports:
- OHLCV data
- Automatic datetime index conversion
- Flexible column mapping
"""

import backtrader as bt
import pandas as pd
from typing import Optional


class PandasDataFeed(bt.feeds.PandasData):
    """
    Pandas DataFrame to Backtrader data feed adapter.
    
    Converts standard OHLCV DataFrame to Backtrader compatible format.
    
    Expected DataFrame format:
    - Index: DatetimeIndex or convertible to datetime
    - Columns: open, high, low, close, volume
    
    Example:
        >>> df = pd.DataFrame({
        ...     'trade_date': [...],
        ...     'open': [...],
        ...     'high': [...],
        ...     'low': [...],
        ...     'close': [...],
        ...     'volume': [...]
        ... })
        >>> data_feed = PandasDataFeed.from_dataframe(df, '600000.SH')
        >>> cerebro.adddata(data_feed)
    """
    
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', None),
    )
    
    @classmethod
    def from_dataframe(
        cls, 
        df: pd.DataFrame, 
        symbol: Optional[str] = None
    ) -> 'PandasDataFeed':
        """
        Create data feed from DataFrame.
        
        Args:
            df: OHLCV DataFrame with datetime index or trade_date column
            symbol: Stock symbol (optional, used for naming)
            
        Returns:
            PandasDataFeed instance ready for Backtrader
            
        Raises:
            ValueError: If required columns are missing
        """
        # Validate required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Make a copy to avoid modifying original
        df = df.copy()
        
        # Handle datetime index
        if 'trade_date' in df.columns:
            df = df.set_index('trade_date')
        
        # Convert index to DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception as e:
                raise ValueError(f"Cannot convert index to datetime: {e}")
        
        # Sort by date (Backtrader requires chronological order)
        df = df.sort_index()
        
        # Create data feed
        data_feed = cls(dataname=df)
        
        # Set name if provided
        if symbol:
            data_feed._name = symbol
        
        return data_feed
    
    @classmethod
    def from_klines(
        cls,
        klines: list,
        symbol: Optional[str] = None
    ) -> 'PandasDataFeed':
        """
        Create data feed from klines list (quantsys-v2 format).
        
        Args:
            klines: List of dicts with keys: trade_date, open, high, low, close, volume
            symbol: Stock symbol
            
        Returns:
            PandasDataFeed instance
            
        Example:
            >>> klines = [
            ...     {'trade_date': '2023-01-01', 'open': 100, ...},
            ...     {'trade_date': '2023-01-02', 'open': 101, ...},
            ... ]
            >>> data_feed = PandasDataFeed.from_klines(klines, '600000.SH')
        """
        if not klines:
            raise ValueError("klines cannot be empty")
        
        # Convert to DataFrame
        df = pd.DataFrame(klines)
        
        # Convert trade_date to datetime
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        return cls.from_dataframe(df, symbol)


def validate_dataframe(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Validate DataFrame format for Backtrader compatibility.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        (is_valid, error_message)
    """
    # Check if DataFrame is empty
    if df.empty:
        return False, "DataFrame is empty"
    
    # Check required columns
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        return False, f"Missing columns: {missing}"
    
    # Check for NaN values
    if df[required_cols].isna().any().any():
        return False, "DataFrame contains NaN values"
    
    # Check datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'trade_date' not in df.columns:
            return False, "No datetime index or trade_date column found"
    
    # Check data types
    for col in required_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            return False, f"Column {col} is not numeric"
    
    return True, ""
