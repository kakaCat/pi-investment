"""Tests for StorageStage - writes cleaned data to database."""

import pytest
import pandas as pd
from datetime import date
from unittest.mock import Mock, MagicMock, patch

from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult
from domain.quantlib.stages.data_pipeline.storage_stage import StorageStage


@pytest.fixture
def sample_data():
    """Sample cleaned DataFrame with source column."""
    return pd.DataFrame({
        'symbol': ['000001.SH', '000001.SH', '000001.SZ'],
        'trade_date': [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 2)],
        'open': [100.0, 101.0, 50.0],
        'high': [102.0, 103.0, 52.0],
        'low': [99.0, 100.0, 49.0],
        'close': [101.0, 102.0, 51.0],
        'volume': [1000000, 1100000, 2000000],
        'amount': [101000000.0, 112200000.0, 102000000.0],
        'source': ['akshare', 'akshare', 'tushare'],
        'quality_score': [95.0, 98.0, 92.0]
    })


@pytest.fixture
def sample_data_no_source():
    """Sample DataFrame without source column (daily_klines only)."""
    return pd.DataFrame({
        'symbol': ['000001.SH', '000001.SH'],
        'trade_date': [date(2024, 1, 2), date(2024, 1, 3)],
        'open': [100.0, 101.0],
        'high': [102.0, 103.0],
        'low': [99.0, 100.0],
        'close': [101.0, 102.0],
        'volume': [1000000, 1100000],
        'amount': [101000000.0, 112200000.0],
        'quality_score': [95.0, 98.0]
    })


@pytest.fixture
def mock_kline_repo():
    """Mock KlineRepository."""
    repo = Mock()
    repo.save_daily_klines = Mock(return_value=3)
    repo.save_raw_klines = Mock(return_value=3)
    return repo


class TestStorageStage:
    """Test suite for StorageStage."""

    def test_write_to_daily_klines(self, sample_data, mock_kline_repo):
        """Test writing to daily_klines table."""
        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=sample_data,
            config={'batch_size': 1000}
        )

        result = stage.execute(context)

        assert result.success is True
        assert result.data.equals(sample_data)  # Pass-through
        assert len(result.errors) == 0

        # Verify daily_klines was called
        mock_kline_repo.save_daily_klines.assert_called_once()
        call_args = mock_kline_repo.save_daily_klines.call_args[0][0]
        assert len(call_args) == 3  # 3 records

        # Check metadata
        assert result.metadata['daily_klines_written'] == 3
        assert result.metadata['total_records'] == 3

    def test_write_to_raw_klines_with_source(self, sample_data, mock_kline_repo):
        """Test writing to raw_klines when source column exists."""
        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=sample_data,
            config={'batch_size': 1000}
        )

        result = stage.execute(context)

        assert result.success is True

        # Verify raw_klines was called
        mock_kline_repo.save_raw_klines.assert_called_once()
        call_args = mock_kline_repo.save_raw_klines.call_args[0][0]
        assert len(call_args) == 3

        # Check metadata
        assert result.metadata['raw_klines_written'] == 3

    def test_write_without_source_column(self, sample_data_no_source):
        """Test writing when source column is missing (daily_klines only)."""
        # Create a fresh mock for this test to avoid interference
        mock_repo = Mock()
        mock_repo.save_daily_klines = Mock(return_value=2)
        mock_repo.save_raw_klines = Mock(return_value=0)

        stage = StorageStage(kline_repo=mock_repo)
        context = PipelineContext(
            data=sample_data_no_source,
            config={'batch_size': 1000}
        )

        result = stage.execute(context)

        assert result.success is True

        # raw_klines should NOT be called
        mock_repo.save_raw_klines.assert_not_called()

        # daily_klines should be called
        mock_repo.save_daily_klines.assert_called_once()

        # Check metadata
        assert result.metadata['daily_klines_written'] == 2
        assert 'raw_klines_written' not in result.metadata

    def test_empty_dataframe(self, mock_kline_repo):
        """Test handling empty DataFrame."""
        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=pd.DataFrame(),
            config={}
        )

        result = stage.execute(context)

        assert result.success is True
        assert len(result.data) == 0
        assert result.metadata['daily_klines_written'] == 0

        # No repository calls should be made
        mock_kline_repo.save_daily_klines.assert_not_called()
        mock_kline_repo.save_raw_klines.assert_not_called()

    def test_batch_processing_large_dataset(self, mock_kline_repo):
        """Test batch processing with large dataset."""
        # Create large dataset (2500 records)
        large_data = pd.DataFrame({
            'symbol': ['000001.SH'] * 2500,
            'trade_date': [date(2024, 1, 1)] * 2500,
            'open': [100.0] * 2500,
            'high': [102.0] * 2500,
            'low': [99.0] * 2500,
            'close': [101.0] * 2500,
            'volume': [1000000] * 2500,
            'amount': [101000000.0] * 2500,
            'source': ['akshare'] * 2500,
            'quality_score': [95.0] * 2500
        })

        mock_kline_repo.save_daily_klines.return_value = 2500
        mock_kline_repo.save_raw_klines.return_value = 2500

        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=large_data,
            config={'batch_size': 1000}
        )

        result = stage.execute(context)

        assert result.success is True
        assert result.metadata['daily_klines_written'] == 2500
        assert result.metadata['raw_klines_written'] == 2500

    def test_database_error_handling(self, sample_data, mock_kline_repo):
        """Test handling database errors gracefully."""
        mock_kline_repo.save_daily_klines.side_effect = Exception("Database connection failed")

        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=sample_data,
            config={}
        )

        result = stage.execute(context)

        assert result.success is False
        assert len(result.errors) > 0
        assert 'Database connection failed' in str(result.errors[0])

    def test_partial_failure_raw_klines(self, sample_data, mock_kline_repo):
        """Test when raw_klines write fails but daily_klines succeeds."""
        mock_kline_repo.save_daily_klines.return_value = 3
        mock_kline_repo.save_raw_klines.side_effect = Exception("Raw klines write failed")

        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=sample_data,
            config={}
        )

        result = stage.execute(context)

        # Should still succeed if daily_klines write succeeds
        assert result.success is True
        assert result.metadata['daily_klines_written'] == 3

        # Error should be logged
        assert len(result.errors) > 0
        assert 'raw_klines' in str(result.errors[0]).lower()

    def test_statistics_tracking(self, sample_data, mock_kline_repo):
        """Test that statistics are properly tracked."""
        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=sample_data,
            config={'batch_size': 1000}
        )

        result = stage.execute(context)

        # Check all expected metadata fields
        assert 'daily_klines_written' in result.metadata
        assert 'raw_klines_written' in result.metadata
        assert 'total_records' in result.metadata
        assert 'batch_size' in result.metadata

        assert result.metadata['total_records'] == 3
        assert result.metadata['batch_size'] == 1000

    def test_upsert_behavior(self, sample_data, mock_kline_repo):
        """Test that upsert behavior is used (update existing records)."""
        # This test verifies that the repository methods are called
        # The actual upsert logic is tested in repository tests
        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=sample_data,
            config={}
        )

        result = stage.execute(context)

        assert result.success is True

        # Verify both methods were called (upsert semantics in repository)
        mock_kline_repo.save_daily_klines.assert_called_once()
        mock_kline_repo.save_raw_klines.assert_called_once()

    def test_dataframe_immutability(self, sample_data, mock_kline_repo):
        """Test that input DataFrame is not modified."""
        original_data = sample_data.copy()

        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=sample_data,
            config={}
        )

        result = stage.execute(context)

        # DataFrame should be unchanged
        pd.testing.assert_frame_equal(sample_data, original_data)
        pd.testing.assert_frame_equal(result.data, original_data)

    def test_default_batch_size(self, sample_data, mock_kline_repo):
        """Test default batch size when not specified in config."""
        stage = StorageStage(kline_repo=mock_kline_repo)
        context = PipelineContext(
            data=sample_data,
            config={}  # No batch_size specified
        )

        result = stage.execute(context)

        assert result.success is True
        # Default batch size should be 1000
        assert result.metadata['batch_size'] == 1000
