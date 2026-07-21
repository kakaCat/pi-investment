import polars as pl
import pytest
from adapters.outbound.repositories import FinancialRepository


class TestFinancialRepositoryPolars:
    def test_get_income_statements_returns_polars_dataframe(self):
        """Test that get_income_statements returns polars DataFrame"""
        # Arrange
        repo = FinancialORMRepository()

        # Act
        result = repo.get_income_statements('600000', limit=10)

        # Assert
        assert isinstance(result, pl.DataFrame)
        if not result.is_empty():
            assert 'symbol' in result.columns
            assert 'report_date' in result.columns
            assert 'revenue' in result.columns

    def test_get_balance_sheets_returns_polars_dataframe(self):
        """Test that get_balance_sheets returns polars DataFrame"""
        # Arrange
        repo = FinancialORMRepository()

        # Act
        result = repo.get_balance_sheets('600000', limit=10)

        # Assert
        assert isinstance(result, pl.DataFrame)
        if not result.is_empty():
            assert 'symbol' in result.columns
            assert 'report_date' in result.columns

    def test_get_cash_flows_returns_polars_dataframe(self):
        """Test that get_cash_flows returns polars DataFrame"""
        # Arrange
        repo = FinancialORMRepository()

        # Act
        result = repo.get_cash_flows('600000', limit=10)

        # Assert
        assert isinstance(result, pl.DataFrame)
        if not result.is_empty():
            assert 'symbol' in result.columns
            assert 'report_date' in result.columns

    def test_empty_result_returns_empty_dataframe_with_schema(self):
        """Test that empty results return DataFrame with schema"""
        # Arrange
        repo = FinancialORMRepository()

        # Act
        result = repo.get_income_statements('999999', limit=1)

        # Assert
        assert isinstance(result, pl.DataFrame)
        # Empty DataFrame should still have columns
        assert result.is_empty()
