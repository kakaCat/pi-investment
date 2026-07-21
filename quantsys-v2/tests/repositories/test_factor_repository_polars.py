import polars as pl
import pytest
from adapters.outbound.repositories import FactorORMRepository


class TestFactorRepositoryPolars:
    def test_get_factor_history_returns_polars_dataframe(self):
        """Test that get_factor_history returns polars DataFrame"""
        # Arrange
        repo = FactorORMRepository()

        # Act
        result = repo.get_factor_history(
            symbol='600000',
            factor_name='momentum',
            start_date='2024-01-01',
            end_date='2024-12-31'
        )

        # Assert
        assert isinstance(result, pl.DataFrame)
        if not result.is_empty():
            assert 'factor_date' in result.columns
            assert 'factor_value' in result.columns

    def test_get_factors_range_returns_polars_dataframe(self):
        """Test that get_factors_range returns polars DataFrame"""
        # Arrange
        repo = FactorORMRepository()

        # Act
        result = repo.get_factors_range(
            symbol='600000',
            start_date='2024-01-01',
            end_date='2024-12-31'
        )

        # Assert
        assert isinstance(result, pl.DataFrame)
        if not result.is_empty():
            assert 'factor_date' in result.columns
            assert 'factor_name' in result.columns
            assert 'factor_value' in result.columns

    def test_empty_result_returns_empty_dataframe(self):
        """Test that empty results return empty DataFrame"""
        # Arrange
        repo = FactorORMRepository()

        # Act
        result = repo.get_factor_history(
            symbol='999999',
            factor_name='momentum',
            start_date='2024-01-01',
            end_date='2024-01-02'
        )

        # Assert
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()
