import polars as pl
import pytest
from datetime import date
from tests.fixtures.polars_test_data import create_test_klines, create_test_financials


class TestPolarsTestData:
    def test_create_test_klines_returns_polars_dataframe(self):
        """Test that create_test_klines returns valid polars DataFrame"""
        # Act
        df = create_test_klines(symbol='600000', days=252)

        # Assert
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 252
        assert 'symbol' in df.columns
        assert 'trade_date' in df.columns
        assert 'close' in df.columns
        assert df['close'].dtype == pl.Float64

    def test_create_test_klines_with_custom_params(self):
        """Test create_test_klines with custom parameters"""
        # Act
        df = create_test_klines(symbol='000001', days=100)

        # Assert
        assert len(df) == 100
        assert df['symbol'][0] == '000001'
