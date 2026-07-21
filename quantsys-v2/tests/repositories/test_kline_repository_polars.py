import polars as pl
import pytest
from adapters.outbound.repositories import KlineORMRepository


class TestKlineRepositoryPolars:
    def test_get_daily_klines_returns_polars_dataframe(self):
        """Test that get_daily_klines returns polars DataFrame"""
        # Arrange
        repo = KlineORMRepository()

        # Act
        result = repo.get_daily_klines('600000', '2024-01-01', '2024-12-31')

        # Assert
        assert isinstance(result, pl.DataFrame)
        if not result.is_empty():
            assert 'trade_date' in result.columns
            assert 'close' in result.columns
            assert result['close'].dtype == pl.Float64

    def test_get_daily_klines_empty_result_has_schema(self):
        """Test that empty result returns DataFrame with schema"""
        # Arrange
        repo = KlineORMRepository()

        # Act
        result = repo.get_daily_klines('999999', '2024-01-01', '2024-01-02')

        # Assert
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()
        assert 'close' in result.columns  # Schema exists even when empty

    def test_get_latest_daily_kline_returns_polars_dataframe(self):
        """Test that get_latest_daily_kline returns polars DataFrame or None"""
        # Arrange
        repo = KlineORMRepository()

        # Act
        result = repo.get_latest_daily_kline('600000')

        # Assert
        if result is not None:
            assert isinstance(result, pl.DataFrame)
            assert len(result) == 1
