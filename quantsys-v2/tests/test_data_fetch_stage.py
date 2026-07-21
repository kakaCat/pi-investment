"""Tests for DataFetchStage."""

import pytest
import pandas as pd
from datetime import datetime
from domain.quantlib.stages.data_pipeline.data_fetch_stage import DataFetchStage
from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult


class TestDataFetchStage:
    """Test suite for DataFetchStage."""

    def test_fetch_from_single_source(self, mocker):
        """Test fetching data from a single source."""
        # Mock data source
        mock_source = mocker.Mock()
        mock_source.fetch_klines.return_value = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-05'],
            'close': [1800.0],
            'volume': [1000000]
        })

        # Mock registry
        mock_registry = mocker.Mock()
        mock_registry.get.return_value = mock_source

        # Create stage with mocked registry
        stage = DataFetchStage(
            sources=['akshare'],
            symbols=['000001.SH'],
            date_range=('2024-01-05', '2024-01-05')
        )
        stage.data_source_registry = mock_registry

        # Execute
        context = PipelineContext(data={}, config={}, metadata={})
        result = stage.execute(context)

        # Assertions
        assert result.success
        assert 'akshare' in result.data
        assert len(result.data['akshare']) == 1
        assert result.data['akshare']['symbol'].iloc[0] == '000001.SH'
        assert 'source' in result.data['akshare'].columns
        assert 'fetch_time' in result.data['akshare'].columns

    def test_fetch_from_multiple_sources(self, mocker):
        """Test fetching data from multiple sources."""
        # Mock akshare source
        mock_akshare = mocker.Mock()
        mock_akshare.fetch_klines.return_value = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-05'],
            'close': [1800.0],
            'volume': [1000000]
        })

        # Mock tushare source
        mock_tushare = mocker.Mock()
        mock_tushare.fetch_klines.return_value = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-05'],
            'close': [1805.0],
            'volume': [1100000]
        })

        # Mock registry
        mock_registry = mocker.Mock()
        mock_registry.get.side_effect = lambda name: mock_akshare if name == 'akshare' else mock_tushare

        # Create stage
        stage = DataFetchStage(
            sources=['akshare', 'tushare'],
            symbols=['000001.SH'],
            date_range=('2024-01-05', '2024-01-05')
        )
        stage.data_source_registry = mock_registry

        # Execute
        context = PipelineContext(data={}, config={}, metadata={})
        result = stage.execute(context)

        # Assertions
        assert result.success
        assert 'akshare' in result.data
        assert 'tushare' in result.data
        assert len(result.data) == 2
        assert result.metadata['sources_fetched'] == 2
        assert result.metadata['total_records'] == 2

    def test_source_failure_handling(self, mocker):
        """Test graceful handling when one source fails."""
        # Mock successful source
        mock_akshare = mocker.Mock()
        mock_akshare.fetch_klines.return_value = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-05'],
            'close': [1800.0],
            'volume': [1000000]
        })

        # Mock failing source
        mock_tushare = mocker.Mock()
        mock_tushare.fetch_klines.side_effect = Exception("Connection timeout")

        # Mock registry
        mock_registry = mocker.Mock()
        mock_registry.get.side_effect = lambda name: mock_akshare if name == 'akshare' else mock_tushare

        # Create stage
        stage = DataFetchStage(
            sources=['akshare', 'tushare'],
            symbols=['000001.SH'],
            date_range=('2024-01-05', '2024-01-05')
        )
        stage.data_source_registry = mock_registry

        # Execute
        context = PipelineContext(data={}, config={}, metadata={})
        result = stage.execute(context)

        # Assertions - should still succeed with partial data
        assert result.success
        assert 'akshare' in result.data
        assert 'tushare' not in result.data
        assert len(result.errors) == 1
        assert result.errors[0]['source'] == 'tushare'
        assert 'Connection timeout' in result.errors[0]['error']
        assert result.metadata['sources_fetched'] == 1

    def test_all_sources_fail(self, mocker):
        """Test behavior when all sources fail."""
        # Mock failing sources
        mock_source = mocker.Mock()
        mock_source.fetch_klines.side_effect = Exception("Network error")

        # Mock registry
        mock_registry = mocker.Mock()
        mock_registry.get.return_value = mock_source

        # Create stage
        stage = DataFetchStage(
            sources=['akshare', 'tushare'],
            symbols=['000001.SH'],
            date_range=('2024-01-05', '2024-01-05')
        )
        stage.data_source_registry = mock_registry

        # Execute
        context = PipelineContext(data={}, config={}, metadata={})
        result = stage.execute(context)

        # Assertions - should fail when all sources fail
        assert not result.success
        assert len(result.data) == 0
        assert len(result.errors) == 2
        assert result.metadata['sources_fetched'] == 0

    def test_empty_sources_validation(self):
        """Test that empty sources list raises ValueError."""
        with pytest.raises(ValueError, match="sources list cannot be empty"):
            DataFetchStage(
                sources=[],
                symbols=['000001.SH'],
                date_range=('2024-01-05', '2024-01-05')
            )

    def test_empty_symbols_validation(self):
        """Test that empty symbols list raises ValueError."""
        with pytest.raises(ValueError, match="symbols list cannot be empty"):
            DataFetchStage(
                sources=['akshare'],
                symbols=[],
                date_range=('2024-01-05', '2024-01-05')
            )

    def test_invalid_date_range_validation(self):
        """Test that invalid date_range raises ValueError."""
        # Test None date_range
        with pytest.raises(ValueError, match="date_range must be a tuple"):
            DataFetchStage(
                sources=['akshare'],
                symbols=['000001.SH'],
                date_range=None
            )

        # Test single element tuple
        with pytest.raises(ValueError, match="date_range must be a tuple"):
            DataFetchStage(
                sources=['akshare'],
                symbols=['000001.SH'],
                date_range=('2024-01-05',)
            )

        # Test empty tuple
        with pytest.raises(ValueError, match="date_range must be a tuple"):
            DataFetchStage(
                sources=['akshare'],
                symbols=['000001.SH'],
                date_range=()
            )
