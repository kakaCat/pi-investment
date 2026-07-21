import polars as pl
import pytest
from datetime import date, timedelta
from domain.quantlib.technical.talib_bridge import TALibBridge


class TestTALibBridge:
    def test_add_indicators_returns_polars_dataframe(self):
        """Test that add_indicators returns polars DataFrame"""
        # Arrange
        start_date = date(2024, 1, 1)
        dates = [start_date + timedelta(days=i) for i in range(50)]
        df = pl.DataFrame({
            'trade_date': dates,
            'open': [100.0 + i * 0.5 for i in range(50)],
            'high': [102.0 + i * 0.5 for i in range(50)],
            'low': [98.0 + i * 0.5 for i in range(50)],
            'close': [100.5 + i * 0.5 for i in range(50)],
            'volume': [1000000 + i * 1000 for i in range(50)],
        })

        # Act
        result = TALibBridge.add_indicators(df)

        # Assert
        assert isinstance(result, pl.DataFrame)
        assert 'rsi' in result.columns
        assert 'macd' in result.columns
        assert 'atr' in result.columns
        assert len(result) == len(df)

    def test_add_indicators_handles_insufficient_data(self):
        """Test that add_indicators handles DataFrames with < 20 rows"""
        # Arrange
        df = pl.DataFrame({
            'open': [100.0] * 10,
            'high': [102.0] * 10,
            'low': [98.0] * 10,
            'close': [100.5] * 10,
            'volume': [1000000] * 10,
        })

        # Act
        result = TALibBridge.add_indicators(df)

        # Assert - Early rows will be NaN but DataFrame should be valid
        assert isinstance(result, pl.DataFrame)
        assert 'rsi' in result.columns
